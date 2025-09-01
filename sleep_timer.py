import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import threading
import time

class SleepTimerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configure the window
        self.title("Sleep Timer")
        self.geometry("300x200")
        self.resizable(False, False)
        
        # Set window icon and style
        self.configure(bg="#f0f0f0")
        
        # Create a frame for content
        main_frame = ttk.Frame(self)
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        # Create and place widgets
        ttk.Label(main_frame, text="Put PC to sleep after:", font=("Segoe UI", 12)).pack(pady=(0, 10))
        
        # Time input frame
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(pady=10)
        
        self.time_entry = ttk.Entry(time_frame, width=8, font=("Segoe UI", 12), justify="center")
        self.time_entry.pack(side="left", padx=(0, 5))
        self.time_entry.insert(0, "30")
        
        # Dropdown for time unit selection
        self.time_unit = tk.StringVar(value="minutes")
        time_unit_dropdown = ttk.Combobox(time_frame, textvariable=self.time_unit, 
                                         values=["seconds", "minutes", "hours"], 
                                         width=8, state="readonly")
        time_unit_dropdown.pack(side="left")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill="x")
        
        self.start_button = ttk.Button(button_frame, text="Start Timer", command=self.start_timer)
        self.start_button.pack(side="left", padx=5, expand=True, fill="x")
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_timer, state="disabled")
        self.cancel_button.pack(side="right", padx=5, expand=True, fill="x")
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Segoe UI", 9))
        self.status_label.pack(pady=(10, 0))
        
        # Timer variables
        self.timer_thread = None
        self.timer_running = False
        self.remaining_time = 0
        
    def start_timer(self):
        # Get time value
        try:
            time_value = float(self.time_entry.get())
            if time_value <= 0:
                messagebox.showerror("Invalid Input", "Please enter a positive number.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            return
        
        # Convert to seconds based on selected unit
        unit = self.time_unit.get()
        if unit == "minutes":
            seconds = time_value * 60
        elif unit == "hours":
            seconds = time_value * 3600
        else:  # seconds
            seconds = time_value
        
        # Update UI
        self.remaining_time = int(seconds)
        self.start_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.timer_running = True
        
        # Start timer in a separate thread
        self.timer_thread = threading.Thread(target=self.run_timer)
        self.timer_thread.daemon = True
        self.timer_thread.start()
    
    def run_timer(self):
        start_time = time.time()
        end_time = start_time + self.remaining_time
        
        while time.time() < end_time and self.timer_running:
            # Calculate remaining time
            self.remaining_time = int(end_time - time.time())
            
            # Update status label
            minutes, seconds = divmod(self.remaining_time, 60)
            hours, minutes = divmod(minutes, 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s remaining"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s remaining"
            else:
                time_str = f"{seconds}s remaining"
                
            self.status_var.set(time_str)
            
            # Sleep for a short time to avoid high CPU usage
            time.sleep(0.5)
        
        # If timer wasn't cancelled, put PC to sleep
        if self.timer_running:
            self.status_var.set("Putting PC to sleep...")
            self.update()
            time.sleep(1)  # Give user a moment to see the message
            self.put_pc_to_sleep()
        
        # Reset UI
        self.reset_ui()
    
    def cancel_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.status_var.set("Timer cancelled")
            self.reset_ui()
    
    def reset_ui(self):
        # Reset UI elements
        self.start_button.config(state="normal")
        self.cancel_button.config(state="disabled")
    
    def put_pc_to_sleep(self):
        # Use Windows API to put PC to sleep
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)

if __name__ == "__main__":
    app = SleepTimerApp()
    app.mainloop()