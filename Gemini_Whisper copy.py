# Gemini_Whisper.py
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Listbox, Scrollbar, BooleanVar, END, MULTIPLE, ttk
import whisper
import subprocess
import platform
import time # For status updates
import datetime # Added for date operations
# from datetime import date # Not strictly needed as datetime.date is used

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

# Directory for "Convert today's drive" feature
TARGET_VOICE_RECORDINGS_DIR = r"G:\My Drive\Voice Recordings" # Use raw string for Windows paths

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
    elif os.path.isdir(TARGET_VOICE_RECORDINGS_DIR):
        dir_to_open = TARGET_VOICE_RECORDINGS_DIR

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
def transcribe_audio(custom_combined_save_path=None):
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
        start_time_transcription_total = time.time() # For ETA calculation
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
            progress_bar['value'] = i # Progress before starting current file
            root.update()

            # Calculate and update ETA
            if i > 0:
                elapsed_time = time.time() - start_time_transcription_total
                avg_time_per_file = elapsed_time / i
                remaining_files = total_files - i
                eta_seconds_val = avg_time_per_file * remaining_files
                eta_minutes = int(eta_seconds_val // 60)
                eta_seconds_display = int(eta_seconds_val % 60)
                eta_display.set(f"ETA: {eta_minutes:02d}:{eta_seconds_display:02d}")
            elif i == 0 and total_files > 1: # For the first file if multiple exist
                eta_display.set(f"ETA: Processing first...")


            root.update() # Ensure ETA is displayed before potential long operation

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
                    formatted_datetime = creation_datetime.strftime("%d %b %Y, %H:%M:%S") # Using %b for abbreviated month
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
            
            # Update progress bar after current file is processed (or attempted)
            progress_bar['value'] = i + 1
            root.update()


        final_message = ""
        if combine_output:
            if combined_transcript_text:
                resolved_combined_save_path = custom_combined_save_path
                user_action_needed_for_save = False

                if not resolved_combined_save_path:
                    user_action_needed_for_save = True
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
                        if custom_combined_save_path:
                             final_message += f"Combined transcript automatically saved to:\n{resolved_combined_save_path}\n\n"
                        else:
                             final_message += f"Combined transcript saved to:\n{resolved_combined_save_path}\n\n"
                        full_transcript_path_display.set(resolved_combined_save_path)
                    except Exception as e:
                        error_msg = f"Error saving combined transcript to {resolved_combined_save_path}: {e}"
                        final_message += error_msg + "\n\n"
                        messagebox.showerror("Save Error", error_msg)
                elif user_action_needed_for_save:
                    final_message += "Combined transcript saving cancelled by user.\n\n"
            else:
                 final_message += "No successful transcriptions to combine.\n\n"

        progress_bar['value'] = total_files # Ensure it's full
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


# Common function for "Convert today's drive" with model selection
def convert_todays_drive_action(selected_model_size="large"):
    global selected_audio_files

    status_label.config(text=f"Scanning {TARGET_VOICE_RECORDINGS_DIR}...")
    progress_bar['value'] = 0
    eta_display.set("ETA: N/A")
    root.update()

    if not os.path.isdir(TARGET_VOICE_RECORDINGS_DIR):
        messagebox.showerror("Error", f"Directory not found: {TARGET_VOICE_RECORDINGS_DIR}")
        status_label.config(text=f"Error: Target directory '{TARGET_VOICE_RECORDINGS_DIR}' not found.")
        return

    today_date_obj = datetime.date.today()
    found_files_for_today = []
    file_pattern = re.compile(r"Recording (\d+)\.wav$", re.IGNORECASE)

    try:
        for filename in os.listdir(TARGET_VOICE_RECORDINGS_DIR):
            match = file_pattern.match(filename)
            if match:
                file_path = os.path.join(TARGET_VOICE_RECORDINGS_DIR, filename)
                try:
                    file_mod_time = os.path.getmtime(file_path)
                    file_mod_date = datetime.date.fromtimestamp(file_mod_time)
                    if file_mod_date == today_date_obj:
                        recording_number = int(match.group(1))
                        found_files_for_today.append((recording_number, file_path))
                except ValueError:
                    print(f"Warning: Could not parse recording number from {filename}")
                except Exception as e:
                    print(f"Warning: Could not process file {filename}: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"Error reading directory {TARGET_VOICE_RECORDINGS_DIR}: {e}")
        status_label.config(text="Error: Could not read target directory.")
        return

    if not found_files_for_today:
        messagebox.showinfo("Info", f"No recordings matching 'Recording <number>.wav' found for today ({today_date_obj.strftime('%Y-%m-%d')}) in {TARGET_VOICE_RECORDINGS_DIR}.")
        status_label.config(text="No recordings found for today.")
        selected_audio_files.clear()
        audio_listbox.delete(0, END)
        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        return

    found_files_for_today.sort(key=lambda x: x[0])
    selected_audio_files = [path for _, path in found_files_for_today]

    audio_listbox.delete(0, END)
    for path in selected_audio_files:
        audio_listbox.insert(END, os.path.basename(path))
    clear_output_displays()
    progress_bar['value'] = 0
    eta_display.set("ETA: N/A")

    status_label.config(text=f"Found {len(selected_audio_files)} recordings. Setting up for transcription with {selected_model_size} model...")
    root.update()

    model_size.set(selected_model_size)
    combine_output_var.set(True)
    output_filename = f"{today_date_obj.strftime('%Y-%m-%d')} transcription combined ({selected_model_size}).txt"
    target_combined_save_path = os.path.join(TARGET_VOICE_RECORDINGS_DIR, output_filename)

    transcribe_audio(custom_combined_save_path=target_combined_save_path)

    selected_audio_files.clear()
    audio_listbox.delete(0, END)


# Function for "Convert today's drive" with large model
def convert_todays_drive_large():
    convert_todays_drive_action(selected_model_size="large")

# Function for "Convert today's drive" with medium model
def convert_todays_drive_medium():
    convert_todays_drive_action(selected_model_size="medium")


# Function to browse and select a SINGLE segments text file for parsing
def browse_segments_file():
    initial_dir = None
    if segments_path_display.get():
        initial_dir = os.path.dirname(segments_path_display.get())
    elif selected_audio_files:
         initial_dir = os.path.dirname(selected_audio_files[0])
    elif os.path.isdir(TARGET_VOICE_RECORDINGS_DIR):
        initial_dir = TARGET_VOICE_RECORDINGS_DIR

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
        # Check if the mouse is leaving the drop_label to go to listbox_frame or vice-versa
        # This check prevents flickering if the drag moves between elements within the drop zone.
        # A simpler approach is to just reset, as TkinterDnD might re-trigger enter quickly.
        listbox_frame.config(bg="#f0f0f0")
        drop_label.config(bg="#f0f0f0", fg="#666666", text="Drag & Drop Audio Files Here")

def handle_drop_files(event):
    global selected_audio_files
    if not TKDND_AVAILABLE:
        return

    handle_drag_leave(event) # Reset appearance

    dropped_data_string = event.data
    if not dropped_data_string:
        return

    # Robustly parse paths from TkinterDnD's string format
    # Format can be: {path with spaces} path_without_spaces {another path with spaces}
    path_candidates = re.findall(r'\{.*?\}|\S+', dropped_data_string)
    
    parsed_paths = []
    for cand in path_candidates:
        if cand.startswith('{') and cand.endswith('}'):
            parsed_paths.append(cand[1:-1]) # Remove braces
        else:
            parsed_paths.append(cand)

    valid_audio_files = []
    valid_extensions = ('.mp3', '.wav', '.m4a')
    for path_str in parsed_paths:
        # Clean path (e.g., remove potential surrounding quotes if any OS/app adds them)
        clean_path = path_str.strip('\'"')
        if os.path.isfile(clean_path) and clean_path.lower().endswith(valid_extensions):
            valid_audio_files.append(clean_path)
        else:
            print(f"Skipping invalid or non-audio file from drop: {path_str}")
    
    if valid_audio_files:
        selected_audio_files = valid_audio_files # Replace current selection with dropped files
        audio_listbox.delete(0, END)
        for path in selected_audio_files:
            audio_listbox.insert(END, os.path.basename(path))
        
        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        status_label.config(text=f"{len(selected_audio_files)} file(s) dropped. Ready.")
    elif dropped_data_string: # Data was dropped, but no valid files found
        status_label.config(text="No valid audio files found in dropped items.")
        # Optionally clear list if no valid files and user expects replacement
        # selected_audio_files.clear()
        # audio_listbox.delete(0, END)

# --- GUI Setup ---
if TKDND_AVAILABLE:
    root = TkinterDnD.Tk()
else:
    root = tk.Tk()

root.title("Gemini Whisper: Multi-Transcription & Segment Parser")

# Variables
model_size = tk.StringVar(value="base")
combine_output_var = BooleanVar(value=False)
segments_file_path = tk.StringVar()
full_transcript_path_display = tk.StringVar()
segments_path_display = tk.StringVar()
parsed_segments_path_display = tk.StringVar()
eta_display = tk.StringVar(value="ETA: N/A")


# === Model Selection Frame ===
model_frame = tk.LabelFrame(root, text="1. Select Whisper Model Size", padx=10, pady=10)
model_frame.pack(padx=10, pady=5, fill="x")
tk.Radiobutton(model_frame, text="Tiny", variable=model_size, value="tiny").pack(anchor="w")
tk.Radiobutton(model_frame, text="Base", variable=model_size, value="base").pack(anchor="w")
tk.Radiobutton(model_frame, text="Small", variable=model_size, value="small").pack(anchor="w")
tk.Radiobutton(model_frame, text="Medium", variable=model_size, value="medium").pack(anchor="w")
tk.Radiobutton(model_frame, text="Large (Slowest, Accurate)", variable=model_size, value="large").pack(anchor="w")

# === Transcription Frame ===
trans_frame = tk.LabelFrame(root, text="2. Manual Transcription", padx=10, pady=10)
trans_frame.pack(padx=10, pady=10, fill="x")

row1_trans = tk.Frame(trans_frame)
row1_trans.pack(fill="x", pady=(0, 5))
tk.Button(row1_trans, text="Browse Audio Files", command=browse_multi_audio).pack(side="left")

listbox_frame = tk.Frame(row1_trans, bd=2, relief=tk.GROOVE, bg="#f0f0f0") # Initial bg color
listbox_frame.pack(side="left", fill="x", expand=True, padx=10)

drop_label = tk.Label(listbox_frame, text="Drag & Drop Audio Files Here", bg="#f0f0f0", fg="#666666") # Initial bg color
drop_label.pack(fill="x", pady=(2, 0))

audio_scrollbar = Scrollbar(listbox_frame, orient="vertical")
audio_listbox = Listbox(listbox_frame, height=4, width=50, yscrollcommand=audio_scrollbar.set, selectmode=MULTIPLE)
audio_scrollbar.config(command=audio_listbox.yview)
audio_scrollbar.pack(side="right", fill="y")
audio_listbox.pack(side="left", fill="x", expand=True, pady=(0, 2))

if TKDND_AVAILABLE:
    # Registering the whole listbox_frame as a primary drop target can be smoother
    listbox_frame.drop_target_register(DND_FILES)
    listbox_frame.dnd_bind('<<Drop>>', handle_drop_files)
    listbox_frame.dnd_bind('<<DragEnter>>', handle_drag_enter)
    listbox_frame.dnd_bind('<<DragLeave>>', handle_drag_leave)
    
    # Also bind to sub-widgets if direct drops on them are expected or to help with visual cues
    drop_label.drop_target_register(DND_FILES) # Allow drop on label itself
    drop_label.dnd_bind('<<Drop>>', handle_drop_files)
    drop_label.dnd_bind('<<DragEnter>>', handle_drag_enter) # Propagate visual cue
    drop_label.dnd_bind('<<DragLeave>>', handle_drag_leave)

    audio_listbox.drop_target_register(DND_FILES) # Allow drop on listbox itself
    audio_listbox.dnd_bind('<<Drop>>', handle_drop_files)
    audio_listbox.dnd_bind('<<DragEnter>>', handle_drag_enter) # Propagate visual cue
    audio_listbox.dnd_bind('<<DragLeave>>', handle_drag_leave)


row2_trans = tk.Frame(trans_frame)
row2_trans.pack(fill="x", pady=(5, 5))
bold_font = ('Helvetica', 10, 'bold')
transcribe_button = tk.Button(
    row2_trans, text="Transcribe Selected Files", command=lambda: transcribe_audio(None),
    bg="lightgreen", font=bold_font, relief=tk.RAISED, borderwidth=2
)
transcribe_button.pack(side="left")
tk.Checkbutton(row2_trans, text="Combine Full Transcripts into ONE file", variable=combine_output_var).pack(side="left", padx=15)

row3_trans = tk.Frame(trans_frame)
row3_trans.pack(fill="x", pady=(0, 5))
status_label = tk.Label(row3_trans, text="Select model and audio file(s)")
status_label.pack(side="left", padx=0)
eta_label = tk.Label(row3_trans, textvariable=eta_display, width=20, anchor="e") # Anchor east
eta_label.pack(side="right", padx=5)

row3b_trans = tk.Frame(trans_frame)
row3b_trans.pack(fill="x", pady=(0, 5))
progress_bar = ttk.Progressbar(row3b_trans, orient="horizontal", length=100, mode="determinate")
progress_bar.pack(fill="x", expand=True, padx=5)

row4_trans = tk.Frame(trans_frame)
row4_trans.pack(fill="x", pady=(5, 0))
tk.Label(row4_trans, text="Last/Combined Transcript:", width=22, anchor='w').pack(side="left")
full_transcript_display_entry = tk.Entry(row4_trans, textvariable=full_transcript_path_display, state='readonly', width=60)
full_transcript_display_entry.pack(side="left", fill="x", expand=True, padx=5)

row5_trans = tk.Frame(trans_frame)
row5_trans.pack(fill="x")
tk.Label(row5_trans, text="Last Individual Segments File:", width=22, anchor='w').pack(side="left")
segments_display_entry = tk.Entry(row5_trans, textvariable=segments_path_display, state='readonly', width=60)
segments_display_entry.pack(side="left", fill="x", expand=True, padx=5)

# === Automated Daily Drive Conversion Frame ===
drive_frame = tk.LabelFrame(root, text="Automated Daily Journaling (from G:\\My Drive\\Voice Recordings)", padx=10, pady=10)
drive_frame.pack(padx=10, pady=(5,10), fill="x")
buttons_frame = tk.Frame(drive_frame)
buttons_frame.pack(fill="x", pady=5)
tk.Button(buttons_frame, text="Convert Today's Drive (LARGE model)",
          command=convert_todays_drive_large,
          height=2, bg="lightblue", relief=tk.RAISED,
          borderwidth=2).pack(side="left", fill="x", expand=True, padx=(0,5))
tk.Button(buttons_frame, text="Convert Today's Drive (MEDIUM model)",
          command=convert_todays_drive_medium,
          height=2, bg="lightgreen", relief=tk.RAISED, # Changed color slightly for differentiation
          borderwidth=2).pack(side="left", fill="x", expand=True, padx=(5,0))


# === Segment Parser Frame ===
parse_frame = tk.LabelFrame(root, text="3. Parse Individual Segments File (Optional)", padx=10, pady=10)
parse_frame.pack(padx=10, pady=10, fill="x")

row1_parse = tk.Frame(parse_frame)
row1_parse.pack(fill="x", pady=(0, 5))
tk.Label(row1_parse, text="Merge if gap < (sec):").pack(side="left")
threshold_entry = tk.Entry(row1_parse, width=7)
threshold_entry.insert(0, "1.0")
threshold_entry.pack(side="left", padx=5)
tk.Button(row1_parse, text="Browse Segments File", command=browse_segments_file).pack(side="left", padx=10)
tk.Button(row1_parse, text="Parse Selected File", command=parse_segments).pack(side="left")

row2_parse = tk.Frame(parse_frame)
row2_parse.pack(fill="x", pady=(0, 5))
tk.Label(row2_parse, text="Segments File to Parse:", width=20, anchor='w').pack(side="left")
segments_input_display_entry = tk.Entry(row2_parse, textvariable=segments_file_path, state='readonly', width=60)
segments_input_display_entry.pack(side="left", fill="x", expand=True, padx=5)

row3_parse = tk.Frame(parse_frame)
row3_parse.pack(fill="x")
tk.Label(row3_parse, text="Parsed Output File:", width=20, anchor='w').pack(side="left")
parsed_segments_display_entry = tk.Entry(row3_parse, textvariable=parsed_segments_path_display, state='readonly', width=60)
parsed_segments_display_entry.pack(side="left", fill="x", expand=True, padx=5)


# === Output Directory Button ===
tk.Button(root, text="Open Output/Audio Directory", command=open_directory).pack(pady=10)

root.mainloop()