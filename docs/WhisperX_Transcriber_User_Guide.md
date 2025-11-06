# WhisperX Diarizing Transcriber

The WhisperX Diarizing Transcriber is a desktop application that wraps the
[whisperx](https://github.com/m-bain/whisperX) transcription toolkit with a
responsive Tk/ttk user interface.  It focuses on reliability, large batch
support and end-to-end speaker diarisation.

## Key features

- Responsive UI with background processing and cancellation support.
- Batch transcription with automatic combined transcript export.
- Optional speaker diarisation (Pyannote) with configurable speaker bounds.
- Multiple export formats: plain text, SRT, WebVTT and JSON.
- Enhanced segment parser for post-processing diarised output.
- Drag-and-drop support, audio preview (when `simpleaudio` is available) and
  detailed progress/ETA indicators.
- Comprehensive logging to `logs/whisperx_app.log` for troubleshooting.

## Requirements

The application uses optional extras whenever they are available:

| Capability            | Dependency                        |
| --------------------- | --------------------------------- |
| Modern theming        | `ttkbootstrap`                    |
| Drag and drop         | `tkinterdnd2`                     |
| Audio preview         | `simpleaudio`                     |
| Transcription runtime | `torch`, `whisperx`, `ffmpeg`     |
| Diarisation           | Hugging Face token + Pyannote via WhisperX |

Install the WhisperX stack (CUDA build shown as an example):

```bash
pip install whisperx
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Optional extras can be installed with:

```bash
pip install ttkbootstrap tkinterdnd2 simpleaudio
```

Ensure `ffmpeg` is available in your `PATH` for best file format coverage.

## Usage

1. Launch the application by executing `python -m automation_maker2.Gemini_WhisperX_TkUI`.
2. Select the desired WhisperX model and diarisation settings.
3. Add one or more audio files via **Add files** or by dragging files onto the
   list.  The UI accepts common formats (`.wav`, `.mp3`, `.m4a`, `.flac`, `.aac`,
   `.wma`, `.ogg`, `.opus`, `.mp4`).  Unsupported files are converted to mono
   16 kHz WAV automatically when `ffmpeg` is available.
4. Configure export formats and press **Start transcription**.
5. Monitor real-time progress, ETA estimates and per-file status.  Cancelling a
   job finishes the current file gracefully.
6. Combined outputs are written alongside individual transcripts.  The UI shows
   the latest transcript, segment file and combined output paths for quick access.
7. Use the **Segment Parser** tab to merge diarised lines with fine grained
   control over gap thresholds, minimum duration and speaker filtering.

## Logging and diagnostics

Runtime logs are rotated and stored at `logs/whisperx_app.log`.  The **Logs &
Settings** tab lets you refresh the log view, open the file, or copy useful
environment metadata to the clipboard when filing bug reports.

## Troubleshooting tips

- If diarisation fails, the application continues with transcription only and
  displays a warning.  Check the log file for stack traces.
- Lack of GPU support automatically falls back to CPU with `float32` compute.
- If `simpleaudio` is unavailable the preview button is disabled.
- Combined transcripts are timestamped to avoid overwriting previous runs.

## Keyboard shortcuts

Standard Tk shortcuts apply, for example `Ctrl+C` to copy log text and `Ctrl+V`
to paste the debug JSON output in the Logs tab.
