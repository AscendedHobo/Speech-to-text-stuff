# Gemini Whisper Executable

This README provides instructions for using the Gemini Whisper executable that was created using PyInstaller.

## About the Executable

The executable is a standalone version of the Gemini_Whisper.py application, which provides:
- Audio transcription using OpenAI's Whisper models
- Multiple model size options (tiny, base, small, medium, large)
- Batch processing of multiple audio files
- Segment parsing and merging
- Drag and drop functionality for audio files

## Location of the Executable

After running the build process, the executable should be located at:
```
dist/Gemini_Whisper.exe
```

## How to Use the Executable

1. Double-click on `Gemini_Whisper.exe` to launch the application
2. The application will open with a GUI interface
3. Select a Whisper model size (base is the default)
4. Browse for audio files or drag and drop them into the application
5. Click "Transcribe Selected Files" to start the transcription process
6. The application will show progress and estimated time remaining
7. Once complete, you can access the transcription files in the same directory as your audio files

## Notes About First Run

- On first run, the application will download the selected Whisper model, which may take some time depending on your internet connection
- The models are downloaded to the user's cache directory, so subsequent runs will be faster
- The large model is the most accurate but also the slowest and requires the most memory

## Troubleshooting

If you encounter any issues:

1. Make sure you have sufficient disk space for the Whisper models
2. Ensure your computer meets the minimum requirements for running Whisper (especially for larger models)
3. If the application crashes, try using a smaller model size
4. For drag and drop functionality, make sure you're dropping valid audio files (.mp3, .wav, .m4a)

## Building the Executable Yourself

If you need to rebuild the executable:

1. Make sure you have PyInstaller installed: `pip install pyinstaller`
2. Run the build script: `python build_exe.py` or `build_exe.bat`
3. The new executable will be created in the `dist` directory
