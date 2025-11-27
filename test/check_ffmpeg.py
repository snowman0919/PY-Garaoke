import shutil
import subprocess
import os

def check_ffmpeg():
    print("Checking for ffmpeg...")
    
    # Check in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"SUCCESS: ffmpeg found at: {ffmpeg_path}")
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            version_head = '\n'.join(result.stdout.splitlines()[:1])
            print(f"Version info head:\n{version_head}")
        except Exception as e:
            print(f"WARNING: ffmpeg found but failed to run: {e}")
    else:
        print("FAIL: ffmpeg not found in PATH.")
        print("Please ensure ffmpeg is installed and added to your system PATH.")
        print("If you just installed it, you might need to restart your terminal/IDE.")
        
    # Check pydub
    try:
        from pydub import AudioSegment
        from pydub.utils import which
        print("\nChecking pydub configuration...")
        pydub_ffmpeg = which("ffmpeg")
        if pydub_ffmpeg:
             print(f"SUCCESS: pydub found ffmpeg at: {pydub_ffmpeg}")
        else:
             print("FAIL: pydub could not find ffmpeg.")
    except ImportError:
        print("WARNING: pydub not installed.")

if __name__ == "__main__":
    check_ffmpeg()
