import torch
import torchaudio
import soundfile
import os

print(f"Torch version: {torch.__version__}")
print(f"Torchaudio version: {torchaudio.__version__}")
print(f"Soundfile version: {soundfile.__version__}")

try:
    print(f"Available backends: {torchaudio.list_audio_backends()}")
except Exception as e:
    print(f"Could not list backends: {e}")

dummy_wav = "test_audio.wav"
if not os.path.exists(dummy_wav):
    import numpy as np
    sr = 44100
    data = np.random.uniform(-1, 1, sr)
    soundfile.write(dummy_wav, data, sr)
    print(f"Created dummy wav: {dummy_wav}")

print("\n--- Attempting load with default backend ---")
try:
    wav, sr = torchaudio.load(dummy_wav)
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")

print("\n--- Attempting load with backend='soundfile' ---")
try:
    wav, sr = torchaudio.load(dummy_wav, backend="soundfile")
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
