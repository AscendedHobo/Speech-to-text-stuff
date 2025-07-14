import os
import re
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT_OUTPUT_DIR = r"D:\YTDLP"

class SimpleDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple YT Downloader")
        self.process = None
        self.downloaded_file = None
        # No quality selection UI; always pick highest quality AV stream for MP4.
        self.create_widgets()
        
    def create_widgets(self):
        # URL Frame
        url_frame = ttk.LabelFrame(self.root, text="Video/Playlist URL")
        url_frame.pack(fill="x", padx=10, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=80)
        self.url_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        
        # Time Segment Frame (with separate HH, MM, SS boxes)
        time_frame = ttk.LabelFrame(self.root, text="Time Segment (Optional)")
        time_frame.pack(fill="x", padx=10, pady=5)
        # Start Time
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(start_frame, text="Start (HH MM SS):").pack(side="left")
        self.start_h = ttk.Entry(start_frame, width=3)
        self.start_h.pack(side="left", padx=(5,0))
        ttk.Label(start_frame, text=":").pack(side="left")
        self.start_m = ttk.Entry(start_frame, width=3)
        self.start_m.pack(side="left")
        ttk.Label(start_frame, text=":").pack(side="left")
        self.start_s = ttk.Entry(start_frame, width=3)
        self.start_s.pack(side="left")
        # End Time
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(end_frame, text="End   (HH MM SS):").pack(side="left")
        self.end_h = ttk.Entry(end_frame, width=3)
        self.end_h.pack(side="left", padx=(5,0))
        ttk.Label(end_frame, text=":").pack(side="left")
        self.end_m = ttk.Entry(end_frame, width=3)
        self.end_m.pack(side="left")
        ttk.Label(end_frame, text=":").pack(side="left")
        self.end_s = ttk.Entry(end_frame, width=3)
        self.end_s.pack(side="left")
        
        # Options Frame: only Playlist, Download Subs, Subs Only
        opts_frame = ttk.LabelFrame(self.root, text="Options")
        opts_frame.pack(fill="x", padx=10, pady=5)
        self.playlist_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Playlist", variable=self.playlist_var).pack(side="left", padx=5)
        self.subs_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Download Subs", variable=self.subs_var).pack(side="left", padx=5)
        self.subs_only_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Subs Only", variable=self.subs_only_var).pack(side="left", padx=5)
        
        # Format Selection: Radio buttons for MP4 or MP3
        fmt_frame = ttk.LabelFrame(self.root, text="Output Format")
        fmt_frame.pack(fill="x", padx=10, pady=5)
        self.format_var = tk.StringVar(value="mp4")
        ttk.Radiobutton(fmt_frame, text="MP4 (Video + Audio)", variable=self.format_var, value="mp4").pack(side="left", padx=10)
        ttk.Radiobutton(fmt_frame, text="MP3 (Audio Only)", variable=self.format_var, value="mp3").pack(side="left", padx=10)
        
        # Output Directory
        out_dir_frame = ttk.LabelFrame(self.root, text="Output Directory")
        out_dir_frame.pack(fill="x", padx=10, pady=5)
        self.out_dir_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        ttk.Label(out_dir_frame, textvariable=self.out_dir_var).pack(side="left", padx=5)
        ttk.Button(out_dir_frame, text="Browse...", command=self.browse_out_dir).pack(side="left", padx=5)
        
        # Control Buttons
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        self.download_btn = ttk.Button(ctrl_frame, text="Download", command=self.start_download)
        self.download_btn.pack(side="left", padx=5)
        self.cancel_btn = ttk.Button(ctrl_frame, text="Cancel", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)
        self.update_btn = ttk.Button(ctrl_frame, text="Update yt-dlp", command=self.update_yt_dlp)
        self.update_btn.pack(side="left", padx=5)
        self.open_dir_btn = ttk.Button(ctrl_frame, text="Open Directory", command=self.open_directory, state="disabled")
        self.open_dir_btn.pack(side="left", padx=5)
        self.open_file_btn = ttk.Button(ctrl_frame, text="Launch File", command=self.open_file, state="disabled")
        self.open_file_btn.pack(side="left", padx=5)
        
        # ETA Label and Progress Bar
        self.eta_label = ttk.Label(self.root, text="ETA: N/A")
        self.eta_label.pack(fill="x", padx=10, pady=(5,0))
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=10, pady=5)
        
        # Log window
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", padx=10, pady=5, expand=True)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text["yscrollcommand"] = log_scroll.set

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def browse_out_dir(self):
        folder = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if folder:
            self.out_dir_var.set(folder)

    def format_time(self, h, m, s):
        hh = h.strip() or "00"
        mm = m.strip() or "00"
        ss = s.strip() or "00"
        if hh == "00" and mm == "00" and ss == "00":
            return None
        return f"{hh.zfill(2)}:{mm.zfill(2)}:{ss.zfill(2)}"

    def build_command(self):
        cmd = ["yt-dlp"]
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return None
        cmd.append(url)
        
        # If Subs Only is checked, add flag
        if self.subs_only_var.get():
            cmd.append("--skip-download")
        
        # Format logic
        if not self.subs_only_var.get():
            fmt = self.format_var.get().lower()
            if fmt == "mp3":
                cmd.extend(["-x", "--audio-format", "mp3"])
            else:  # mp4: always choose highest quality combined stream
                cmd.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
        
        # Time segments
        start = self.format_time(self.start_h.get(), self.start_m.get(), self.start_s.get())
        end = self.format_time(self.end_h.get(), self.end_m.get(), self.end_s.get())
        if start or end:
            segment = f"{start if start else ''}-{end if end else ''}"
            cmd.extend(["--download-sections", f"*{segment}"])
        
        # Playlist option
        if self.playlist_var.get():
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")
        
        # Subtitles: if "Download Subs" is checked, add both flags.
        if self.subs_var.get():
            cmd.append("--write-subs")
            cmd.append("--write-auto-subs")
        
        # Output template: using chosen output directory
        out_dir = self.out_dir_var.get()
        tmpl = os.path.join(out_dir, "%(title)s-%(id)s.%(ext)s")
        cmd.extend(["-o", tmpl])
        
        return cmd

    def start_download(self):
        cmd = self.build_command()
        if not cmd:
            return
        self.log("Starting download with command: " + " ".join(cmd))
        self.downloaded_file = None
        self.eta_label.config(text="ETA: N/A")
        self.open_dir_btn.config(state="disabled")
        self.open_file_btn.config(state="disabled")
        self.download_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        
        threading.Thread(target=self.run_command, args=(cmd,), daemon=True).start()

    def run_command(self, cmd):
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            for line in self.process.stdout:
                line = line.strip()
                # Update ETA and progress if line contains "[download]" and "ETA"
                if line.startswith("[download]") and "ETA" in line:
                    eta_match = re.search(r'ETA\s+([\d:]+)', line)
                    if eta_match:
                        self.eta_label.config(text=f"ETA: {eta_match.group(1)}")
                    pct_match = re.search(r'(\d+\.\d+)%', line)
                    if pct_match:
                        try:
                            self.progress["value"] = float(pct_match.group(1))
                        except ValueError:
                            pass
                    continue  # skip logging raw progress line
                else:
                    self.log(line)
                # Capture destination for non-playlist downloads
                if "--yes-playlist" not in cmd:
                    dest_match = re.search(r"Destination:\s*(.+)", line)
                    if dest_match:
                        self.downloaded_file = dest_match.group(1).strip()
            self.process.wait()
            if self.process.returncode == 0:
                self.log("Download completed successfully.")
            else:
                self.log(f"Download finished with errors (code {self.process.returncode}).")
        except Exception as e:
            self.log("Error during download: " + str(e))
        finally:
            self.process = None
            self.download_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.progress["value"] = 0
            self.open_dir_btn.config(state="normal")
            if self.downloaded_file:
                self.open_file_btn.config(state="normal")
            else:
                self.open_file_btn.config(state="disabled")

    def cancel_download(self):
        if self.process:
            self.log("Cancelling download...")
            self.process.terminate()
            self.process = None
            self.download_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.progress["value"] = 0

    def update_yt_dlp(self):
        self.log("Updating yt-dlp...")
        threading.Thread(target=self.run_update, daemon=True).start()
        
    def run_update(self):
        try:
            proc = subprocess.Popen(["yt-dlp", "-U"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            for line in proc.stdout:
                self.log(line.strip())
            proc.wait()
            self.log("Update finished.")
        except Exception as e:
            self.log("Error during update: " + str(e))
        
    def open_directory(self):
        out_dir = self.out_dir_var.get()
        try:
            os.startfile(out_dir)
        except Exception as e:
            self.log("Error opening directory: " + str(e))
    
    def open_file(self):
        if self.downloaded_file and os.path.isfile(self.downloaded_file):
            try:
                os.startfile(self.downloaded_file)
            except Exception as e:
                self.log("Error launching file: " + str(e))
        else:
            self.log("No downloaded file found.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleDownloaderApp(root)
    root.mainloop()
