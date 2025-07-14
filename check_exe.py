import os
import sys

# Path to the executable
exe_path = os.path.join("dist", "Gemini_Whisper.exe")
full_path = os.path.abspath(exe_path)

print(f"Checking for executable at: {full_path}")

if os.path.exists(full_path):
    print(f"SUCCESS: Executable exists at {full_path}")
    print(f"File size: {os.path.getsize(full_path) / (1024*1024):.2f} MB")
else:
    print(f"ERROR: Executable not found at {full_path}")
    
    # Check if dist directory exists
    dist_dir = os.path.dirname(full_path)
    if os.path.exists(dist_dir):
        print(f"The dist directory exists at: {dist_dir}")
        print("Contents of dist directory:")
        for item in os.listdir(dist_dir):
            item_path = os.path.join(dist_dir, item)
            if os.path.isfile(item_path):
                print(f"  - {item} ({os.path.getsize(item_path) / (1024*1024):.2f} MB)")
            else:
                print(f"  - {item} (directory)")
    else:
        print(f"The dist directory does not exist at: {dist_dir}")
        
    # Check current directory
    print(f"Current working directory: {os.getcwd()}")
    print("Contents of current directory:")
    for item in os.listdir("."):
        print(f"  - {item}")
