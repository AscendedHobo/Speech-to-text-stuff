import os
import re
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT_OUTPUT_DIR = r"D:\YTDLP"  # default output directory

class YTDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YT Downloader")
        self.process = None
        self.create_widgets()
        
    def create_widgets(self):
        # URL Frame
        url_frame = ttk.LabelFrame(self.root, text="Video/Playlist URL")
        url_frame.pack(fill="x", padx=10, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=80)
        self.url_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        
        # Time Segment Frame
        time_frame = ttk.LabelFrame(self.root, text="Time Segment (Optional, HH:MM:SS)")
        time_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(time_frame, text="Start:").pack(side="left", padx=5)
        self.start_time_entry = ttk.Entry(time_frame, width=10)
        self.start_time_entry.pack(side="left", padx=5)
        ttk.Label(time_frame, text="End:").pack(side="left", padx=5)
        self.end_time_entry = ttk.Entry(time_frame, width=10)
        self.end_time_entry.pack(side="left", padx=5)
        
        # Options Frame
        options_frame = ttk.LabelFrame(self.root, text="Options")
        options_frame.pack(fill="x", padx=10, pady=5)
        self.audio_only_var = tk.BooleanVar()
        self.playlist_var = tk.BooleanVar()
        self.write_subs_var = tk.BooleanVar()
        self.write_auto_subs_var = tk.BooleanVar()
        
        ttk.Checkbutton(options_frame, text="Audio Only", variable=self.audio_only_var).pack(side="left", padx=5)
        ttk.Checkbutton(options_frame, text="Playlist", variable=self.playlist_var).pack(side="left", padx=5)
        ttk.Checkbutton(options_frame, text="Download Subtitles", variable=self.write_subs_var).pack(side="left", padx=5)
        ttk.Checkbutton(options_frame, text="Download Auto-Subs", variable=self.write_auto_subs_var).pack(side="left", padx=5)
        
        # Format Selection Frame
        format_frame = ttk.LabelFrame(self.root, text="Output Format")
        format_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(format_frame, text="Format:").pack(side="left", padx=5)
        self.format_var = tk.StringVar(value="mp4")
        format_options = ["mp3", "mp4", "mkv", "webm"]
        self.format_dropdown = ttk.OptionMenu(format_frame, self.format_var, self.format_var.get(), *format_options)
        self.format_dropdown.pack(side="left", padx=5)
        
        # Output Directory Frame
        out_dir_frame = ttk.LabelFrame(self.root, text="Output Directory")
        out_dir_frame.pack(fill="x", padx=10, pady=5)
        self.out_dir_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.out_dir_label = ttk.Label(out_dir_frame, textvariable=self.out_dir_var)
        self.out_dir_label.pack(side="left", padx=5)
        ttk.Button(out_dir_frame, text="Browse...", command=self.browse_output_dir).pack(side="left", padx=5)
        
        # Preset Frame
        preset_frame = ttk.LabelFrame(self.root, text="Presets")
        preset_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(preset_frame, text="Save Preset", command=self.save_preset).pack(side="left", padx=5)
        ttk.Button(preset_frame, text="Load Preset", command=self.load_preset).pack(side="left", padx=5)
        
        # Control Buttons Frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=5)
        self.download_btn = ttk.Button(control_frame, text="Download", command=self.start_download)
        self.download_btn.pack(side="left", padx=5)
        self.cancel_btn = ttk.Button(control_frame, text="Cancel", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)
        self.update_btn = ttk.Button(control_frame, text="Update yt-dlp", command=self.update_yt_dlp)
        self.update_btn.pack(side="left", padx=5)
        
        # Progress Bar
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=10, pady=5)
        
        # Logging/Console Window
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", padx=10, pady=5, expand=True)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text['yscrollcommand'] = log_scroll.set

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
    
    def browse_output_dir(self):
        directory = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if directory:
            self.out_dir_var.set(directory)
    
    def build_command(self):
        cmd = ["yt-dlp"]
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return None
        
        cmd.append(url)
        
        fmt = self.format_var.get().lower()
        if self.audio_only_var.get():
            cmd.extend(["-x", "--audio-format", fmt])
        else:
            if fmt == "mp4":
                # Try to get mp4 video with m4a audio, but fallback to any available formats
                cmd.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio"])
        
        # Time segments
        start = self.start_time_entry.get().strip()
        end = self.end_time_entry.get().strip()
        if start or end:
            segment = ""
            if start:
                segment += start
            segment += "-"
            if end:
                segment += end
            cmd.extend(["--download-sections", f"*{segment}"])
        
        # Playlist
        if self.playlist_var.get():
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")
        
        # Subtitles
        if self.write_subs_var.get():
            cmd.append("--write-subs")
        if self.write_auto_subs_var.get():
            cmd.append("--write-auto-subs")
        
        # Output template: using chosen directory and filename template
        out_dir = self.out_dir_var.get()
        output_template = os.path.join(out_dir, "%(title)s-%(id)s.%(ext)s")
        cmd.extend(["-o", output_template])
        
        return cmd

    def start_download(self):
        cmd = self.build_command()
        if not cmd:
            return
        
        self.log("Starting download with command: " + " ".join(cmd))
        self.download_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress["value"] = 0
        
        # Run download in a separate thread
        threading.Thread(target=self.run_command, args=(cmd,), daemon=True).start()

    def run_command(self, cmd):
        try:
            # Launch subprocess; capture both stdout and stderr
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            # Read output line by line
            for line in self.process.stdout:
                self.log(line.strip())
                # Try to parse a percentage (e.g., "12.3%")
                match = re.search(r'(\d+\.\d+)%', line)
                if match:
                    try:
                        percent = float(match.group(1))
                        self.progress["value"] = percent
                    except ValueError:
                        pass
            self.process.wait()
            if self.process.returncode == 0:
                self.log("Download completed successfully.")
            else:
                self.log("Download finished with errors (code {}).".format(self.process.returncode))
        except Exception as e:
            self.log("Error during download: " + str(e))
        finally:
            self.process = None
            self.download_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.progress["value"] = 0

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
        # Run "yt-dlp -U" in a separate thread
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
        
    def save_preset(self):
        preset = {
            "url": self.url_entry.get().strip(),
            "start_time": self.start_time_entry.get().strip(),
            "end_time": self.end_time_entry.get().strip(),
            "audio_only": self.audio_only_var.get(),
            "playlist": self.playlist_var.get(),
            "write_subs": self.write_subs_var.get(),
            "write_auto_subs": self.write_auto_subs_var.get(),
            "format": self.format_var.get(),
            "out_dir": self.out_dir_var.get()
        }
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(preset, f, indent=4)
                self.log("Preset saved to " + file_path)
            except Exception as e:
                self.log("Error saving preset: " + str(e))
    
    def load_preset(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, "r") as f:
                    preset = json.load(f)
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, preset.get("url", ""))
                self.start_time_entry.delete(0, "end")
                self.start_time_entry.insert(0, preset.get("start_time", ""))
                self.end_time_entry.delete(0, "end")
                self.end_time_entry.insert(0, preset.get("end_time", ""))
                self.audio_only_var.set(preset.get("audio_only", False))
                self.playlist_var.set(preset.get("playlist", False))
                self.write_subs_var.set(preset.get("write_subs", False))
                self.write_auto_subs_var.set(preset.get("write_auto_subs", False))
                self.format_var.set(preset.get("format", "mp4"))
                self.out_dir_var.set(preset.get("out_dir", DEFAULT_OUTPUT_DIR))
                self.log("Preset loaded from " + file_path)
            except Exception as e:
                self.log("Error loading preset: " + str(e))
        
if __name__ == "__main__":
    root = tk.Tk()
    app = YTDownloaderApp(root)
    root.mainloop()
