import os
import re
import threading
import subprocess
import queue
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional modern theming via ttkbootstrap (fallback gracefully if unavailable)
try:
    import ttkbootstrap as tb
    TTKB_AVAILABLE = True
except Exception:
    TTKB_AVAILABLE = False

DEFAULT_OUTPUT_DIR = r"D:\YTDLP"

class SimpleDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple YT Downloader")
        self.process = None
        self.downloaded_file = None
        self.msg_queue: "queue.Queue[dict]" = queue.Queue()

        # Initialize style / theme (match Gemini_Whisper_TkUI approach)
        if 'TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE:
            # Modern dark theme by default; user can change from UI
            self.style = tb.Style(theme='darkly')
        else:
            self.style = ttk.Style()
            try:
                self.style.theme_use('clam')
            except Exception:
                pass

        # Ensure default output directory exists
        try:
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        except Exception:
            pass

        # No quality selection UI; always pick highest quality AV stream for MP4.
        self.create_widgets()
        # Start UI queue polling for thread-safe updates
        self.root.after(100, self._poll_queue)
        
    def create_widgets(self):
        # URL Frame
        url_frame = ttk.LabelFrame(self.root, text="Video/Playlist URL")
        url_frame.pack(fill="x", padx=10, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=80)
        self.url_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        ttk.Button(url_frame, text="Paste", command=self.paste_url).pack(side="left", padx=(5, 0))
        
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
        
        # Options Frame: only Playlist, Download Subs, Subs Only + Theme switcher
        opts_frame = ttk.LabelFrame(self.root, text="Options", padding=5)
        opts_frame.pack(fill="x", padx=10, pady=5)
        self.playlist_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Playlist", variable=self.playlist_var).pack(side="left", padx=5)
        self.subs_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Download Subs", variable=self.subs_var).pack(side="left", padx=5)
        self.subs_only_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, text="Subs Only", variable=self.subs_only_var).pack(side="left", padx=5)
        
        # Theme switcher (parity with Gemini_Whisper_TkUI)
        def _switch_theme(event=None):
            if not ('TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE):
                messagebox.showinfo("Theme", "Advanced themes require ttkbootstrap to be installed.")
                return
            chosen = theme_combo.get()
            try:
                self.style.theme_use(chosen)
            except Exception as e:
                messagebox.showerror("Theme Error", f"Could not switch theme: {e}")

        if 'TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE:
            ttk.Label(opts_frame, text="Theme:").pack(side="left", padx=(16, 0))
            theme_combo = ttk.Combobox(
                opts_frame,
                state="readonly",
                width=12,
                values=self.style.theme_names(),
            )
            try:
                theme_combo.set(self.style.theme.name)
            except Exception:
                theme_combo.set('darkly')
            theme_combo.pack(side="left", padx=6)
            theme_combo.bind("<<ComboboxSelected>>", _switch_theme)

            def _set_dark():
                try:
                    self.style.theme_use('darkly')
                    theme_combo.set('darkly')
                except Exception:
                    pass

            def _set_blue():
                try:
                    self.style.theme_use('flatly')
                    theme_combo.set('flatly')
                except Exception:
                    pass

            ttk.Button(opts_frame, text="Dark", command=_set_dark).pack(side="left", padx=(8, 2))
            ttk.Button(opts_frame, text="Blue", command=_set_blue).pack(side="left", padx=(2, 0))
        else:
            ttk.Label(opts_frame, text="Install 'ttkbootstrap' for modern dark/blue themes.", foreground="#555").pack(side="left", padx=(16, 0))
        
        # Format Selection: Radio buttons for MP4 or MP3
        fmt_frame = ttk.LabelFrame(self.root, text="Output Format", padding=5)
        fmt_frame.pack(fill="x", padx=10, pady=5)
        self.format_var = tk.StringVar(value="mp4")
        ttk.Radiobutton(fmt_frame, text="MP4 (Video + Audio)", variable=self.format_var, value="mp4").pack(side="left", padx=10)
        ttk.Radiobutton(fmt_frame, text="MP3 (Audio Only)", variable=self.format_var, value="mp3").pack(side="left", padx=10)

        # MP4-specific options (Resolution selection)
        mp4_opts = ttk.LabelFrame(self.root, text="MP4 Options", padding=5)
        mp4_opts.pack(fill="x", padx=10, pady=(0,5))
        ttk.Label(mp4_opts, text="Resolution:").pack(side="left")
        self.resolution_var = tk.StringVar(value="best")
        self.resolution_combo = ttk.Combobox(
            mp4_opts,
            state="disabled",
            width=10,
            values=["best"],
            textvariable=self.resolution_var,
        )
        self.resolution_combo.pack(side="left", padx=6)
        self.fetch_btn = ttk.Button(mp4_opts, text="Fetch Resolutions", command=self.fetch_resolutions, state="disabled")
        self.fetch_btn.pack(side="left", padx=6)
        # Prefer 60fps checkbox
        self.prefer_60fps = tk.BooleanVar(value=False)
        self.fps_check = ttk.Checkbutton(mp4_opts, text="Prefer 60fps", variable=self.prefer_60fps, state="disabled")
        self.fps_check.pack(side="left", padx=6)

        # MP3-specific options
        mp3_opts = ttk.LabelFrame(self.root, text="MP3 Options", padding=5)
        mp3_opts.pack(fill="x", padx=10, pady=(0,5))
        ttk.Label(mp3_opts, text="Audio bitrate:").pack(side="left")
        self.audio_bitrate_var = tk.StringVar(value="192K")
        self.audio_bitrate_combo = ttk.Combobox(
            mp3_opts,
            state="readonly",
            width=8,
            values=["320K", "256K", "192K", "160K", "128K", "96K", "64K", "48K", "best"],
            textvariable=self.audio_bitrate_var,
        )
        self.audio_bitrate_combo.pack(side="left", padx=6)

        def _toggle_mp3_options(*_):
            is_mp3 = self.format_var.get().lower() == "mp3"
            subs_only = self.subs_only_var.get()
            state = "readonly" if is_mp3 and not subs_only else "disabled"
            try:
                self.audio_bitrate_combo.configure(state=state)
            except Exception:
                pass
            # MP4 controls
            is_mp4 = self.format_var.get().lower() == "mp4"
            mp4_state = "normal" if is_mp4 and not subs_only else "disabled"
            try:
                self.resolution_combo.configure(state=mp4_state)
                self.fetch_btn.configure(state=mp4_state)
                self.fps_check.configure(state=mp4_state)
            except Exception:
                pass
            # If switched to MP4 and URL present, auto-fetch (avoid spam if we already have >1 option)
            if is_mp4 and not subs_only:
                try:
                    if self.url_entry.get().strip() and len(self.resolution_combo.cget('values')) <= 1:
                        self.fetch_resolutions()
                except Exception:
                    pass

        self.format_var.trace_add("write", _toggle_mp3_options)
        # Subtitles-only implies no media download, so disable bitrate
        # Ensure variable exists before trace
        try:
            self.subs_only_var.trace_add("write", _toggle_mp3_options)
        except Exception:
            pass
        _toggle_mp3_options()
        
        # Output Directory
        out_dir_frame = ttk.LabelFrame(self.root, text="Output Directory", padding=5)
        out_dir_frame.pack(fill="x", padx=10, pady=5)
        # Confirm default output directory creation if missing
        initial_out_dir = DEFAULT_OUTPUT_DIR
        if not os.path.isdir(initial_out_dir):
            try:
                if messagebox.askyesno(
                    "Create Folder",
                    f"The default output folder does not exist:\n{initial_out_dir}\n\nCreate it now?"
                ):
                    os.makedirs(initial_out_dir, exist_ok=True)
                else:
                    fallback = os.path.join(os.path.expanduser("~"), "Downloads")
                    if not os.path.isdir(fallback):
                        fallback = os.path.expanduser("~")
                    initial_out_dir = fallback
            except Exception as e:
                messagebox.showerror("Folder Error", f"Could not create folder:\n{initial_out_dir}\n\n{e}")
                fallback = os.path.join(os.path.expanduser("~"), "Downloads")
                if not os.path.isdir(fallback):
                    fallback = os.path.expanduser("~")
                initial_out_dir = fallback
        self.out_dir_var = tk.StringVar(value=initial_out_dir)
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
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill="both", padx=10, pady=5, expand=True)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text["yscrollcommand"] = log_scroll.set

        # Basic dark palette fallback for Tk widgets if ttkbootstrap is unavailable
        if not ('TTKB_AVAILABLE' in globals() and TTKB_AVAILABLE):
            try:
                self.root.configure(bg='#1e1e1e')
                self.style.configure('TFrame', background='#1e1e1e')
                self.style.configure('TLabelframe', background='#1e1e1e', foreground='#e6e6e6')
                self.style.configure('TLabelframe.Label', background='#1e1e1e', foreground='#e6e6e6')
                self.style.configure('TLabel', background='#1e1e1e', foreground='#e6e6e6')
                self.style.configure('TButton', foreground='#e6e6e6')
                self.style.map('TButton', foreground=[('active', '#ffffff')])
                self.style.configure('TCheckbutton', background='#1e1e1e', foreground='#e6e6e6')
                # tk.Text needs manual colors
                self.log_text.configure(bg='#111214', fg='#e6e6e6', insertbackground='#e6e6e6')
            except Exception:
                pass

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _enqueue(self, item: dict):
        try:
            self.msg_queue.put_nowait(item)
        except Exception:
            pass

    def _poll_queue(self):
        try:
            while True:
                item = self.msg_queue.get_nowait()
                typ = item.get('type')
                if typ == 'log':
                    self.log(item.get('text', ''))
                elif typ == 'progress':
                    eta = item.get('eta')
                    if eta is not None:
                        self.eta_label.config(text=f"ETA: {eta}")
                    pct = item.get('pct')
                    if pct is not None:
                        try:
                            self.progress["value"] = float(pct)
                        except Exception:
                            pass
                elif typ == 'update_resolutions':
                    vals = item.get('values') or ["best"]
                    try:
                        self.resolution_combo.configure(values=vals)
                        # Keep current selection if still present, else set to best
                        cur = self.resolution_var.get()
                        if cur not in vals:
                            self.resolution_var.set(vals[0])
                    except Exception:
                        pass
                elif typ == 'enable_fetch':
                    try:
                        self.fetch_btn.configure(state='normal')
                    except Exception:
                        pass
                elif typ == 'done':
                    rc = item.get('returncode', -1)
                    self.process = None
                    self.download_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress["value"] = 0
                    self.open_dir_btn.config(state="normal")
                    self.downloaded_file = item.get('downloaded_file')
                    if self.downloaded_file:
                        self.open_file_btn.config(state="normal")
                    else:
                        self.open_file_btn.config(state="disabled")
                    if rc == 0:
                        self.log("Download completed successfully.")
                    else:
                        self.log(f"Download finished with errors (code {rc}).")
                elif typ == 'eta_reset':
                    self.eta_label.config(text="ETA: N/A")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def browse_out_dir(self):
        folder = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if folder:
            # askdirectory returns existing folders. Just set it.
            self.out_dir_var.set(folder)

    def paste_url(self):
        try:
            text = self.root.clipboard_get()
        except Exception:
            text = ""
        text = (text or "").strip()
        if not text:
            messagebox.showinfo("Paste URL", "Clipboard is empty.")
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, text)
        # Auto-fetch resolutions if MP4 is selected
        if self.format_var.get().lower() == 'mp4':
            self.fetch_resolutions()

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
                # Optional bitrate for mp3
                q = (self.audio_bitrate_var.get() or "").strip()
                if q and q.lower() != "best":
                    # yt-dlp accepts values like 192K for constant bitrate
                    cmd.extend(["--audio-quality", q])
            else:  # mp4: choose by selected resolution
                selected_res = (self.resolution_var.get() or "best").lower()
                prefer60 = bool(self.prefer_60fps.get())
                if selected_res == 'best' or selected_res == 'auto':
                    if prefer60:
                        fmt_selector = (
                            "bestvideo[ext=mp4][fps>=60]+bestaudio[ext=m4a]/"
                            "best[ext=mp4][fps>=60]/"
                            "best[fps>=60]/"
                            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                        )
                    else:
                        fmt_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                else:
                    try:
                        h = int(re.sub(r'[^0-9]', '', selected_res))
                        # Prefer mp4 video with height<=h (and optionally fps>=60), with fallbacks
                        if prefer60:
                            fmt_selector = (
                                f"bestvideo[ext=mp4][height<={h}][fps>=60]+bestaudio[ext=m4a]/"
                                f"best[ext=mp4][height<={h}][fps>=60]/"
                                f"best[height<={h}][fps>=60]/"
                                f"bestvideo[ext=mp4][height<={h}]+bestaudio[ext=m4a]/"
                                f"best[ext=mp4][height<={h}]/"
                                f"best[height<={h}]"
                            )
                        else:
                            fmt_selector = (
                                f"bestvideo[ext=mp4][height<={h}]+bestaudio[ext=m4a]/"
                                f"best[ext=mp4][height<={h}]/"
                                f"best[height<={h}]"
                            )
                    except Exception:
                        fmt_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                cmd.extend(["-f", fmt_selector])
        
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
        if not os.path.isdir(out_dir):
            try:
                if messagebox.askyesno(
                    "Create Folder",
                    f"Selected output folder does not exist:\n{out_dir}\n\nCreate it now?"
                ):
                    os.makedirs(out_dir, exist_ok=True)
                else:
                    messagebox.showwarning("Output Folder", "Please choose an existing folder.")
                    return None
            except Exception as e:
                messagebox.showerror("Folder Error", f"Could not create folder:\n{out_dir}\n\n{e}")
                return None
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
                        self._enqueue({'type': 'progress', 'eta': eta_match.group(1)})
                    pct_match = re.search(r'(\d+\.\d+)%', line)
                    if pct_match:
                        try:
                            self._enqueue({'type': 'progress', 'pct': float(pct_match.group(1))})
                        except ValueError:
                            pass
                    continue  # skip logging raw progress line
                else:
                    self._enqueue({'type': 'log', 'text': line})
                # Capture destination for non-playlist downloads
                if "--yes-playlist" not in cmd:
                    dest_match = re.search(r"Destination:\s*(.+)", line)
                    if dest_match:
                        self.downloaded_file = dest_match.group(1).strip()
            self.process.wait()
            self._enqueue({'type': 'done', 'returncode': self.process.returncode, 'downloaded_file': self.downloaded_file})
        except Exception as e:
            self._enqueue({'type': 'log', 'text': "Error during download: " + str(e)})
        finally:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                except Exception:
                    pass
            self._enqueue({'type': 'eta_reset'})

    def fetch_resolutions(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showinfo("Fetch Resolutions", "Enter or paste a URL first.")
            return
        # Disable fetch button while running
        try:
            self.fetch_btn.configure(state='disabled')
        except Exception:
            pass
        def _run():
            try:
                self._enqueue({'type': 'log', 'text': 'Querying formats: yt-dlp -F ...'})
                proc = subprocess.Popen(["yt-dlp", "-F", url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                lines = []
                for ln in proc.stdout:
                    s = ln.rstrip("\n")
                    lines.append(s)
                    # Limit log noise; show only a few lines
                proc.wait()
                text = "\n".join(lines)
                heights = set()
                for s in lines:
                    # Expect columns with extension and resolution; filter mp4 only
                    # Try to detect extension column as ' mp4 '
                    if re.search(r"\bmp4\b", s):
                        # Extract 720p/1080p etc.
                        m = re.search(r"(\d{3,4})p", s)
                        if m:
                            try:
                                heights.add(int(m.group(1)))
                            except Exception:
                                pass
                        else:
                            # Try WxH form
                            m2 = re.search(r"\b(\d{3,4})x(\d{3,4})\b", s)
                            if m2:
                                try:
                                    heights.add(int(m2.group(2)))
                                except Exception:
                                    pass
                if not heights:
                    # Fallback: take any numeric p tokens
                    for s in lines:
                        m = re.search(r"(\d{3,4})p", s)
                        if m:
                            try:
                                heights.add(int(m.group(1)))
                            except Exception:
                                pass
                vals = ["best"] + [f"{h}p" for h in sorted(heights, reverse=True)]
                self._enqueue({'type': 'update_resolutions', 'values': vals})
                self._enqueue({'type': 'log', 'text': f"Available MP4 resolutions: {', '.join(vals)}"})
            except Exception as e:
                self._enqueue({'type': 'log', 'text': f'Format query failed: {e}'})
            finally:
                self._enqueue({'type': 'enable_fetch'})
        threading.Thread(target=_run, daemon=True).start()

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
        # Attempt yt-dlp self-update first; fall back to pip update if needed.
        fallback_pip = False
        try:
            self._enqueue({'type': 'log', 'text': 'Updating yt-dlp via self-update (yt-dlp -U)...'})
            proc = subprocess.Popen(["yt-dlp", "-U"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            for line in proc.stdout:
                s = line.strip()
                self._enqueue({'type': 'log', 'text': s})
                if 'Use that to update' in s or 'pip' in s and 'update' in s and 'yt-dlp' in s:
                    fallback_pip = True
            proc.wait()
            if proc.returncode != 0:
                fallback_pip = True
        except Exception as e:
            self._enqueue({'type': 'log', 'text': f"Self-update failed: {e}"})
            fallback_pip = True

        if fallback_pip:
            self._enqueue({'type': 'log', 'text': 'Trying pip update in current Python environment...'})
            self._pip_update()
        else:
            self._enqueue({'type': 'log', 'text': 'Update finished. You may need to restart the app.'})

    def _pip_update(self):
        # Try pip update; if it fails (e.g., permissions), retry with --user
        cmds = [
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            [sys.executable, '-m', 'pip', 'install', '--upgrade', '--user', 'yt-dlp'],
        ]
        for idx, cmd in enumerate(cmds, start=1):
            try:
                self._enqueue({'type': 'log', 'text': 'Running: ' + ' '.join(cmd)})
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                for line in proc.stdout:
                    self._enqueue({'type': 'log', 'text': line.strip()})
                proc.wait()
                if proc.returncode == 0:
                    self._enqueue({'type': 'log', 'text': 'yt-dlp updated successfully via pip.'})
                    self._enqueue({'type': 'log', 'text': 'Tip: Restart this app to ensure the new version is used.'})
                    return
                else:
                    self._enqueue({'type': 'log', 'text': f'pip update attempt {idx} failed with code {proc.returncode}.'})
            except Exception as e:
                self._enqueue({'type': 'log', 'text': f'pip update attempt {idx} error: {e}'})
        self._enqueue({'type': 'log', 'text': 'All update attempts finished. If yt-dlp is managed by pipx/scoop/choco, use that tool to update.'})
        
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
