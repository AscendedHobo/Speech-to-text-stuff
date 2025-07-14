# modern_yt_downloader.py

import os
import re
import threading
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- CONFIGURATION ---
DEFAULT_OUTPUT_DIR = r"D:\YTDLP"  # Change this to your preferred default directory

# --- MAIN APPLICATION CLASS ---
class ModernDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Modern YT Downloader")
        self.geometry("800x650")
        ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
        ctk.set_default_color_theme("blue")

        # --- State Variables ---
        self.process = None
        self.downloaded_file = None
        self.out_dir_var = ctk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.playlist_var = ctk.BooleanVar()
        self.subs_var = ctk.BooleanVar()
        self.subs_only_var = ctk.BooleanVar()
        self.format_var = ctk.StringVar(value="MP4")

        # --- Create Widgets ---
        self.create_widgets()

    def create_widgets(self):
        # Use grid layout for the main window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Main Frame ---
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        main_frame.grid_columnconfigure(1, weight=1)

        # URL Entry
        ctk.CTkLabel(main_frame, text="Video/Playlist URL:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.url_entry = ctk.CTkEntry(main_frame, placeholder_text="Enter URL here...")
        self.url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # --- Tab View for Settings and Log ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.tab_view.add("Settings")
        self.tab_view.add("Log")
        self.tab_view.set("Settings") # Start on the settings tab

        # --- Settings Tab ---
        settings_tab = self.tab_view.tab("Settings")
        settings_tab.grid_columnconfigure(0, weight=1)

        # Time Segment Frame
        time_frame = ctk.CTkFrame(settings_tab)
        time_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        time_frame.grid_columnconfigure((1, 3, 5), weight=1)
        ctk.CTkLabel(time_frame, text="Time Segment (Optional)").grid(row=0, column=0, columnspan=6, pady=(5, 10))
        # Start Time
        ctk.CTkLabel(time_frame, text="Start (HH:MM:SS):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.start_h = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.start_h.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.start_m = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.start_m.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.start_s = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.start_s.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        # End Time
        ctk.CTkLabel(time_frame, text="End   (HH:MM:SS):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.end_h = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.end_h.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.end_m = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.end_m.grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.end_s = ctk.CTkEntry(time_frame, width=40, placeholder_text="00")
        self.end_s.grid(row=2, column=3, padx=5, pady=5, sticky="w")

        # Options & Format Frame
        opts_fmt_frame = ctk.CTkFrame(settings_tab)
        opts_fmt_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        opts_fmt_frame.grid_columnconfigure(1, weight=1)
        # Options
        ctk.CTkLabel(opts_fmt_frame, text="Options:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkCheckBox(opts_fmt_frame, text="Playlist", variable=self.playlist_var).grid(row=0, column=1, padx=5, sticky="w")
        ctk.CTkCheckBox(opts_fmt_frame, text="Download Subs", variable=self.subs_var).grid(row=0, column=2, padx=5, sticky="w")
        ctk.CTkCheckBox(opts_fmt_frame, text="Subs Only", variable=self.subs_only_var, command=self.toggle_format_options).grid(row=0, column=3, padx=5, sticky="w")
        # Format
        ctk.CTkLabel(opts_fmt_frame, text="Format:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.format_selector = ctk.CTkSegmentedButton(opts_fmt_frame, values=["MP4", "MP3"], variable=self.format_var)
        self.format_selector.grid(row=1, column=1, columnspan=3, padx=10, pady=10, sticky="w")

        # Output Directory
        out_dir_frame = ctk.CTkFrame(settings_tab)
        out_dir_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        out_dir_frame.grid_columnconfigure(0, weight=1)
        self.out_dir_label = ctk.CTkLabel(out_dir_frame, textvariable=self.out_dir_var, anchor="w")
        self.out_dir_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(out_dir_frame, text="Browse...", command=self.browse_out_dir).grid(row=0, column=1, padx=10, pady=10)

        # --- Log Tab ---
        log_tab = self.tab_view.tab("Log")
        self.log_textbox = ctk.CTkTextbox(log_tab, state="disabled", wrap="word")
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Progress Bar and ETA ---
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        self.eta_label = ctk.CTkLabel(progress_frame, text="ETA: N/A")
        self.eta_label.grid(row=0, column=1, padx=5, sticky="e")
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=2, padx=5, pady=(0, 5), sticky="ew")
        
        # --- Control Buttons ---
        ctrl_frame = ctk.CTkFrame(self)
        ctrl_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        self.download_btn = ctk.CTkButton(ctrl_frame, text="Download", command=self.start_download)
        self.download_btn.pack(side="left", padx=5, pady=5)
        self.cancel_btn = ctk.CTkButton(ctrl_frame, text="Cancel", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=5, pady=5)
        self.update_btn = ctk.CTkButton(ctrl_frame, text="Update yt-dlp", command=self.update_yt_dlp)
        self.update_btn.pack(side="left", padx=5, pady=5)
        self.open_file_btn = ctk.CTkButton(ctrl_frame, text="Launch File", command=self.open_file, state="disabled")
        self.open_file_btn.pack(side="right", padx=5, pady=5)
        self.open_dir_btn = ctk.CTkButton(ctrl_frame, text="Open Directory", command=self.open_directory, state="disabled")
        self.open_dir_btn.pack(side="right", padx=5, pady=5)

    def log(self, message):
        """ Appends a message to the log textbox in a thread-safe way. """
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def browse_out_dir(self):
        folder = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if folder:
            self.out_dir_var.set(folder)

    def format_time(self, h, m, s):
        """ Formats HH, MM, SS entries into a time string. Returns None if all are empty/zero. """
        h, m, s = h.strip(), m.strip(), s.strip()
        if not h and not m and not s:
            return None
        return f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}"

    def build_command(self):
        """ Constructs the yt-dlp command list from UI settings. """
        cmd = ["yt-dlp"]
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return None
        cmd.append(url)

        if self.subs_only_var.get():
            cmd.append("--skip-download")
        else: # Format logic only applies if we are not in "subs only" mode
            fmt = self.format_var.get().lower()
            if fmt == "mp3":
                cmd.extend(["-x", "--audio-format", "mp3"])
            else: # mp4
                # *** THIS IS THE FIX FOR THE FORMAT ERROR ***
                # More resilient format selection string.
                cmd.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"])

        start_time = self.format_time(self.start_h.get(), self.start_m.get(), self.start_s.get())
        end_time = self.format_time(self.end_h.get(), self.end_m.get(), self.end_s.get())
        if start_time or end_time:
            # yt-dlp is flexible: *start-end, *start-, *-end are all valid
            segment = f"*{start_time or ''}-{end_time or ''}"
            cmd.extend(["--download-sections", segment])

        cmd.append("--yes-playlist" if self.playlist_var.get() else "--no-playlist")

        if self.subs_var.get() or self.subs_only_var.get():
            cmd.extend(["--write-subs", "--write-auto-subs"])

        out_dir = self.out_dir_var.get()
        # Ensure output directory exists
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir)
                self.log(f"Created output directory: {out_dir}")
            except OSError as e:
                messagebox.showerror("Error", f"Could not create directory: {e}")
                return None
        
        # Use a safe and informative output template
        tmpl = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")
        cmd.extend(["-o", tmpl])
        return cmd

    def toggle_format_options(self):
        """ Disables or enables format selection based on 'Subs Only' checkbox. """
        if self.subs_only_var.get():
            self.format_selector.configure(state="disabled")
        else:
            self.format_selector.configure(state="normal")
            
    def set_ui_state(self, is_running):
        """ Helper to enable/disable UI elements during download. """
        state = "disabled" if is_running else "normal"
        cancel_state = "normal" if is_running else "disabled"

        self.download_btn.configure(state=state)
        self.update_btn.configure(state=state)
        self.url_entry.configure(state=state)
        self.cancel_btn.configure(state=cancel_state)
        # Keep directory button always available unless a download is running
        self.open_dir_btn.configure(state="normal" if not is_running and os.path.isdir(self.out_dir_var.get()) else "disabled")
        # File button is handled separately in run_command's finally block

    def start_download(self):
        cmd = self.build_command()
        if not cmd:
            return

        self.tab_view.set("Log") # Switch to log view
        self.log("Starting download...")
        self.log(f"Command: {' '.join(cmd)}")

        self.downloaded_file = None
        self.eta_label.configure(text="ETA: N/A")
        self.open_file_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.set_ui_state(is_running=True)
        
        threading.Thread(target=self.run_command, args=(cmd,), daemon=True).start()

    def run_command(self, cmd):
        try:
            # Use CREATE_NO_WINDOW flag on Windows to hide the console
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True, 
                encoding='utf-8',
                startupinfo=startupinfo
            )
            for line in self.process.stdout:
                line = line.strip()
                self.log(line) # Log everything for debugging
                
                if line.startswith("[download]"):
                    # Regex for progress percentage
                    pct_match = re.search(r'(\d+\.\d+)%', line)
                    if pct_match:
                        try:
                            progress_val = float(pct_match.group(1)) / 100.0
                            self.progress_bar.set(progress_val)
                        except ValueError:
                            pass
                    # Regex for ETA
                    eta_match = re.search(r'ETA\s+([\d:]+)', line)
                    if eta_match:
                        self.eta_label.configure(text=f"ETA: {eta_match.group(1)}")
                
                # Capture filename
                if not self.playlist_var.get():
                    dest_match = re.search(r"\[download\] Destination: (.*)", line)
                    final_file_match = re.search(r"\[Merger\] Merging formats into \"(.*)\"", line)
                    if dest_match:
                        self.downloaded_file = dest_match.group(1).strip()
                    if final_file_match:
                        self.downloaded_file = final_file_match.group(1).strip()

            self.process.wait()
            if self.process.returncode == 0:
                self.log("\n--- Download completed successfully! ---")
            else:
                self.log(f"\n--- Download finished with errors (code {self.process.returncode}). ---")
        except FileNotFoundError:
            self.log("\n*** ERROR: yt-dlp not found. Make sure it's in your system's PATH. ***")
            messagebox.showerror("Error", "yt-dlp executable not found. Please ensure it is installed and in your system's PATH.")
        except Exception as e:
            self.log(f"\n--- An unexpected error occurred: {e} ---")
        finally:
            self.process = None
            self.set_ui_state(is_running=False)
            self.progress_bar.set(0)
            self.eta_label.configure(text="ETA: N/A")
            if self.downloaded_file and os.path.exists(self.downloaded_file):
                self.open_file_btn.configure(state="normal")
            else:
                # If it was a playlist, we don't track a single file, but the dir button should work.
                self.open_file_btn.configure(state="disabled")

    def cancel_download(self):
        if self.process:
            self.log("\n--- Cancelling download... ---")
            self.process.terminate() # More forceful than kill

    def update_yt_dlp(self):
        self.tab_view.set("Log")
        self.log("--- Checking for yt-dlp updates... ---")
        self.set_ui_state(is_running=True) # Disable buttons during update
        threading.Thread(target=self.run_update, daemon=True).start()
        
    def run_update(self):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen(
                ["yt-dlp", "-U"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                startupinfo=startupinfo
            )
            for line in proc.stdout:
                self.log(line.strip())
            proc.wait()
            self.log("--- Update check finished. ---")
        except Exception as e:
            self.log(f"Error during update: {e}")
        finally:
            self.set_ui_state(is_running=False) # Re-enable buttons
        
    def open_directory(self):
        out_dir = self.out_dir_var.get()
        if os.path.isdir(out_dir):
            try:
                os.startfile(out_dir)
            except Exception as e:
                self.log(f"Error opening directory: {e}")
        else:
            self.log(f"Directory not found: {out_dir}")

    def open_file(self):
        if self.downloaded_file and os.path.isfile(self.downloaded_file):
            try:
                os.startfile(self.downloaded_file)
            except Exception as e:
                self.log(f"Error launching file: {e}")
        else:
            self.log("Downloaded file not found or path is incorrect.")
            messagebox.showwarning("Warning", "Could not find the downloaded file to launch.")

if __name__ == "__main__":
    app = ModernDownloaderApp()
    app.mainloop()