import sounddevice as sd
import soundfile as sf
import numpy as np
import librosa
from PySide6.QtCore import QObject, Signal, QThread
import time
from collections import deque

def get_target_samplerate():
    """
    Determines the target sample rate for the application.
    Prioritizes the default Output device's sample rate to ensure playback compatibility.
    """
    try:
        device_info = sd.query_devices(kind='output')
        return int(device_info.get('default_samplerate', 44100))
    except Exception as e:
        print(f"Warning: Could not query output device sample rate: {e}. Defaulting to 44100.")
        return 44100

# Global target sample rate to ensure consistency across all streams
TARGET_SR = get_target_samplerate()

class AudioPlayer(QObject):
    finished = Signal()
    position_changed = Signal(float)

    def __init__(self, parent=None, sr=22050):
        super().__init__(parent)
        self.sr = TARGET_SR # Initialize with target SR
        self.current_data = None
        self.stream = None
        self.start_time = 0.0
        self.duration = 0.0
        self.playing = False

    def load(self, filepath):
        try:
            # Load initially with original SR to avoid slow IO resampling if we can
            # But librosa.load might be slower than sf.read. 
            # Let's use sf.read and then resample if needed.
            data, original_sr = sf.read(filepath, dtype='float32')
            
            if original_sr != TARGET_SR:
                print(f"Resampling audio from {original_sr} to {TARGET_SR} Hz for playback...")
                # Handle mono and stereo
                if data.ndim > 1:
                    # librosa expects (channels, samples) for multi-channel
                    resampled = librosa.resample(data.T, orig_sr=original_sr, target_sr=TARGET_SR).T
                else:
                    resampled = librosa.resample(data, orig_sr=original_sr, target_sr=TARGET_SR)
                self.current_data = resampled.astype(np.float32) # Ensure float32
            else:
                self.current_data = data
                
            self.sr = TARGET_SR
            self.duration = len(self.current_data) / self.sr
            return True
        except Exception as e:
            print(f"Error loading audio file {filepath}: {e}")
            self.current_data = None
            return False

    def play(self, start_sec=0.0, end_sec=None):
        if self.current_data is None:
            return

        self.start_time = start_sec
        start_frame = int(start_sec * self.sr)
        end_frame = int(self.duration * self.sr if end_sec is None else end_sec * self.sr)
        
        # Prepare playback chunk
        chunk = self.current_data[start_frame:end_frame]
        
        # Force Stereo for better compatibility on macOS
        if chunk.ndim == 1:
            # Duplicate mono to stereo
            self.playback_data = np.column_stack((chunk, chunk))
        else:
            self.playback_data = chunk
            
        self.playback_duration = len(self.playback_data) / self.sr
        
        if self.stream:
            self.stream.close()

        self.block_size = 1024 
        self.current_frame = 0
        self.playing = True

        def callback(outdata, frames, time_info, status):
            if status:
                print(status)
            
            chunk_end = self.current_frame + frames
            if chunk_end > len(self.playback_data):
                valid_frames = len(self.playback_data) - self.current_frame
                outdata[:valid_frames] = self.playback_data[self.current_frame:]
                outdata[valid_frames:] = 0 # Fill remaining with silence
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
                channels=2, # Force Stereo
                dtype='float32',
                callback=callback,
                blocksize=self.block_size
            )
            self.stream.start()
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            self.playing = False

    def stop(self):
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.playing = False
            self.finished.emit()

    def is_playing(self):
        return self.playing
    
    def get_duration(self):
        return self.duration


class AudioRecorder(QObject):
    finished = Signal(str) 
    
    def __init__(self, parent=None, sr=22050, channels=1):
        super().__init__(parent)
        self.sr = TARGET_SR # Force consistent SR
        self.channels = channels
        self.recording_data = []
        self.stream = None
        self.filepath = None
        self.is_recording = False

    def start_recording(self, filepath):
        self.filepath = filepath
        self.recording_data = []
        self.is_recording = True

        def callback(indata, frames, time_info, status):
            if status:
                print(status)
            self.recording_data.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=self.sr,
                channels=self.channels,
                dtype='float32',
                callback=callback
            )
            self.stream.start()
        except Exception as e:
            print(f"Error starting recorder stream: {e}")
            self.is_recording = False

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
                        sf.write(self.filepath, full_recording, self.sr)
                        self.finished.emit(self.filepath)
                    except Exception as e:
                        print(f"Error saving recording: {e}")
                        self.finished.emit("")

                save_thread = threading.Thread(target=save_file)
                save_thread.start()
            else:
                print("No audio data recorded.")
                self.finished.emit("") 

class RealtimePitchDetector(QThread):
    pitch_detected = Signal(float) 
    volume_detected = Signal(float) 

    def __init__(self, parent=None, sr=22050, blocksize=2048):
        super().__init__(parent)
        self.sr = TARGET_SR # Force consistent SR
        self.blocksize = blocksize
        self.running = False
        self.input_stream = None
        self.pitch_buffer = deque(maxlen=5) 

    def run(self):
        self.running = True
        
        try:
            with sd.InputStream(samplerate=self.sr, blocksize=self.blocksize, channels=1, dtype='float32') as self.input_stream:
                while self.running:
                    indata, overflowed = self.input_stream.read(self.blocksize)
                    if overflowed:
                        print("Audio input overflowed!")
                    
                    audio_chunk = indata[:, 0] # Assume mono
                    
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    self.volume_detected.emit(rms)

                    try:
                        if rms < 0.02:
                            self.pitch_detected.emit(0.0)
                            self.pitch_buffer.clear()
                            continue

                        n = len(audio_chunk)
                        fft_spec = np.fft.rfft(audio_chunk, n=n*2)
                        acorr = np.fft.irfft(fft_spec * np.conj(fft_spec))
                        acorr = acorr[:n] 
                        
                        if acorr[0] == 0:
                            continue
                        acorr = acorr / acorr[0]

                        min_freq = 60
                        max_freq = 1000
                        min_lag = int(self.sr / max_freq)
                        max_lag = int(self.sr / min_freq)
                        
                        if max_lag < len(acorr):
                            window = acorr[min_lag:max_lag]
                            if len(window) > 0:
                                peak_idx = np.argmax(window) + min_lag
                                
                                if acorr[peak_idx] > 0.4: 
                                    if 0 < peak_idx < len(acorr) - 1:
                                        alpha = acorr[peak_idx - 1]
                                        beta = acorr[peak_idx]
                                        gamma = acorr[peak_idx + 1]
                                        if (2 * beta - alpha - gamma) != 0:
                                            offset = 0.5 * (alpha - gamma) / (2 * beta - alpha - gamma)
                                            peak_idx += offset
                                    
                                    pitch_hz = self.sr / peak_idx
                                    self.pitch_buffer.append(pitch_hz)
                                    
                                    smoothed_pitch = float(np.median(self.pitch_buffer))
                                    self.pitch_detected.emit(smoothed_pitch)
                                else:
                                    self.pitch_detected.emit(0.0)
                            else:
                                self.pitch_detected.emit(0.0)
                        else:
                            self.pitch_detected.emit(0.0)
                            
                    except Exception as e:
                        print(f"Realtime pitch detection error: {e}")
                        self.pitch_detected.emit(0.0)

        except Exception as e:
            print(f"Error in RealtimePitchDetector stream: {e}")
        finally:
            self.running = False
            if self.input_stream:
                self.input_stream.close()

    def stop(self):
        self.running = False
        self.wait()
