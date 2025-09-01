import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Listbox, Scrollbar, BooleanVar, END, MULTIPLE, ttk
import whisper
import subprocess
import platform
import time
import datetime

# Import TkinterDnD for drag and drop functionality
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    print("tkinterdnd2 library not found. Drag and drop functionality will be disabled.")
    print("You can install it with: pip install tkinterdnd2")

# Global list to store selected audio file paths
selected_audio_files = []

# Function to browse and select multiple audio files
def browse_multi_audio():
    global selected_audio_files
    paths = filedialog.askopenfilenames(
        title="Select Audio Files",
        filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")]
    )
    if paths:
        selected_audio_files = list(paths)
        audio_listbox.delete(0, END)
        for path in selected_audio_files:
            audio_listbox.insert(END, os.path.basename(path))

        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        status_label.config(text=f"{len(selected_audio_files)} file(s) selected. Ready.")
    else:
        if not selected_audio_files:
             audio_listbox.delete(0, END)
             progress_bar['value'] = 0
             eta_display.set("ETA: N/A")
             status_label.config(text="No files selected.")


# Function to clear output path display fields
def clear_output_displays():
     full_transcript_path_display.set("")
     segments_path_display.set("")
     parsed_segments_path_display.set("")
     segments_file_path.set("")


# Function to open the directory
def open_directory():
    dir_to_open = ""
    if parsed_segments_path_display.get() and os.path.exists(os.path.dirname(parsed_segments_path_display.get())):
         dir_to_open = os.path.dirname(parsed_segments_path_display.get())
    elif segments_file_path.get() and os.path.exists(os.path.dirname(segments_file_path.get())):
         dir_to_open = os.path.dirname(segments_file_path.get())
    elif full_transcript_path_display.get() and os.path.exists(os.path.dirname(full_transcript_path_display.get())):
        dir_to_open = os.path.dirname(full_transcript_path_display.get())
    elif selected_audio_files:
        dir_to_open = os.path.dirname(selected_audio_files[0])
    
    if not dir_to_open:
        messagebox.showerror("Error", "No files selected or processed yet to determine a relevant directory.")
        return
    if not os.path.isdir(dir_to_open):
         messagebox.showerror("Error", f"Directory not found: {dir_to_open}")
         return

    try:
        if platform.system() == "Windows":
            os.startfile(dir_to_open)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", dir_to_open])
        else:
            subprocess.Popen(["xdg-open", dir_to_open])
    except Exception as e:
        messagebox.showerror("Error", f"Could not open directory: {e}")


# Function to transcribe the chosen audio files
def transcribe_audio():
    global selected_audio_files
    selected_model = model_size.get()
    combine_output = combine_output_var.get()

    if not selected_audio_files:
        messagebox.showerror("Error", "Please select one or more audio files first.")
        return

    if not selected_model:
        messagebox.showerror("Error", "Please select a model size.")
        return

    progress_bar['value'] = 0
    progress_bar['maximum'] = len(selected_audio_files)
    eta_display.set("ETA: Calculating...")
    status_label.config(text=f"Loading {selected_model} model...")
    root.update()

    try:
        start_time_transcription_total = time.time()
        model = whisper.load_model(selected_model)
        status_label.config(text=f"Model '{selected_model}' loaded.")
        root.update()
        time.sleep(0.5)

        combined_transcript_text = ""
        processed_files_count = 0
        error_files = []
        last_individual_segments_path = ""
        total_files = len(selected_audio_files)

        for i, audio_file in enumerate(selected_audio_files):
            current_filename = os.path.basename(audio_file)
            status_label.config(text=f"Transcribing file {i+1}/{total_files}: {current_filename}...")
            progress_bar['value'] = i
            root.update()

            if i > 0:
                elapsed_time = time.time() - start_time_transcription_total
                avg_time_per_file = elapsed_time / i
                remaining_files = total_files - i
                eta_seconds_val = avg_time_per_file * remaining_files
                eta_minutes = int(eta_seconds_val // 60)
                eta_seconds_display = int(eta_seconds_val % 60)
                eta_display.set(f"ETA: {eta_minutes:02d}:{eta_seconds_display:02d}")
            elif i == 0 and total_files > 1:
                eta_display.set(f"ETA: Processing first...")

            root.update()

            try:
                result = model.transcribe(audio_file, fp16=False)

                output_dir = os.path.dirname(audio_file)
                base_filename = os.path.splitext(current_filename)[0]
                individual_transcript_filename = f"{base_filename}_full_transcript.txt"
                individual_segments_filename = f"{base_filename}_segments.txt"

                individual_transcript_path = os.path.join(output_dir, individual_transcript_filename)
                individual_segments_path = os.path.join(output_dir, individual_segments_filename)

                try:
                    file_creation_time = os.path.getctime(audio_file)
                    creation_datetime = datetime.datetime.fromtimestamp(file_creation_time)
                    formatted_datetime = creation_datetime.strftime("%d %b %Y, %H:%M:%S")
                except Exception as e_time:
                    print(f"Could not get creation time for {audio_file}: {e_time}")
                    formatted_datetime = "Unknown Time"

                header_info = f"===== Transcription for: {current_filename}  Datetime: {formatted_datetime} ====="

                if combine_output:
                    if combined_transcript_text:
                        combined_transcript_text += f"\n\n{header_info}\n\n"
                    else:
                        combined_transcript_text += f"{header_info}\n\n"
                    combined_transcript_text += result["text"]
                else:
                    with open(individual_transcript_path, "w", encoding="utf-8") as f:
                        f.write(f"{header_info}\n\n")
                        f.write(result["text"])
                    full_transcript_path_display.set(individual_transcript_path)

                with open(individual_segments_path, "w", encoding="utf-8") as f:
                    for segment in result.get("segments", []):
                        start = round(segment['start'], 2)
                        end = round(segment['end'], 2)
                        text = segment['text'].strip()
                        f.write(f"[{start:.2f} - {end:.2f}] {text}\n")
                last_individual_segments_path = individual_segments_path
                segments_path_display.set(last_individual_segments_path)
                processed_files_count += 1

            except Exception as e:
                error_files.append(f"{current_filename}: {e}")
                print(f"Error transcribing {current_filename}: {e}")
                status_label.config(text=f"Error on file {i+1}: {current_filename}. Skipping.")
                time.sleep(1)
            
            progress_bar['value'] = i + 1
            root.update()


        final_message = ""
        if combine_output:
            if combined_transcript_text:
                resolved_combined_save_path = filedialog.asksaveasfilename(
                    title="Save Combined Transcript As",
                    defaultextension=".txt",
                    filetypes=[("Text Files", "*.txt")],
                    initialfile="combined_transcript.txt",
                    initialdir=os.path.dirname(selected_audio_files[0]) if selected_audio_files else None
                )

                if resolved_combined_save_path:
                    try:
                        with open(resolved_combined_save_path, "w", encoding="utf-8") as f:
                            f.write(combined_transcript_text)
                        final_message += f"Combined transcript saved to:\n{resolved_combined_save_path}\n\n"
                        full_transcript_path_display.set(resolved_combined_save_path)
                    except Exception as e:
                        error_msg = f"Error saving combined transcript to {resolved_combined_save_path}: {e}"
                        final_message += error_msg + "\n\n"
                        messagebox.showerror("Save Error", error_msg)
                else:
                    final_message += "Combined transcript saving cancelled by user.\n\n"
            else:
                 final_message += "No successful transcriptions to combine.\n\n"

        progress_bar['value'] = total_files
        eta_display.set("ETA: Completed" if processed_files_count > 0 else "ETA: N/A")
        status_label.config(text="Transcription process finished.")
        final_message += f"Processed {processed_files_count} out of {total_files} files."
        if not combine_output:
             final_message += "\nIndividual transcripts and segment files saved in respective audio directories."
        else:
             final_message += "\nIndividual segment files saved in respective audio directories."

        if error_files:
            final_message += f"\n\nErrors occurred in {len(error_files)} file(s):\n" + "\n".join(error_files)
            messagebox.showwarning("Transcription Complete with Errors", final_message)
        elif processed_files_count > 0:
             messagebox.showinfo("Transcription Complete", final_message)
             if last_individual_segments_path:
                 segments_file_path.set(last_individual_segments_path)
        else:
             messagebox.showerror("Transcription Failed", "No files were successfully transcribed.")

    except Exception as e:
        progress_bar['value'] = 0
        eta_display.set("ETA: Error")
        status_label.config(text="Error during transcription setup.")
        messagebox.showerror("Transcription Error", f"An error occurred: {e}")


# Function to browse and select a SINGLE segments text file for parsing
def browse_segments_file():
    initial_dir = None
    if segments_path_display.get():
        initial_dir = os.path.dirname(segments_path_display.get())
    elif selected_audio_files:
         initial_dir = os.path.dirname(selected_audio_files[0])
    
    path = filedialog.askopenfilename(
        title="Select Segments File to Parse",
        filetypes=[("Text Files", "*.txt")],
        initialdir=initial_dir
    )
    if path:
        segments_file_path.set(path)
        parsed_segments_path_display.set("")


# Function to parse (merge) segments
def parse_segments():
    selected_segments_file = segments_file_path.get()
    if not selected_segments_file:
        messagebox.showerror("Error", "Please browse and select a segments text file first.")
        return
    try:
        threshold = float(threshold_entry.get())
        if threshold <= 0:
            messagebox.showerror("Error", "Threshold must be a positive number.")
            return
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid numeric threshold.")
        return

    try:
        with open(selected_segments_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        segments = []
        pattern = re.compile(r"\[\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*\]\s*(.*)")
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            match = pattern.match(line)
            if match:
                try:
                    start = float(match.group(1))
                    end = float(match.group(2))
                    text = match.group(3).strip()
                    if start > end:
                        print(f"Warning: Skipping segment on line {i+1} due to start time ({start}) > end time ({end}). Line: '{line}'")
                        continue
                    segments.append({"start": start, "end": end, "text": text})
                except ValueError:
                     print(f"Warning: Skipping segment on line {i+1} due to invalid number format. Line: '{line}'")
                     continue
            else:
                print(f"Warning: Skipping segment on line {i+1} due to format mismatch. Line: '{line}'")

        if not segments:
            messagebox.showwarning("Parsing Warning", "No valid segments found in the selected file.")
            return

        merged_segments = []
        if segments:
            current_segment = segments[0].copy()
            for next_segment in segments[1:]:
                time_gap = next_segment["start"] - current_segment["end"]
                if 0 <= time_gap < threshold:
                    current_segment["end"] = next_segment["end"]
                    separator = " " if current_segment["text"] else ""
                    current_segment["text"] += separator + next_segment["text"]
                else:
                    merged_segments.append(current_segment)
                    current_segment = next_segment.copy()
            merged_segments.append(current_segment)

        input_dir = os.path.dirname(selected_segments_file)
        input_basename = os.path.splitext(os.path.basename(selected_segments_file))[0]

        if input_basename.endswith("_segments"):
             parsed_filename = input_basename.replace("_segments", f"_parsed_segments_t{threshold}.txt")
        else:
             parsed_filename = f"{input_basename}_parsed_t{threshold}.txt"

        parsed_segments_path = os.path.join(input_dir, parsed_filename)

        with open(parsed_segments_path, "w", encoding="utf-8") as f:
            for seg in merged_segments:
                start = round(seg['start'], 2)
                end = round(seg['end'], 2)
                f.write(f"[{start:.2f} - {end:.2f}] {seg['text']}\n")

        parsed_segments_path_display.set(parsed_segments_path)
        messagebox.showinfo("Success", f"Parsed segments saved to:\n{parsed_segments_path}")

    except FileNotFoundError:
         messagebox.showerror("Error", f"File not found: {selected_segments_file}")
    except Exception as e:
        messagebox.showerror("Parsing Error", f"An error occurred during parsing: {e}")

# --- Drag and Drop Handler Functions ---
def handle_drag_enter(event):
    if TKDND_AVAILABLE:
        listbox_frame.config(bg="#e0ffe0") # Lighter green
        drop_label.config(bg="#e0ffe0", fg="#006400", text="Drop Audio Files Here!") # DarkGreen

def handle_drag_leave(event):
    if TKDND_AVAILABLE:
        listbox_frame.config(bg=root.cget('bg')) # Reset to default window background
        drop_label.config(bg=root.cget('bg'), fg="#666666", text="Drag & Drop Audio Files Here")

def handle_drop_files(event):
    global selected_audio_files
    if not TKDND_AVAILABLE:
        return

    handle_drag_leave(event) # Reset appearance

    dropped_data_string = event.data
    if not dropped_data_string:
        return

    path_candidates = re.findall(r'\{.*?\}|\S+', dropped_data_string)
    
    parsed_paths = []
    for cand in path_candidates:
        if cand.startswith('{') and cand.endswith('}'):
            parsed_paths.append(cand[1:-1])
        else:
            parsed_paths.append(cand)

    valid_audio_files = []
    valid_extensions = ('.mp3', '.wav', '.m4a')
    for path_str in parsed_paths:
        clean_path = path_str.strip('\'"')
        if os.path.isfile(clean_path) and clean_path.lower().endswith(valid_extensions):
            valid_audio_files.append(clean_path)
        else:
            print(f"Skipping invalid or non-audio file from drop: {path_str}")
    
    if valid_audio_files:
        selected_audio_files = valid_audio_files
        audio_listbox.delete(0, END)
        for path in selected_audio_files:
            audio_listbox.insert(END, os.path.basename(path))
        
        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        status_label.config(text=f"{len(selected_audio_files)} file(s) dropped. Ready.")
    elif dropped_data_string:
        status_label.config(text="No valid audio files found in dropped items.")

# --- GUI Setup ---
if TKDND_AVAILABLE:
    root = TkinterDnD.Tk()
else:
    root = tk.Tk()

root.title("Gemini Whisper: Multi-Transcription & Segment Parser")
root.geometry("800x700") # Set a default window size
root.resizable(True, True)

# Apply a modern theme
style = ttk.Style()
style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'

# Configure styles for widgets
style.configure('TFrame', background='#f0f0f0')
style.configure('TLabelFrame', background='#f0f0f0', font=('Helvetica', 10, 'bold'))
style.configure('TLabel', background='#f0f0f0', font=('Helvetica', 9))
style.configure('TButton', font=('Helvetica', 9, 'bold'), padding=5)
style.map('TButton', background=[('active', '#e0e0e0')])
style.configure('TRadiobutton', background='#f0f0f0', font=('Helvetica', 9))
style.configure('TCheckbutton', background='#f0f0f0', font=('Helvetica', 9))
style.configure('TEntry', fieldbackground='white', font=('Helvetica', 9))
style.configure('TProgressbar', thickness=10)
style.configure('TListbox', font=('Helvetica', 9)) # No direct TListbox style, but for consistency

# Variables
model_size = tk.StringVar(value="large") # Default to large
combine_output_var = BooleanVar(value=False)
segments_file_path = tk.StringVar()
full_transcript_path_display = tk.StringVar()
segments_path_display = tk.StringVar()
parsed_segments_path_display = tk.StringVar()
eta_display = tk.StringVar(value="ETA: N/A")


# === Model Selection Frame ===
model_frame = ttk.LabelFrame(root, text="1. Select Whisper Model Size", padding=(10, 10))
model_frame.pack(padx=10, pady=5, fill="x")

model_options_frame = ttk.Frame(model_frame)
model_options_frame.pack(fill="x")

ttk.Radiobutton(model_options_frame, text="Tiny (Fastest, Least Accurate)", variable=model_size, value="tiny").grid(row=0, column=0, sticky="w", padx=5, pady=2)
ttk.Radiobutton(model_options_frame, text="Base", variable=model_size, value="base").grid(row=1, column=0, sticky="w", padx=5, pady=2)
ttk.Radiobutton(model_options_frame, text="Small", variable=model_size, value="small").grid(row=2, column=0, sticky="w", padx=5, pady=2)
ttk.Radiobutton(model_options_frame, text="Medium", variable=model_size, value="medium").grid(row=3, column=0, sticky="w", padx=5, pady=2)
ttk.Radiobutton(model_options_frame, text="Large (Slowest, Most Accurate)", variable=model_size, value="large").grid(row=4, column=0, sticky="w", padx=5, pady=2)


# === Transcription Frame ===
trans_frame = ttk.LabelFrame(root, text="2. Transcribe Audio Files", padding=(10, 10))
trans_frame.pack(padx=10, pady=10, fill="x")

# Browse and Drop Zone
browse_drop_frame = ttk.Frame(trans_frame)
browse_drop_frame.pack(fill="x", pady=(0, 5))

ttk.Button(browse_drop_frame, text="Browse Audio Files", command=browse_multi_audio).pack(side="left", padx=(0, 10))

listbox_frame = ttk.Frame(browse_drop_frame, relief=tk.GROOVE, borderwidth=2)
listbox_frame.pack(side="left", fill="both", expand=True)

drop_label = ttk.Label(listbox_frame, text="Drag & Drop Audio Files Here", anchor="center", foreground="#666666")
drop_label.pack(fill="x", pady=(5, 0))

audio_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical")
audio_listbox = Listbox(listbox_frame, height=4, yscrollcommand=audio_scrollbar.set, selectmode=MULTIPLE, relief=tk.FLAT)
audio_scrollbar.config(command=audio_listbox.yview)
audio_scrollbar.pack(side="right", fill="y")
audio_listbox.pack(side="left", fill="both", expand=True, pady=(0, 5))

if TKDND_AVAILABLE:
    listbox_frame.drop_target_register(DND_FILES)
    listbox_frame.dnd_bind('<<Drop>>', handle_drop_files)
    listbox_frame.dnd_bind('<<DragEnter>>', handle_drag_enter)
    listbox_frame.dnd_bind('<<DragLeave>>', handle_drag_leave)
    
    drop_label.drop_target_register(DND_FILES)
    drop_label.dnd_bind('<<Drop>>', handle_drop_files)
    drop_label.dnd_bind('<<DragEnter>>', handle_drag_enter)
    drop_label.dnd_bind('<<DragLeave>>', handle_drag_leave)

    audio_listbox.drop_target_register(DND_FILES)
    audio_listbox.dnd_bind('<<Drop>>', handle_drop_files)
    audio_listbox.dnd_bind('<<DragEnter>>', handle_drag_enter)
    audio_listbox.dnd_bind('<<DragLeave>>', handle_drag_leave)


# Transcribe Button and Options
transcribe_options_frame = ttk.Frame(trans_frame)
transcribe_options_frame.pack(fill="x", pady=(5, 5))

transcribe_button = ttk.Button(
    transcribe_options_frame, text="Start Transcription", command=transcribe_audio,
    style='Accent.TButton' # Custom style for a more prominent button
)
transcribe_button.pack(side="left")

ttk.Checkbutton(transcribe_options_frame, text="Combine Full Transcripts into ONE file", variable=combine_output_var).pack(side="left", padx=15)

# Status and Progress
status_progress_frame = ttk.Frame(trans_frame)
status_progress_frame.pack(fill="x", pady=(0, 5))

status_label = ttk.Label(status_progress_frame, text="Select model and audio file(s)")
status_label.pack(side="left", padx=0, fill="x", expand=True)

eta_label = ttk.Label(status_progress_frame, textvariable=eta_display, width=15, anchor="e")
eta_label.pack(side="right", padx=5)

progress_bar = ttk.Progressbar(trans_frame, orient="horizontal", length=100, mode="determinate")
progress_bar.pack(fill="x", expand=True, padx=5, pady=(0, 5))

# Output Paths
output_paths_frame = ttk.Frame(trans_frame)
output_paths_frame.pack(fill="x", pady=(5, 0))

ttk.Label(output_paths_frame, text="Last/Combined Transcript:").grid(row=0, column=0, sticky="w", pady=2)
ttk.Entry(output_paths_frame, textvariable=full_transcript_path_display, state='readonly').grid(row=0, column=1, sticky="ew", padx=5, pady=2)

ttk.Label(output_paths_frame, text="Last Individual Segments File:").grid(row=1, column=0, sticky="w", pady=2)
ttk.Entry(output_paths_frame, textvariable=segments_path_display, state='readonly').grid(row=1, column=1, sticky="ew", padx=5, pady=2)

output_paths_frame.grid_columnconfigure(1, weight=1)


# === Segment Parser Frame ===
parse_frame = ttk.LabelFrame(root, text="3. Parse Individual Segments File (Optional)", padding=(10, 10))
parse_frame.pack(padx=10, pady=10, fill="x")

# Controls for parsing
parse_controls_frame = ttk.Frame(parse_frame)
parse_controls_frame.pack(fill="x", pady=(0, 5))

ttk.Label(parse_controls_frame, text="Merge if gap < (sec):").pack(side="left")
threshold_entry = ttk.Entry(parse_controls_frame, width=7)
threshold_entry.insert(0, "1.0")
threshold_entry.pack(side="left", padx=5)

ttk.Button(parse_controls_frame, text="Browse Segments File", command=browse_segments_file).pack(side="left", padx=(10, 5))
ttk.Button(parse_controls_frame, text="Parse Selected File", command=parse_segments).pack(side="left")

# Output paths for parsing
parse_output_paths_frame = ttk.Frame(parse_frame)
parse_output_paths_frame.pack(fill="x", pady=(5, 0))

ttk.Label(parse_output_paths_frame, text="Segments File to Parse:").grid(row=0, column=0, sticky="w", pady=2)
ttk.Entry(parse_output_paths_frame, textvariable=segments_file_path, state='readonly').grid(row=0, column=1, sticky="ew", padx=5, pady=2)

ttk.Label(parse_output_paths_frame, text="Parsed Output File:").grid(row=1, column=0, sticky="w", pady=2)
ttk.Entry(parse_output_paths_frame, textvariable=parsed_segments_path_display, state='readonly').grid(row=1, column=1, sticky="ew", padx=5, pady=2)

parse_output_paths_frame.grid_columnconfigure(1, weight=1)


# === Output Directory Button ===
ttk.Button(root, text="Open Output/Audio Directory", command=open_directory).pack(pady=10)

root.mainloop()