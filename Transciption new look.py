# modern_whisper_app.py

import os
import re
import threading
import subprocess
import platform
import time
import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox, Listbox, Scrollbar, END

# Use whisper-openai library
try:
    import whisper
except ImportError:
    messagebox.showerror("Whisper Not Found", "The 'whisper-openai' library is not installed.\nPlease run: pip install whisper-openai")
    exit()

# Import TkinterDnD for drag and drop functionality
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    print("WARNING: tkinterdnd2 library not found. Drag and drop will be disabled.")
    print("You can install it with: pip install tkinterdnd2")

# --- MAIN APPLICATION CLASS ---
class ModernWhisperApp(TkinterDnD.Tk if TKDND_AVAILABLE else ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Modern Whisper Transcriber & Parser")
        self.geometry("850x750")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- State Variables ---
        self.selected_audio_files = []
        self.model_size_var = ctk.StringVar(value="base")
        self.combine_output_var = ctk.BooleanVar(value=False)
        self.last_generated_segments_file = ctk.StringVar()
        self.is_processing = False

        # --- Layout Configuration ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Main content area
        self.grid_rowconfigure(1, weight=0) # Progress bar
        self.grid_rowconfigure(2, weight=1) # Log area

        # --- Create Log Textbox First ---
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(log_frame, state="disabled", wrap="word", font=("Courier New", 10))
        self.log_textbox.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # --- Create Widgets ---
        self.create_widgets()

    def create_widgets(self):
        # --- Main Tab View ---
        self.tab_view = ctk.CTkTabview(self, anchor="w")
        self.tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.tab_view.add("Transcription")
        self.tab_view.add("Segment Parser")
        
        # --- Transcription Tab ---
        self.create_transcription_tab()

        # --- Segment Parser Tab ---
        self.create_parser_tab()

        # --- Progress & ETA Frame ---
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.eta_label = ctk.CTkLabel(progress_frame, text="ETA: N/A", width=100, anchor="e")
        self.eta_label.grid(row=0, column=1, padx=5, sticky="e")

    def create_transcription_tab(self):
        transcribe_tab = self.tab_view.tab("Transcription")
        transcribe_tab.grid_columnconfigure(0, weight=1)

        # File Selection Frame
        file_frame = ctk.CTkFrame(transcribe_tab)
        file_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        file_frame.grid_columnconfigure(0, weight=1)
        
        self.audio_listbox = Listbox(file_frame, height=6, bg="#2b2b2b", fg="white", selectbackground="#1f6aa5", relief="flat", borderwidth=0, highlightthickness=0)
        self.audio_listbox.grid(row=0, column=0, rowspan=3, padx=10, pady=10, sticky="nsew")
        
        self.browse_btn = ctk.CTkButton(file_frame, text="Browse Files", command=self.browse_multi_audio)
        self.browse_btn.grid(row=0, column=1, padx=10, pady=(10,5), sticky="ew")
        self.remove_btn = ctk.CTkButton(file_frame, text="Remove Selected", command=self.remove_selected_files)
        self.remove_btn.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        self.clear_btn = ctk.CTkButton(file_frame, text="Clear All", command=self.clear_all_files)
        self.clear_btn.grid(row=2, column=1, padx=10, pady=(5,10), sticky="ew")
        
        # Drag and Drop Setup
        if TKDND_AVAILABLE:
            drop_target_widget = self.audio_listbox
            drop_target_widget.drop_target_register(DND_FILES)
            drop_target_widget.dnd_bind('<<Drop>>', self.handle_drop_files)
            self.log("Drag & Drop is enabled. Drop audio files onto the list.")

        # Options Frame
        options_frame = ctk.CTkFrame(transcribe_tab)
        options_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        options_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(options_frame, text="Whisper Model:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.model_menu = ctk.CTkOptionMenu(options_frame, variable=self.model_size_var, values=["tiny", "base", "small", "medium", "large"])
        self.model_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.combine_checkbox = ctk.CTkCheckBox(options_frame, text="Combine all transcripts into a single file", variable=self.combine_output_var)
        self.combine_checkbox.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="w")
        
        # Action Button
        self.transcribe_btn = ctk.CTkButton(transcribe_tab, text="Start Transcription", height=40, command=self.start_transcription)
        self.transcribe_btn.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
    
    def create_parser_tab(self):
        parser_tab = self.tab_view.tab("Segment Parser")
        parser_tab.grid_columnconfigure(1, weight=1)

        # Input File Frame
        parser_input_frame = ctk.CTkFrame(parser_tab)
        parser_input_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        parser_input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parser_input_frame, text="Segments File to Parse:").grid(row=0, column=0, padx=10, pady=10)
        self.parser_file_entry = ctk.CTkEntry(parser_input_frame, textvariable=self.last_generated_segments_file, state="readonly")
        self.parser_file_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.parser_browse_btn = ctk.CTkButton(parser_input_frame, text="Browse...", command=self.browse_segments_file)
        self.parser_browse_btn.grid(row=0, column=2, padx=10, pady=10)

        # Options Frame
        parser_options_frame = ctk.CTkFrame(parser_tab)
        parser_options_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(parser_options_frame, text="Merge segments if time gap is less than (seconds):").pack(side="left", padx=10, pady=10)
        self.threshold_entry = ctk.CTkEntry(parser_options_frame, width=80)
        self.threshold_entry.insert(0, "1.0")
        self.threshold_entry.pack(side="left", padx=10, pady=10)

        # Action Button
        self.parse_btn = ctk.CTkButton(parser_tab, text="Parse & Merge Segments", height=40, command=self.start_parsing)
        self.parse_btn.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    # --- UI State & Logging ---

    def set_ui_state(self, is_busy):
        self.is_processing = is_busy
        state = "disabled" if is_busy else "normal"
        self.browse_btn.configure(state=state)
        self.remove_btn.configure(state=state)
        self.clear_btn.configure(state=state)
        self.model_menu.configure(state=state)
        self.combine_checkbox.configure(state=state)
        self.transcribe_btn.configure(state=state)
        self.parser_browse_btn.configure(state=state)
        self.threshold_entry.configure(state=state)
        self.parse_btn.configure(state=state)
        
    def log(self, message):
        """ Appends a message to the log textbox in a thread-safe way. """
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    # --- File Management & Drag/Drop ---

    def update_file_list(self):
        self.audio_listbox.delete(0, END)
        for path in self.selected_audio_files:
            self.audio_listbox.insert(END, os.path.basename(path))
        self.log(f"Updated file list: {len(self.selected_audio_files)} file(s) loaded.")

    def browse_multi_audio(self):
        paths = filedialog.askopenfilenames(
            title="Select Audio Files",
            filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.flac *.ogg")]
        )
        if paths:
            self.selected_audio_files.extend(list(paths))
            self.selected_audio_files = sorted(list(set(self.selected_audio_files))) # Remove duplicates
            self.update_file_list()

    def remove_selected_files(self):
        selected_indices = self.audio_listbox.curselection()
        if not selected_indices:
            self.log("No files selected in the list to remove.")
            return
        
        # Remove from backend list by value, not index, to be safe
        selected_filenames = [self.audio_listbox.get(i) for i in selected_indices]
        self.selected_audio_files = [p for p in self.selected_audio_files if os.path.basename(p) not in selected_filenames]
        self.update_file_list()

    def clear_all_files(self):
        self.selected_audio_files.clear()
        self.update_file_list()

    def handle_drop_files(self, event):
        if not TKDND_AVAILABLE: return
        
        # Robustly parse paths from TkinterDnD's string format
        path_candidates = re.findall(r'\{.*?\}|\S+', event.data)
        parsed_paths = []
        for cand in path_candidates:
            parsed_paths.append(cand.strip('{}'))

        valid_extensions = ('.mp3', '.wav', '.m4a', '.flac', '.ogg')
        dropped_files = [p for p in parsed_paths if os.path.isfile(p) and p.lower().endswith(valid_extensions)]
        
        if dropped_files:
            self.selected_audio_files.extend(dropped_files)
            self.selected_audio_files = sorted(list(set(self.selected_audio_files))) # Remove duplicates
            self.update_file_list()

    # --- Core Functionality & Threading ---
    
    def start_transcription(self):
        if self.is_processing: return
        if not self.selected_audio_files:
            messagebox.showerror("Error", "Please select one or more audio files first.")
            return
        
        self.set_ui_state(is_busy=True)
        self.progress_bar.set(0)
        self.eta_label.configure(text="ETA: Starting...")
        self.log("--- Starting Transcription Process ---")
        
        threading.Thread(target=self._run_transcription_thread, daemon=True).start()

    def _run_transcription_thread(self):
        model_name = self.model_size_var.get()
        combine_output = self.combine_output_var.get()
        
        try:
            self.log(f"Loading Whisper model '{model_name}'. This may take a moment...")
            model = whisper.load_model(model_name)
            self.log(f"Model '{model_name}' loaded successfully.")

            total_files = len(self.selected_audio_files)
            combined_transcript_text = ""
            start_time = time.time()

            for i, audio_file in enumerate(self.selected_audio_files):
                filename = os.path.basename(audio_file)
                self.log(f"[{i+1}/{total_files}] Transcribing: {filename}")
                
                # ETA calculation
                if i > 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i
                    eta = avg_time * (total_files - i)
                    self.eta_label.configure(text=f"ETA: {int(eta // 60)}m {int(eta % 60)}s")

                result = model.transcribe(audio_file, fp16=False) # fp16=False for CPU
                
                # --- File Saving ---
                output_dir = os.path.dirname(audio_file)
                base_filename = os.path.splitext(filename)[0]
                
                # Use file's modification time for timestamp
                mod_time = os.path.getmtime(audio_file)
                dt_object = datetime.datetime.fromtimestamp(mod_time)
                header = f"===== {filename} | {dt_object.strftime('%Y-%m-%d %H:%M')} ====="
                
                # Save individual segments file regardless of combine option
                segments_path = os.path.join(output_dir, f"{base_filename}_segments.txt")
                with open(segments_path, "w", encoding="utf-8") as f:
                    for segment in result.get("segments", []):
                        f.write(f"[{segment['start']:.2f} - {segment['end']:.2f}] {segment['text'].strip()}\n")
                self.log(f"  -> Saved segments to: {segments_path}")
                self.last_generated_segments_file.set(segments_path) # Auto-populate for parser

                # Handle full transcript
                if combine_output:
                    combined_transcript_text += f"\n\n{header}\n{result['text'].strip()}"
                else:
                    transcript_path = os.path.join(output_dir, f"{base_filename}_transcript.txt")
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(f"{header}\n\n{result['text'].strip()}")
                    self.log(f"  -> Saved full transcript to: {transcript_path}")

                self.progress_bar.set((i + 1) / total_files)

            if combine_output and combined_transcript_text:
                first_file_dir = os.path.dirname(self.selected_audio_files[0])
                today_str = datetime.date.today().strftime('%Y-%m-%d')
                save_path = os.path.join(first_file_dir, f"Combined Transcript_{today_str}.txt")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(combined_transcript_text.strip())
                self.log(f"-> Saved combined transcript to: {save_path}")

            self.log("--- Transcription process finished successfully! ---")

        except Exception as e:
            self.log(f"ERROR: An error occurred during transcription: {e}")
            messagebox.showerror("Transcription Error", str(e))
        finally:
            self.set_ui_state(is_busy=False)
            self.eta_label.configure(text="ETA: Done")

    def browse_segments_file(self):
        path = filedialog.askopenfilename(
            title="Select Segments File to Parse",
            filetypes=[("Text Files", "*.txt")]
        )
        if path:
            self.last_generated_segments_file.set(path)

    def start_parsing(self):
        if self.is_processing: return
        
        file_to_parse = self.last_generated_segments_file.get()
        if not file_to_parse or not os.path.exists(file_to_parse):
            messagebox.showerror("Error", "Please select a valid segments file to parse.")
            return
        
        try:
            threshold = float(self.threshold_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid threshold. Please enter a number (e.g., 1.0).")
            return
            
        self.set_ui_state(is_busy=True)
        self.log(f"--- Starting Segment Parsing for {os.path.basename(file_to_parse)} ---")
        
        threading.Thread(target=self._run_parsing_thread, args=(file_to_parse, threshold), daemon=True).start()

    def _run_parsing_thread(self, filepath, threshold):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            pattern = re.compile(r"\[\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*\]\s*(.*)")
            segments = []
            for line in lines:
                match = pattern.match(line.strip())
                if match:
                    segments.append({
                        "start": float(match.group(1)),
                        "end": float(match.group(2)),
                        "text": match.group(3).strip()
                    })
            
            if not segments:
                self.log("No valid segments found in the file.")
                return

            # Merge logic
            merged = []
            if segments:
                current_segment = segments[0].copy()
                for next_segment in segments[1:]:
                    if 0 <= (next_segment["start"] - current_segment["end"]) < threshold:
                        current_segment["end"] = next_segment["end"]
                        current_segment["text"] += " " + next_segment["text"]
                    else:
                        merged.append(current_segment)
                        current_segment = next_segment.copy()
                merged.append(current_segment)
            
            # Save parsed file
            input_dir = os.path.dirname(filepath)
            base = os.path.splitext(os.path.basename(filepath))[0]
            output_filename = f"{base.replace('_segments', '')}_parsed_t{threshold}.txt"
            output_path = os.path.join(input_dir, output_filename)

            with open(output_path, "w", encoding="utf-8") as f:
                for seg in merged:
                    f.write(f"[{seg['start']:.2f} - {seg['end']:.2f}] {seg['text']}\n")
            
            self.log(f"Successfully parsed segments.")
            self.log(f"-> Saved merged file to: {output_path}")

        except Exception as e:
            self.log(f"ERROR: An error occurred during parsing: {e}")
            messagebox.showerror("Parsing Error", str(e))
        finally:
            self.set_ui_state(is_busy=False)


if __name__ == "__main__":
    app = ModernWhisperApp()
    app.mainloop()