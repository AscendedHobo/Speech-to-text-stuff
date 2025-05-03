import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import whisper
import subprocess  # For non-Windows systems if needed

# Function to browse and select an MP3 file
def browse_mp3():
    path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
    if path:
        audio_path.set(path)
        status_label.config(text="Ready to transcribe.")

# Function to open the directory containing the transcript files
def open_directory():
    if not audio_path.get():
        messagebox.showerror("Error", "No file selected to determine the directory.")
        return
    directory = os.path.dirname(audio_path.get())
    try:
        os.startfile(directory)
    except AttributeError:
        subprocess.Popen(["xdg-open", directory])
    except Exception as e:
        messagebox.showerror("Error", f"Could not open directory: {e}")

# Function to transcribe the chosen audio file and save full transcript and segments
def transcribe_audio():
    if not audio_path.get():
        messagebox.showerror("Error", "Please choose an audio file first.")
        return

    status_label.config(text="Transcribing...")
    root.update()  # Refresh the GUI

    # Load model (change "base" to another model size if needed)
    model = whisper.load_model("base")
    result = model.transcribe(audio_path.get())

    # Save full transcript
    full_transcript_path = os.path.join(os.path.dirname(audio_path.get()), "full_transcript.txt")
    with open(full_transcript_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    # Save segments; each line will have the format: [start - end] text
    segments_path = os.path.join(os.path.dirname(audio_path.get()), "segments.txt")
    with open(segments_path, "w", encoding="utf-8") as f:
        for segment in result.get("segments", []):
            start = round(segment['start'], 2)
            end = round(segment['end'], 2)
            text = segment['text'].strip()
            f.write(f"[{start} - {end}] {text}\n")

    status_label.config(text="Transcription completed!")
    messagebox.showinfo("Success", f"Transcription completed!\nFull transcript saved to:\n{full_transcript_path}\nSegments saved to:\n{segments_path}")

# Function to browse and select a segments text file for parsing
def browse_segments_file():
    path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
    if path:
        segments_file_path.set(path)

# Function to parse (merge) segments based on a threshold value
def parse_segments():
    if not segments_file_path.get():
        messagebox.showerror("Error", "Please choose a segments text file first.")
        return
    try:
        threshold = float(threshold_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid numeric threshold.")
        return

    # Read segments from the file; expecting format: [start - end] text
    with open(segments_file_path.get(), "r", encoding="utf-8") as f:
        lines = f.readlines()

    segments = []
    pattern = re.compile(r"\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]\s*(.*)")
    for line in lines:
        match = pattern.match(line)
        if match:
            start = float(match.group(1))
            end = float(match.group(2))
            text = match.group(3).strip()
            segments.append({"start": start, "end": end, "text": text})

    # Merge segments if their duration is less than the threshold
    merged_segments = []
    if segments:
        current = segments[0]
        for seg in segments[1:]:
            duration = current["end"] - current["start"]
            if duration < threshold:
                current["end"] = seg["end"]
                current["text"] += " " + seg["text"]
            else:
                merged_segments.append(current)
                current = seg
        merged_segments.append(current)

    # Save the merged segments to a new file
    parsed_segments_path = os.path.join(os.path.dirname(segments_file_path.get()), "parsed_segments.txt")
    with open(parsed_segments_path, "w", encoding="utf-8") as f:
        for seg in merged_segments:
            start = round(seg['start'], 2)
            end = round(seg['end'], 2)
            f.write(f"[{start} - {end}] {seg['text']}\n")

    messagebox.showinfo("Success", f"Parsed segments saved to:\n{parsed_segments_path}")

# Set up the main window
root = tk.Tk()
root.title("Whisper Transcription & Segment Parser")

# Variables to hold file paths
audio_path = tk.StringVar()
segments_file_path = tk.StringVar()

# === Transcription Frame ===
trans_frame = tk.LabelFrame(root, text="Transcription", padx=10, pady=10)
trans_frame.pack(padx=10, pady=10, fill="x")

tk.Button(trans_frame, text="Browse Audio", command=browse_mp3).pack(side="left")
tk.Button(trans_frame, text="Transcribe", command=transcribe_audio).pack(side="left", padx=10)
tk.Button(trans_frame, text="Open Directory", command=open_directory).pack(side="left", padx=10)

# Status label for transcription process
status_label = tk.Label(trans_frame, text="Idle")
status_label.pack(side="left", padx=10)

# === Segment Parser Frame ===
parse_frame = tk.LabelFrame(root, text="Segment Parser", padx=10, pady=10)
parse_frame.pack(padx=10, pady=10, fill="x")

tk.Label(parse_frame, text="Threshold (sec):").pack(side="left")
threshold_entry = tk.Entry(parse_frame, width=10)
threshold_entry.insert(0, "0.5")
threshold_entry.pack(side="left", padx=5)

tk.Button(parse_frame, text="Browse Segments File", command=browse_segments_file).pack(side="left", padx=10)
tk.Button(parse_frame, text="Parse Segments", command=parse_segments).pack(side="left")

root.mainloop()
    