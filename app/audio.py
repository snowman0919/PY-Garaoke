import sounddevice as sd
import soundfile as sf
import numpy as np
import librosa
from PySide6.QtCore import QObject, Signal, QThread
import time

class AudioPlayer(QObject):
    finished = Signal()
    position_changed = Signal(float)

    def __init__(self, parent=None, sr=22050):
        super().__init__(parent)
        self.sr = sr
        self.current_data = None
        self.stream = None
        self.start_time = 0.0
        self.duration = 0.0
        self.playing = False

    def load(self, filepath):
        try:
            self.current_data, self.sr = sf.read(filepath, dtype='float32')
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
        
        self.playback_data = self.current_data[start_frame:end_frame]
        self.playback_duration = len(self.playback_data) / self.sr
        
        if self.stream:
            self.stream.close()

        self.block_size = 1024 # Arbitrary block size, can be adjusted
        self.current_frame = 0
        self.playing = True

        def callback(outdata, frames, time_info, status):
            if status:
                print(status)
            
            chunk_end = self.current_frame + frames
            if chunk_end > len(self.playback_data):
                outdata[:len(self.playback_data) - self.current_frame] = self.playback_data[self.current_frame:]
                outdata[len(self.playback_data) - self.current_frame:] = 0 # Fill remaining with silence
                self.playing = False
                raise sd.CallbackStop
            else:
                outdata[:] = self.playback_data[self.current_frame:chunk_end]
                self.current_frame = chunk_end
                current_position_sec = (self.current_frame / self.sr) + self.start_time
                self.position_changed.emit(current_position_sec)

        self.stream = sd.OutputStream(
            samplerate=self.sr,
            channels=self.playback_data.shape[1] if self.playback_data.ndim > 1 else 1,
            dtype='float32',
            callback=callback,
            blocksize=self.block_size
        )
        self.stream.start()
        # In a real app, this should run in a separate thread or use QTimer for updates
        # For simplicity, will let the callback handle finishing
        # The stream will block until callbackstop or error
        # A more robust solution would be to manage the stream in a QThread.

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
    finished = Signal(str) # Emits filepath of recorded audio
    
    def __init__(self, parent=None, sr=22050, channels=1):
        super().__init__(parent)
        self.sr = sr
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

        self.stream = sd.InputStream(
            samplerate=self.sr,
            channels=self.channels,
            dtype='float32',
            callback=callback
        )
        self.stream.start()

    def stop_recording(self):
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.is_recording = False
            
            if self.recording_data:
                full_recording = np.concatenate(self.recording_data, axis=0)
                sf.write(self.filepath, full_recording, self.sr)
                self.finished.emit(self.filepath)
            else:
                print("No audio data recorded.")
                self.finished.emit("") # Emit empty string if no recording

class RealtimePitchDetector(QThread):
    pitch_detected = Signal(float) # Emits pitch in Hz
    volume_detected = Signal(float) # Emits RMS volume

    def __init__(self, parent=None, sr=22050, blocksize=1024):
        super().__init__(parent)
        self.sr = sr
        self.blocksize = blocksize
        self.running = False
        self.input_stream = None

    def run(self):
        self.running = True
        try:
            with sd.InputStream(samplerate=self.sr, blocksize=self.blocksize, channels=1, dtype='float32') as self.input_stream:
                while self.running:
                    indata, overflowed = self.input_stream.read(self.blocksize)
                    if overflowed:
                        print("Audio input overflowed!")
                    
                    audio_chunk = indata[:, 0] # Assume mono
                    
                    # Calculate RMS volume
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    self.volume_detected.emit(rms)

                    # Pitch detection
                    # Using a lighter weight pitch detection for real-time
                    # librosa.pyin can be too slow for very small blocks
                    # A more optimized real-time pitch detector might be needed for very low latency
                    try:
                        f0, _, _ = librosa.pyin(audio_chunk, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=self.sr, hop_length=self.blocksize // 2)
                        # Take the median pitch if multiple pitches are detected, or the first valid one
                        valid_pitches = f0[~np.isnan(f0)]
                        if len(valid_pitches) > 0:
                            median_pitch = np.median(valid_pitches)
                            self.pitch_detected.emit(median_pitch)
                        else:
                            self.pitch_detected.emit(0.0) # No pitch detected
                    except Exception as e:
                        print(f"Realtime pitch detection error: {e}")
                        self.pitch_detected.emit(0.0) # Emit 0 if error or no pitch

        except Exception as e:
            print(f"Error in RealtimePitchDetector stream: {e}")
        finally:
            self.running = False
            if self.input_stream:
                self.input_stream.close()

    def stop(self):
        self.running = False
        self.wait() # Wait for the thread to finish
