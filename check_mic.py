import sounddevice as sd
import numpy as np
import time

def check_microphone():
    print("Checking audio devices...")
    devices = sd.query_devices()
    print(devices)
    
    default_input = sd.default.device[0]
    print(f"\nDefault input device index: {default_input}")
    if default_input >= 0:
        print(f"Default device info: {devices[default_input]['name']}")

    print("\nRecording 3 seconds of audio to check levels...")
    duration = 3  # seconds
    fs = 44100
    
    try:
        myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        for i in range(30):
            time.sleep(0.1)
            # visual feedback of current volume
            # We can't easily access current buffer in sd.rec without callback
            # so we just wait.
        sd.wait()
        
        max_amp = np.max(np.abs(myrecording))
        mean_amp = np.mean(np.abs(myrecording))
        
        print(f"\nRecording finished.")
        print(f"Max Amplitude: {max_amp:.6f}")
        print(f"Mean Amplitude: {mean_amp:.6f}")
        
        if max_amp < 0.002:
            print("WARNING: Input is very quiet or silent. Check microphone settings.")
        else:
            print("Input level seems OK.")
            
    except Exception as e:
        print(f"Error recording: {e}")

if __name__ == "__main__":
    check_microphone()
