import os
import re
import time
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import sys

# Modern theming via ttkbootstrap (fallback gracefully if unavailable)
try:
    import ttkbootstrap as tb
    TTKB_AVAILABLE = True
except Exception:
    TTKB_AVAILABLE = False

# Optional drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False

import whisper


# ----------------------
# State
# ----------------------
selected_audio_files = []


# ----------------------
# Helpers
# ----------------------
def clear_output_displays():
    full_transcript_path_display.set("")
    segments_path_display.set("")
    parsed_segments_path_display.set("")
    segments_file_path.set("")


def open_directory():
    # Open the most relevant directory based on last outputs
    paths = [
        parsed_segments_path_display.get(),
        segments_path_display.get(),
        full_transcript_path_display.get(),
        selected_audio_files[0] if selected_audio_files else "",
    ]
    for p in paths:
        if p:
            directory = os.path.dirname(p) if os.path.isfile(p) else (p if os.path.isdir(p) else os.path.dirname(p))
            if directory and os.path.isdir(directory):
                try:
                    os.startfile(directory)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open directory: {e}")
                return
    messagebox.showinfo("Info", "No valid directory to open yet.")


def open_last_transcript():
    path = full_transcript_path_display.get()
    if not path:
        messagebox.showinfo("Open Transcript", "No transcript file to open yet.")
        return
    try:
        if os.path.isfile(path):
            os.startfile(path)
        else:
            messagebox.showwarning("Not Found", f"Transcript file not found:\n{path}")
    except Exception as e:
        messagebox.showerror("Open Error", f"Could not open file:\n{e}")


# ----------------------
# File selection
# ----------------------
def browse_multi_audio():
    global selected_audio_files
    paths = filedialog.askopenfilenames(
        title="Select Audio Files",
        filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")]
    )
    if paths:
        selected_audio_files = list(paths)
        refresh_audio_list()
        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        status_label.config(text=f"{len(selected_audio_files)} file(s) selected. Ready.")


def refresh_audio_list():
    audio_listbox.delete(0, tk.END)
    for p in selected_audio_files:
        audio_listbox.insert(tk.END, os.path.basename(p))
    update_list_actions_state()


def remove_selected_from_list():
    global selected_audio_files
    sel = list(audio_listbox.curselection())
    if not sel:
        return
    # Remove from end to start to keep indices stable
    for i in reversed(sel):
        del selected_audio_files[i]
    refresh_audio_list()
    status_label.config(text=f"{len(selected_audio_files)} file(s) remain.")


def clear_list():
    global selected_audio_files
    selected_audio_files = []
    refresh_audio_list()
    clear_output_displays()
    progress_bar['value'] = 0
    eta_display.set("ETA: N/A")
    status_label.config(text="No files selected.")


def update_list_actions_state():
    has_items = len(selected_audio_files) > 0
    remove_btn.config(state=tk.NORMAL if has_items else tk.DISABLED)
    clear_btn.config(state=tk.NORMAL if has_items else tk.DISABLED)


# ----------------------
# Transcription
# ----------------------
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
        time.sleep(0.2)

        combined_transcript_text = ""
        processed_files_count = 0
        error_files = []
        last_individual_segments_path = ""
        total_files = len(selected_audio_files)

        for i, audio_file in enumerate(selected_audio_files):
            current_filename = os.path.basename(audio_file)
            status_label.config(text=f"Transcribing {i+1}/{total_files}: {current_filename}...")
            progress_bar['value'] = i
            root.update()

            if i > 0:
                elapsed_time = time.time() - start_time_transcription_total
                avg_time = elapsed_time / i
                remaining = total_files - i
                eta_sec = max(0, int(avg_time * remaining))
                eta_display.set(f"ETA: {eta_sec//60:02d}:{eta_sec%60:02d}")
            elif total_files > 1:
                eta_display.set("ETA: Processing first…")

            try:
                result = model.transcribe(audio_file, fp16=False)

                output_dir = os.path.dirname(audio_file)
                base = os.path.splitext(current_filename)[0]
                transcript_path = os.path.join(output_dir, f"{base}_full_transcript.txt")
                segments_path = os.path.join(output_dir, f"{base}_segments.txt")

                try:
                    ctime = os.path.getctime(audio_file)
                    formatted_dt = datetime.datetime.fromtimestamp(ctime).strftime("%d %b %Y, %H:%M:%S")
                except Exception:
                    formatted_dt = "Unknown Time"

                header = f"===== Transcription for: {current_filename}  Datetime: {formatted_dt} =====\n\n"

                if combine_output:
                    if combined_transcript_text:
                        combined_transcript_text += f"\n\n{header}"
                    else:
                        combined_transcript_text += header
                    combined_transcript_text += result.get("text", "")
                else:
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(header)
                        f.write(result.get("text", ""))
                    full_transcript_path_display.set(transcript_path)

                with open(segments_path, "w", encoding="utf-8") as f:
                    for seg in result.get("segments", []):
                        start = round(seg.get('start', 0.0), 2)
                        end = round(seg.get('end', 0.0), 2)
                        text = (seg.get('text') or "").strip()
                        f.write(f"[{start:.2f} - {end:.2f}] {text}\n")
                last_individual_segments_path = segments_path
                segments_path_display.set(last_individual_segments_path)
                processed_files_count += 1

            except Exception as e:
                error_files.append(f"{current_filename}: {e}")
                status_label.config(text=f"Error on file {i+1}: {current_filename}. Skipping.")
                time.sleep(0.3)

            progress_bar['value'] = i + 1
            root.update()

        final_message = ""
        if combine_output and combined_transcript_text:
            save_path = filedialog.asksaveasfilename(
                title="Save Combined Transcript As",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt")],
                initialfile="combined_transcript.txt",
                initialdir=os.path.dirname(selected_audio_files[0]) if selected_audio_files else None,
            )
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(combined_transcript_text)
                    full_transcript_path_display.set(save_path)
                    final_message += f"Combined transcript saved to:\n{save_path}\n\n"
                except Exception as e:
                    msg = f"Error saving combined transcript to {save_path}: {e}"
                    final_message += msg + "\n\n"
                    messagebox.showerror("Save Error", msg)
            else:
                final_message += "Combined transcript saving cancelled by user.\n\n"

        eta_display.set("ETA: Completed" if processed_files_count > 0 else "ETA: N/A")
        status_label.config(text="Transcription finished.")
        final_message += f"Processed {processed_files_count} of {total_files} file(s)."
        if not combine_output:
            final_message += "\nIndividual transcripts and segment files saved next to audio files."
        else:
            final_message += "\nIndividual segment files saved next to audio files."

        if error_files:
            final_message += f"\n\nErrors in {len(error_files)} file(s):\n" + "\n".join(error_files)
            messagebox.showwarning("Complete with Errors", final_message)
            if last_individual_segments_path:
                segments_file_path.set(last_individual_segments_path)
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


# ----------------------
# Segment parsing
# ----------------------
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


def parse_segments():
    selected_segments_file = segments_file_path.get()
    if not selected_segments_file:
        messagebox.showerror("Error", "Please select a segments text file first.")
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
            if not line:
                continue
            m = pattern.match(line)
            if m:
                try:
                    start = float(m.group(1))
                    end = float(m.group(2))
                    text = m.group(3).strip()
                    if start > end:
                        continue
                    segments.append({"start": start, "end": end, "text": text})
                except ValueError:
                    continue

        if not segments:
            messagebox.showwarning("Parsing Warning", "No valid segments found in the selected file.")
            return

        merged = []
        current = segments[0].copy()
        for nxt in segments[1:]:
            gap = nxt["start"] - current["end"]
            if 0 <= gap < threshold:
                current["end"] = nxt["end"]
                current["text"] = (current["text"] + (" " if current["text"] else "") + nxt["text"]).strip()
            else:
                merged.append(current)
                current = nxt.copy()
        merged.append(current)

        input_dir = os.path.dirname(selected_segments_file)
        input_base = os.path.splitext(os.path.basename(selected_segments_file))[0]
        if input_base.endswith("_segments"):
            parsed_name = input_base.replace("_segments", f"_parsed_segments_t{threshold}.txt")
        else:
            parsed_name = f"{input_base}_parsed_t{threshold}.txt"

        parsed_path = os.path.join(input_dir, parsed_name)
        with open(parsed_path, "w", encoding="utf-8") as f:
            for seg in merged:
                s = round(seg['start'], 2)
                e = round(seg['end'], 2)
                f.write(f"[{s:.2f} - {e:.2f}] {seg['text']}\n")

        parsed_segments_path_display.set(parsed_path)
        messagebox.showinfo("Success", f"Parsed segments saved to:\n{parsed_path}")

    except FileNotFoundError:
        messagebox.showerror("Error", f"File not found: {selected_segments_file}")
    except Exception as e:
        messagebox.showerror("Parsing Error", f"An error occurred during parsing: {e}")


# ----------------------
# Drag & drop handlers
# ----------------------
def handle_drag_enter(event):
    if TKDND_AVAILABLE:
        listbox_frame.config(bg="#eaf7ff")
        drop_label.config(bg="#eaf7ff", fg="#004a77", text="Drop Audio Files Here")


def handle_drag_leave(event):
    if TKDND_AVAILABLE:
        listbox_frame.config(bg=default_drop_bg)
        drop_label.config(bg=default_drop_bg, fg="#666666", text="Drag & Drop Audio Files Here")


def handle_drop_files(event):
    global selected_audio_files
    if not TKDND_AVAILABLE:
        return

    handle_drag_leave(event)
    data = event.data
    if not data:
        return

    # Support {path with spaces} path_without_spaces format
    candidates = re.findall(r'\{.*?\}|\S+', data)
    parsed_paths = [(c[1:-1] if c.startswith('{') and c.endswith('}') else c) for c in candidates]

    valid_audio = []
    valid_ext = ('.mp3', '.wav', '.m4a')
    for p in parsed_paths:
        clean = p.strip('\"')
        if os.path.isfile(clean) and clean.lower().endswith(valid_ext):
            valid_audio.append(clean)

    if valid_audio:
        selected_audio_files = valid_audio
        refresh_audio_list()
        clear_output_displays()
        progress_bar['value'] = 0
        eta_display.set("ETA: N/A")
        status_label.config(text=f"{len(selected_audio_files)} file(s) dropped. Ready.")


# ----------------------
# UI
# ----------------------
if TKDND_AVAILABLE:
    root = TkinterDnD.Tk()
else:
    root = tk.Tk()

root.title("Whisper Transcriber")

# Improve default look with ttkbootstrap (if present) or a nicer ttk theme
if 'TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE:
    # Choose a modern dark theme by default; users can change later
    style = tb.Style(theme='darkly')
else:
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except Exception:
        pass

# Variables
model_size = tk.StringVar(value="large")  # Default to largest model
combine_output_var = tk.BooleanVar(value=False)
segments_file_path = tk.StringVar()
full_transcript_path_display = tk.StringVar()
segments_path_display = tk.StringVar()
parsed_segments_path_display = tk.StringVar()
eta_display = tk.StringVar(value="ETA: N/A")


# Top-level layout
container = ttk.Frame(root, padding=10)
container.pack(fill="both", expand=True)

# Basic menubar with Help -> Open User Guide (PDF)
# Basic menubar with Help -> Open User Guide (PDF)
menubar = tk.Menu(root)
help_menu = tk.Menu(menubar, tearoff=0)

def resource_path(rel_path: str) -> str:
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)

def open_user_guide():
    try:
        pdf_path = resource_path(os.path.join('docs', 'Whisper_Transcriber_User_Guide.pdf'))
        md_path = resource_path(os.path.join('docs', 'user_guide.md'))
        if os.path.isfile(pdf_path):
            os.startfile(pdf_path)
        elif os.path.isfile(md_path):
            os.startfile(md_path)
        else:
            messagebox.showinfo("User Guide", "Guide not found yet. Please run the guide builder or check the repo README.")
    except Exception as e:
        messagebox.showerror("Open Guide Error", f"Could not open user guide: {e}")

help_menu.add_command(label="Open User Guide", command=open_user_guide)
menubar.add_cascade(label="Help", menu=help_menu)
root.config(menu=menubar)

# Section: Model
model_frame = ttk.LabelFrame(container, text="1. Model", padding=10)
model_frame.pack(fill="x")

ttk.Label(model_frame, text="Whisper model:").pack(side="left")
model_combo = ttk.Combobox(
    model_frame,
    textvariable=model_size,
    state="readonly",
    values=["tiny", "base", "small", "medium", "large"],
    width=12,
)
model_combo.pack(side="left", padx=8)
ttk.Label(model_frame, text="Default is 'large' for best accuracy.").pack(side="left")

# Optional theme switcher when ttkbootstrap is available
def _switch_theme(event=None):
    if not ('TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE):
        messagebox.showinfo("Theme", "Advanced themes require ttkbootstrap to be installed.")
        return
    chosen = theme_combo.get()
    try:
        style.theme_use(chosen)
    except Exception as e:
        messagebox.showerror("Theme Error", f"Could not switch theme: {e}")

if 'TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE:
    ttk.Label(model_frame, text="Theme:").pack(side="left", padx=(16, 0))
    theme_combo = ttk.Combobox(
        model_frame,
        state="readonly",
        width=12,
        values=style.theme_names(),
    )
    try:
        # Reflect current theme name if available
        theme_combo.set(style.theme.name)
    except Exception:
        theme_combo.set('darkly')
    theme_combo.pack(side="left", padx=6)
    theme_combo.bind("<<ComboboxSelected>>", _switch_theme)

    # Quick presets for common requests
    def _set_dark():
        try:
            style.theme_use('darkly')
            theme_combo.set('darkly')
        except Exception:
            pass
    def _set_blue():
        try:
            # Flatly is a nice blue-accent theme
            style.theme_use('flatly')
            theme_combo.set('flatly')
        except Exception:
            pass
    ttk.Button(model_frame, text="Dark", command=_set_dark).pack(side="left", padx=(8, 2))
    ttk.Button(model_frame, text="Blue", command=_set_blue).pack(side="left", padx=(2, 0))
else:
    ttk.Label(model_frame, text="Install 'ttkbootstrap' for modern dark/blue themes.", foreground="#555").pack(side="left", padx=(16, 0))



# Basic dark palette fallback if ttkbootstrap is unavailable
if not ('TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE):
    try:
        root.configure(bg='#1e1e1e')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabelframe', background='#1e1e1e', foreground='#e6e6e6')
        style.configure('TLabelframe.Label', background='#1e1e1e', foreground='#e6e6e6')
        style.configure('TLabel', background='#1e1e1e', foreground='#e6e6e6')
        style.configure('TButton', foreground='#e6e6e6')
        style.map('TButton', foreground=[('active', '#ffffff')])
        style.configure('TCheckbutton', background='#1e1e1e', foreground='#e6e6e6')
    except Exception:
        pass# Section: Files
files_frame = ttk.LabelFrame(container, text="2. Audio Files", padding=10)
files_frame.pack(fill="both", expand=True, pady=(10, 0))

listbox_frame = tk.Frame(files_frame, bd=1, relief=tk.SOLID)
listbox_frame.pack(fill="both", expand=True)
default_drop_bg = listbox_frame.cget("bg")

drop_label = tk.Label(
    listbox_frame,
    text="Drag & Drop Audio Files Here",
    fg="#666666",
)
drop_label.pack(fill="x", padx=10, pady=(10, 4))

audio_listbox = tk.Listbox(listbox_frame, height=6, selectmode=tk.EXTENDED)
# Apply dark colors to Tk widgets when ttkbootstrap is unavailable
if not ('TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE):
    try:
        listbox_frame.configure(bg='#202020')
        drop_label.configure(bg='#202020', fg='#cfd8dc')
        audio_listbox.configure(bg='#111214', fg='#e6e6e6', selectbackground='#0d6efd')
        # Keep drag-leave background consistent with our override
        default_drop_bg = '#202020'
    except Exception:
        pass
audio_listbox.pack(fill="both", expand=True, padx=6, pady=(0, 6))

controls_frame = ttk.Frame(files_frame)
controls_frame.pack(fill="x")
ttk.Button(controls_frame, text="Browse…", command=browse_multi_audio).pack(side="left")
remove_btn = ttk.Button(controls_frame, text="Remove Selected", command=remove_selected_from_list)
remove_btn.pack(side="left", padx=6)
clear_btn = ttk.Button(controls_frame, text="Clear List", command=clear_list)
clear_btn.pack(side="left")

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


# Section: Transcribe
trans_frame = ttk.LabelFrame(container, text="3. Transcribe", padding=10)
trans_frame.pack(fill="x", pady=(10, 0))

row1 = ttk.Frame(trans_frame)
row1.pack(fill="x")
transcribe_btn = ttk.Button(row1, text="Transcribe Selected Files", command=transcribe_audio)
transcribe_btn.pack(side="left")
ttk.Checkbutton(row1, text="Combine full transcripts into one file", variable=combine_output_var).pack(side="left", padx=10)

row2 = ttk.Frame(trans_frame)
row2.pack(fill="x", pady=(8, 0))
status_label = ttk.Label(row2, text="Select model and audio file(s)")
status_label.pack(side="left")
eta_label = ttk.Label(row2, textvariable=eta_display)
eta_label.pack(side="right")

row3 = ttk.Frame(trans_frame)
row3.pack(fill="x", pady=(6, 0))
progress_bar = ttk.Progressbar(row3, orient="horizontal", mode="determinate")
progress_bar.pack(fill="x")

row4 = ttk.Frame(trans_frame)
row4.pack(fill="x", pady=(8, 0))
ttk.Label(row4, text="Last/Combined Transcript:").pack(side="left")
full_transcript_entry = ttk.Entry(row4, textvariable=full_transcript_path_display, state='readonly')
full_transcript_entry.pack(side="left", fill="x", expand=True, padx=6)
ttk.Button(row4, text="Open", command=open_last_transcript).pack(side="left")

row5 = ttk.Frame(trans_frame)
row5.pack(fill="x", pady=(4, 0))
ttk.Label(row5, text="Last Segments File:").pack(side="left")
segments_entry = ttk.Entry(row5, textvariable=segments_path_display, state='readonly')
segments_entry.pack(side="left", fill="x", expand=True, padx=6)


# Section: Segment Parser (Optional)
parse_frame = ttk.LabelFrame(container, text="4. Parse Segments (Optional)", padding=10)
parse_frame.pack(fill="x", pady=(10, 0))

prow1 = ttk.Frame(parse_frame)
prow1.pack(fill="x")
ttk.Label(prow1, text="Merge if gap < (sec):").pack(side="left")
threshold_entry = ttk.Entry(prow1, width=8)
threshold_entry.insert(0, "1.0")
threshold_entry.pack(side="left", padx=6)
ttk.Button(prow1, text="Browse Segments File", command=browse_segments_file).pack(side="left", padx=6)
ttk.Button(prow1, text="Parse Selected File", command=parse_segments).pack(side="left")

prow2 = ttk.Frame(parse_frame)
prow2.pack(fill="x", pady=(6, 0))
ttk.Label(prow2, text="Segments File:").pack(side="left")
segments_input_entry = ttk.Entry(prow2, textvariable=segments_file_path, state='readonly')
segments_input_entry.pack(side="left", fill="x", expand=True, padx=6)

prow3 = ttk.Frame(parse_frame)
prow3.pack(fill="x", pady=(4, 0))
ttk.Label(prow3, text="Parsed Output:").pack(side="left")
parsed_output_entry = ttk.Entry(prow3, textvariable=parsed_segments_path_display, state='readonly')
parsed_output_entry.pack(side="left", fill="x", expand=True, padx=6)


# Footer actions
footer = ttk.Frame(container)
footer.pack(fill="x", pady=10)
ttk.Button(footer, text="Open Output/Audio Directory", command=open_directory).pack(side="right")


# Initialize
def _init():
    refresh_audio_list()
    # Normalize Browse button label if mojibake occurred
    try:
        for w in controls_frame.winfo_children():
            try:
                if w.winfo_class() in ("TButton", "Button") and "Browse" in str(w.cget("text")):
                    w.config(text="Browse…")
                    break
            except Exception:
                pass
    except Exception:
        pass


_init()
root.mainloop()
