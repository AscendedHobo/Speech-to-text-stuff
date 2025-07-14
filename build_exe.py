import os
import subprocess
import sys
import time

def build_executable():
    print("Building Gemini_Whisper executable...")
    
    # Run PyInstaller with the spec file
    try:
        subprocess.run(["pyinstaller", "--clean", "Gemini_Whisper.spec"], check=True)
        print("\nBuild complete!")
        
        # Check if the executable was created
        exe_path = os.path.join("dist", "Gemini_Whisper.exe")
        if os.path.exists(exe_path):
            print(f"Executable created successfully at: {os.path.abspath(exe_path)}")
        else:
            print("Warning: Executable file not found in the expected location.")
        
    except subprocess.CalledProcessError as e:
        print(f"Error during build process: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_executable()
    
    # Keep console window open if run directly
    if success:
        print("\nPress Enter to exit...")
        input()
    else:
        print("\nBuild failed. Press Enter to exit...")
        input()
