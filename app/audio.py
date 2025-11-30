import sounddevice as sd
import soundfile as sf
import numpy as np
import librosa
from PySide6.QtCore import QObject, Signal, QThread, QMutex, QMutexLocker
import time
from collections import deque

# Global Audio State
_INPUT_DEVICE_INDEX = None
_INPUT_SAMPLERATE = 44100
_OUTPUT_SAMPLERATE = 44100

def get_output_samplerate():
    try:
        device_info = sd.query_devices(kind='output')
        return int(device_info.get('default_samplerate', 44100))
    except Exception as e:
        print(f"Warning: Output SR query failed: {e}")
        return 44100

def probe_input_device():
    print("Probing audio input devices...")
    try:
        input_devices = sd.query_devices()
        candidates = []
        default_input = sd.default.device[0]
        
        if default_input >= 0 and input_devices[default_input]['max_input_channels'] > 0:
            candidates.append(default_input)
            
        for i, d in enumerate(input_devices):
            if d['max_input_channels'] > 0 and i != default_input:
                candidates.append(i)

        test_rates = [44100, 48000, 16000, 22050]
        
        for dev_idx in candidates:
            dev_info = input_devices[dev_idx]
            dev_default_sr = int(dev_info.get('default_samplerate', 44100))
            current_test_rates = [dev_default_sr] + [r for r in test_rates if r != dev_default_sr]
            
            for sr in current_test_rates:
                try:
                    with sd.InputStream(device=dev_idx, samplerate=sr, channels=1):
                        pass
                    print(f"Selected Input: {dev_info['name']} (ID: {dev_idx}) at {sr} Hz")
                    return dev_idx, sr
                except Exception:
                    continue
    except Exception as e:
        print(f"Probe error: {e}")
    
    return None, 44100

def initialize_audio_system():
    global _INPUT_DEVICE_INDEX, _INPUT_SAMPLERATE, _OUTPUT_SAMPLERATE
    _OUTPUT_SAMPLERATE = get_output_samplerate()
    _INPUT_DEVICE_INDEX, _INPUT_SAMPLERATE = probe_input_device()

initialize_audio_system()

class AudioInputEngine(QObject):
    """
    Singleton-like engine that manages a SINGLE input stream
    and distributes data to registered consumers (recorder, pitch detector).
    """
    _instance = None
    error_occurred = Signal(str)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.stream = None
        self.consumers = []
        self.mutex = QMutex()
        self.running = False

    def register_consumer(self, callback):
        with QMutexLocker(self.mutex):
            if callback not in self.consumers:
                self.consumers.append(callback)
            if not self.running and self.consumers:
                self.start_stream()

    def unregister_consumer(self, callback):
        with QMutexLocker(self.mutex):
            if callback in self.consumers:
                self.consumers.remove(callback)
            if self.running and not self.consumers:
                self.stop_stream()

    def start_stream(self):
        if self.running: return
        
        device = _INPUT_DEVICE_INDEX
        sr = _INPUT_SAMPLERATE
        
        def audio_callback(indata, frames, time_info, status):
            if status: print(f"Input status: {status}")
            # Broadcast data to all consumers
            data_copy = indata.copy()
            with QMutexLocker(self.mutex):
                for consumer in self.consumers:
                    try:
                        consumer(data_copy)
                    except Exception as e:
                        print(f"Consumer error: {e}")

        try:
            self.stream = sd.InputStream(
                device=device,
                samplerate=sr,
                channels=1,
                dtype='float32',
                callback=audio_callback
            )
            self.stream.start()
            self.running = True
            print(f"AudioInputEngine started on device {device} at {sr}Hz")
        except Exception as e:
            print(f"AudioInputEngine start failed: {e}")
            self.running = False
            self.error_occurred.emit(str(e))

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.running = False
        print("AudioInputEngine stopped")

class AudioRecorder(QObject):
    finished = Signal(str)
    recording_failed = Signal(str)
    
    def __init__(self, parent=None, channels=1):
        super().__init__(parent)
        self.recording_data = []
        self.filepath = None
        self.is_recording = False
        self.engine = AudioInputEngine.instance()

    def start_recording(self, filepath):
        self.filepath = filepath
        self.recording_data = []
        self.is_recording = True
        self.engine.error_occurred.connect(self._on_engine_error)
        self.engine.register_consumer(self._process_audio)

    def _process_audio(self, indata):
        if self.is_recording:
            self.recording_data.append(indata)

    def _on_engine_error(self, msg):
        if self.is_recording:
            self.stop_recording()
            self.recording_failed.emit(msg)

    def stop_recording(self):
        self.is_recording = False
        self.engine.unregister_consumer(self._process_audio)
        try:
            self.engine.error_occurred.disconnect(self._on_engine_error)
        except: pass
        
        if self.recording_data:
            import threading
            def save_file():
                try:
                    full_recording = np.concatenate(self.recording_data, axis=0)
                    sf.write(self.filepath, full_recording, _INPUT_SAMPLERATE)
                    self.finished.emit(self.filepath)
                except Exception as e:
                    print(f"Save error: {e}")
                    self.finished.emit("")
            save_thread = threading.Thread(target=save_file)
            save_thread.start()
        else:
            self.finished.emit("")

class RealtimePitchDetector(QObject): # Changed from QThread to QObject
    pitch_detected = Signal(float) 
    volume_detected = Signal(float) 

    def __init__(self, parent=None, blocksize=2048):
        super().__init__(parent)
        self.pitch_buffer = deque(maxlen=8) 
        self.silence_counter = 0
        self.engine = AudioInputEngine.instance()
        self.running = False
        self.sr = _INPUT_SAMPLERATE

    def start(self):
        self.running = True
        self.engine.register_consumer(self._process_audio)

    def stop(self):
        self.running = False
        self.engine.unregister_consumer(self._process_audio)

    def _process_audio(self, indata):
        if not self.running: return
        
        # Process in-place (lightweight) or spawn worker? 
        # Pitch detection is roughly 5-10ms. Input callback might block.
        # Ideally, we should push to a queue and have a worker thread consume it.
        # But for now let's try direct processing to see if it holds up.
        # If it glitches, we move calculation to thread.
        
        # Actually, fast autocorrelation is fast enough for Python? 
        # Maybe not. Let's run calculation in a separate thread to be safe.
        # But `RealtimePitchDetector` was a Thread before.
        # Let's re-make it a Thread that consumes a Queue.
        pass

# Re-implementing RealtimePitchDetector as a Thread that consumes from AudioInputEngine
import queue

class RealtimePitchDetector(QThread):
    pitch_detected = Signal(float) 
    volume_detected = Signal(float) 

    def __init__(self, parent=None, blocksize=2048):
        super().__init__(parent)
        self.queue = queue.Queue()
        self.running = False
        self.pitch_buffer = deque(maxlen=8) 
        self.silence_counter = 0
        self.engine = AudioInputEngine.instance()
        self.sr = _INPUT_SAMPLERATE

    def run(self):
        self.running = True
        self.engine.register_consumer(self._enqueue_audio)
        
        while self.running:
            try:
                audio_chunk = self.queue.get(timeout=1.0) # Wait for data
                self._analyze_chunk(audio_chunk)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Pitch loop error: {e}")

        self.engine.unregister_consumer(self._enqueue_audio)

    def _enqueue_audio(self, indata):
        if self.running:
            # We might need to downsample or buffer if chunks are too small?
            # AudioInputEngine sends blocks.
            self.queue.put(indata[:, 0].copy()) # Store mono

    def _analyze_chunk(self, audio_chunk):
        rms = np.sqrt(np.mean(audio_chunk**2))
        self.volume_detected.emit(rms)

        if rms < 0.015:
            self.silence_counter += 1
            if self.silence_counter > 3:
                self.pitch_detected.emit(0.0)
                self.pitch_buffer.clear()
            return

        n = len(audio_chunk)
        fft_spec = np.fft.rfft(audio_chunk, n=n*2)
        acorr = np.fft.irfft(fft_spec * np.conj(fft_spec))
        acorr = acorr[:n]
        
        if acorr[0] == 0: return
        acorr = acorr / acorr[0]

        min_freq, max_freq = 60, 1000
        min_lag = int(self.sr / max_freq)
        max_lag = int(self.sr / min_freq)
        
        pitch_found = False
        if max_lag < len(acorr):
            window = acorr[min_lag:max_lag]
            if len(window) > 0:
                peak_idx = np.argmax(window) + min_lag
                if acorr[peak_idx] > 0.3: 
                    pitch_found = True
                    if 0 < peak_idx < len(acorr) - 1:
                        alpha = acorr[peak_idx - 1]
                        beta = acorr[peak_idx]
                        gamma = acorr[peak_idx + 1]
                        if (2 * beta - alpha - gamma) != 0:
                            peak_idx += 0.5 * (alpha - gamma) / (2 * beta - alpha - gamma)
                    
                    pitch_hz = self.sr / peak_idx
                    self.pitch_buffer.append(pitch_hz)
                    self.silence_counter = 0
                    self.pitch_detected.emit(float(np.median(self.pitch_buffer)))
        
        if not pitch_found:
                self.silence_counter += 1
                if self.silence_counter > 3: self.pitch_detected.emit(0.0)

    def stop(self):
        self.running = False
        self.wait()

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