import sounddevice as sd
import soundfile as sf
import numpy as np
import librosa
from PySide6.QtCore import QObject, Signal, QThread
import time
from collections import deque

# Global State for Audio Devices
_INPUT_DEVICE_INDEX = None
_INPUT_SAMPLERATE = 44100
_OUTPUT_SAMPLERATE = 44100

def get_output_samplerate():
    try:
        device_info = sd.query_devices(kind='output')
        return int(device_info.get('default_samplerate', 44100))
    except Exception as e:
        print(f"Warning: Could not query output device sample rate: {e}. Defaulting to 44100.")
        return 44100

def probe_input_device():
    """
    Probes for a working input device and sample rate.
    Returns (device_index, sample_rate).
    """
    print("Probing audio input devices...")
    try:
        input_devices = sd.query_devices()
        candidates = []
        default_input = sd.default.device[0]
        
        # Check default first
        if default_input >= 0 and input_devices[default_input]['max_input_channels'] > 0:
            candidates.append(default_input)
            
        # Add others
        for i, d in enumerate(input_devices):
            if d['max_input_channels'] > 0 and i != default_input:
                candidates.append(i)

        test_rates = [44100, 48000, 16000, 22050] 
        
        for dev_idx in candidates:
            dev_info = input_devices[dev_idx]
            dev_default_sr = int(dev_info.get('default_samplerate', 44100))
            # Prioritize device default, then standard rates
            current_test_rates = [dev_default_sr] + [r for r in test_rates if r != dev_default_sr]
            
            for sr in current_test_rates:
                try:
                    with sd.InputStream(device=dev_idx, samplerate=sr, channels=1):
                        pass
                    print(f"Selected Input Device: {dev_info['name']} (Index {dev_idx}) at {sr} Hz")
                    return dev_idx, sr
                except Exception:
                    continue
    except Exception as e:
        print(f"Error probing input devices: {e}")
    
    print("Fallback: Using system default input.")
    return None, 44100

def initialize_audio_system():
    global _INPUT_DEVICE_INDEX, _INPUT_SAMPLERATE, _OUTPUT_SAMPLERATE
    _OUTPUT_SAMPLERATE = get_output_samplerate()
    _INPUT_DEVICE_INDEX, _INPUT_SAMPLERATE = probe_input_device()

# Initialize on module load
initialize_audio_system()

class AudioPlayer(QObject):
    finished = Signal()
    playback_failed = Signal(str)
    position_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sr = _OUTPUT_SAMPLERATE
        self.current_data = None
        self.stream = None
        self.start_time = 0.0
        self.duration = 0.0
        self.playing = False
        self._is_manual_stop = False

    def load(self, filepath):
        try:
            # Reload global SR in case it changed (unlikely for output, but safe)
            global _OUTPUT_SAMPLERATE
            self.sr = _OUTPUT_SAMPLERATE
            
            data, original_sr = sf.read(filepath, dtype='float32')
            
            if original_sr != self.sr:
                print(f"Resampling playback: {original_sr} -> {self.sr} Hz")
                if data.ndim > 1:
                    resampled = librosa.resample(data.T, orig_sr=original_sr, target_sr=self.sr).T
                else:
                    resampled = librosa.resample(data, orig_sr=original_sr, target_sr=self.sr)
                self.current_data = resampled.astype(np.float32) 
            else:
                self.current_data = data
                
            self.duration = len(self.current_data) / self.sr
            return True
        except Exception as e:
            print(f"Error loading audio: {e}")
            self.current_data = None
            return False

    def play(self, start_sec=0.0, end_sec=None):
        if self.current_data is None: return

        self.start_time = start_sec
        start_frame = int(start_sec * self.sr)
        end_frame = int(self.duration * self.sr if end_sec is None else end_sec * self.sr)
        
        chunk = self.current_data[start_frame:end_frame]
        
        if chunk.ndim == 1:
            self.playback_data = np.column_stack((chunk, chunk))
        else:
            self.playback_data = chunk
            
        if self.stream: self.stream.close()

        self.block_size = 1024 
        self.current_frame = 0
        self.playing = True
        self._is_manual_stop = False

        def callback(outdata, frames, time_info, status):
            if status: print(f"Playback status: {status}")
            
            chunk_end = self.current_frame + frames
            if chunk_end > len(self.playback_data):
                valid_frames = len(self.playback_data) - self.current_frame
                outdata[:valid_frames] = self.playback_data[self.current_frame:]
                outdata[valid_frames:] = 0
                self.playing = False
                raise sd.CallbackStop
            else:
                outdata[:] = self.playback_data[self.current_frame:chunk_end]
                self.current_frame = chunk_end
                current_position_sec = (self.current_frame / self.sr) + self.start_time
                self.position_changed.emit(current_position_sec)

        try:
            self.stream = sd.OutputStream(
                samplerate=self.sr,
                channels=2,
                dtype='float32',
                callback=callback,
                finished_callback=self._on_stream_finished,
                blocksize=self.block_size
            )
            self.stream.start()
        except Exception as e:
            print(f"Playback stream error: {e}")
            self.playing = False
            self.playback_failed.emit(str(e))

    def _on_stream_finished(self):
        if not self._is_manual_stop:
            self.finished.emit()

    def stop(self):
        if self.stream and self.stream.active:
            self._is_manual_stop = True
            self.stream.stop()
            self.stream.close()
            self.playing = False

    def is_playing(self):
        return self.playing
    
    def get_duration(self):
        return self.duration


class AudioRecorder(QObject):
    finished = Signal(str)
    recording_failed = Signal(str)
    
    def __init__(self, parent=None, channels=1):
        super().__init__(parent)
        self.channels = channels
        self.recording_data = []
        self.stream = None
        self.filepath = None
        self.is_recording = False

    def start_recording(self, filepath):
        self.filepath = filepath
        self.recording_data = []
        self.is_recording = True
        
        # Try to use current global settings
        device_idx = _INPUT_DEVICE_INDEX
        sr = _INPUT_SAMPLERATE

        def callback(indata, frames, time_info, status):
            if status: print(f"Recording status: {status}")
            self.recording_data.append(indata.copy())

        try:
            self._open_stream(device_idx, sr, callback)
        except Exception as e:
            print(f"Initial recording failed ({e}), re-probing devices...")
            # Re-probe and try once more
            initialize_audio_system()
            try:
                self._open_stream(_INPUT_DEVICE_INDEX, _INPUT_SAMPLERATE, callback)
            except Exception as final_e:
                print(f"Retry failed: {final_e}")
                self.is_recording = False
                self.recording_failed.emit(str(final_e))

    def _open_stream(self, device, sr, cb):
        self.stream = sd.InputStream(
            device=device,
            samplerate=sr,
            channels=self.channels,
            dtype='float32',
            callback=cb
        )
        self.stream.start()
        print(f"Recording started on device {device} at {sr}Hz")

    def stop_recording(self):
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.is_recording = False
            
            if self.recording_data:
                import threading
                def save_file():
                    try:
                        full_recording = np.concatenate(self.recording_data, axis=0)
                        # Save with the actual SR used
                        sf.write(self.filepath, full_recording, _INPUT_SAMPLERATE)
                        self.finished.emit(self.filepath)
                    except Exception as e:
                        print(f"Error saving recording: {e}")
                        self.finished.emit("")

                save_thread = threading.Thread(target=save_file)
                save_thread.start()
            else:
                self.finished.emit("") 
        else:
            self.finished.emit("")

class RealtimePitchDetector(QThread):
    pitch_detected = Signal(float) 
    volume_detected = Signal(float) 

    def __init__(self, parent=None, blocksize=2048):
        super().__init__(parent)
        self.blocksize = blocksize
        self.running = False
        self.input_stream = None
        self.pitch_buffer = deque(maxlen=8) 
        self.silence_counter = 0

    def run(self):
        self.running = True
        device = _INPUT_DEVICE_INDEX
        sr = _INPUT_SAMPLERATE
        
        try:
            with sd.InputStream(device=device, samplerate=sr, blocksize=self.blocksize, channels=1, dtype='float32') as self.input_stream:
                while self.running:
                    indata, overflowed = self.input_stream.read(self.blocksize)
                    if overflowed: print("Pitch input overflow")
                    
                    audio_chunk = indata[:, 0]
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    self.volume_detected.emit(rms)

                    try:
                        if rms < 0.015:
                            self.silence_counter += 1
                            if self.silence_counter > 3:
                                self.pitch_detected.emit(0.0)
                                self.pitch_buffer.clear()
                            continue

                        # Fast autocorrelation pitch detection
                        n = len(audio_chunk)
                        fft_spec = np.fft.rfft(audio_chunk, n=n*2)
                        acorr = np.fft.irfft(fft_spec * np.conj(fft_spec))
                        acorr = acorr[:n]
                        
                        if acorr[0] == 0: continue
                        acorr = acorr / acorr[0]

                        min_freq, max_freq = 60, 1000
                        min_lag = int(sr / max_freq)
                        max_lag = int(sr / min_freq)
                        
                        pitch_found = False
                        if max_lag < len(acorr):
                            window = acorr[min_lag:max_lag]
                            if len(window) > 0:
                                peak_idx = np.argmax(window) + min_lag
                                if acorr[peak_idx] > 0.3: 
                                    pitch_found = True
                                    # Parabolic interpolation
                                    if 0 < peak_idx < len(acorr) - 1:
                                        alpha = acorr[peak_idx - 1]
                                        beta = acorr[peak_idx]
                                        gamma = acorr[peak_idx + 1]
                                        if (2 * beta - alpha - gamma) != 0:
                                            peak_idx += 0.5 * (alpha - gamma) / (2 * beta - alpha - gamma)
                                    
                                    pitch_hz = sr / peak_idx
                                    self.pitch_buffer.append(pitch_hz)
                                    self.silence_counter = 0
                                    self.pitch_detected.emit(float(np.median(self.pitch_buffer)))
                        
                        if not pitch_found:
                             self.silence_counter += 1
                             if self.silence_counter > 3: self.pitch_detected.emit(0.0)
                            
                    except Exception as e:
                        print(f"Pitch calc error: {e}")
                        self.pitch_detected.emit(0.0)

        except Exception as e:
            print(f"Pitch detector stream error: {e}")
        finally:
            self.running = False
            if self.input_stream: self.input_stream.close()

    def stop(self):
        self.running = False
        self.wait()
