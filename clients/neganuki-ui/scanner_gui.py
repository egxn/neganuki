"""
Neganuki Film Scanner GUI
==========================

Graphical user interface for controlling the film scanner.
Built with Tkinter for compatibility with Raspberry Pi.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from PIL import Image, ImageTk
import io
import sys
from pathlib import Path

# Add backend to path for proto imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

try:
    import grpc
    from backend.grpc.generated import scanner_pb2, scanner_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    print("WARNING: gRPC modules not available. Please run: poetry run generate-protos")


class ScannerGUI:
    """Main GUI application for the film scanner."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Neganuki Film Scanner")
        self.root.geometry("1024x768")
        self.root.resizable(True, True)
        
        # Connection state
        self.connected = False
        self.channel = None
        self.stub = None
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Preview streaming state
        self.preview_streaming = False
        self.preview_thread = None
        
        # Preview state
        self.current_preview = None
        self.preview_label = None
        
        # Status tracking
        self.last_frame_count = 0
        
        # Setup UI
        self._setup_ui()
        
        # Try to connect on startup
        self.after_id = self.root.after(500, self.try_auto_connect)
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Configure grid weights for responsive layout
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Top frame - Connection and controls
        self._create_connection_frame()
        
        # Main content frame
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Left panel - Controls
        self._create_control_panel(main_frame)
        
        # Right panel - Preview and status
        self._create_preview_panel(main_frame)
        
        # Bottom frame - Status bar
        self._create_status_bar()
    
    def _create_connection_frame(self):
        """Create connection controls at the top."""
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Host
        ttk.Label(conn_frame, text="Host:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.host_var = tk.StringVar(value="localhost")
        ttk.Entry(conn_frame, textvariable=self.host_var, width=20).grid(
            row=0, column=1, padx=5, pady=5, sticky="w"
        )
        
        # Port
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.port_var = tk.StringVar(value="50051")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=10).grid(
            row=0, column=3, padx=5, pady=5, sticky="w"
        )
        
        # Connect button
        self.connect_btn = ttk.Button(
            conn_frame, text="Connect", command=self.toggle_connection
        )
        self.connect_btn.grid(row=0, column=4, padx=10, pady=5)
        
        # Connection status indicator
        self.conn_status_label = ttk.Label(
            conn_frame, text="● Disconnected", foreground="red"
        )
        self.conn_status_label.grid(row=0, column=5, padx=10, pady=5)
    
    def _create_control_panel(self, parent):
        """Create the control panel with buttons."""
        control_frame = ttk.LabelFrame(parent, text="Scanner Controls", padding=10)
        control_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        control_frame.grid_columnconfigure(0, weight=1)
        
        # Scan controls
        scan_frame = ttk.LabelFrame(control_frame, text="Scan Operations", padding=10)
        scan_frame.grid(row=0, column=0, sticky="ew", pady=5)
        scan_frame.grid_columnconfigure(0, weight=1)
        
        self.start_btn = ttk.Button(
            scan_frame, text="▶ Start Scan", command=self.start_scan, style="Accent.TButton"
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", pady=2)
        
        self.pause_btn = ttk.Button(
            scan_frame, text="⏸ Pause", command=self.pause_scan, state="disabled"
        )
        self.pause_btn.grid(row=1, column=0, sticky="ew", pady=2)
        
        self.resume_btn = ttk.Button(
            scan_frame, text="⏵ Resume", command=self.resume_scan, state="disabled"
        )
        self.resume_btn.grid(row=2, column=0, sticky="ew", pady=2)
        
        self.stop_btn = ttk.Button(
            scan_frame, text="⏹ Stop", command=self.stop_scan, state="disabled"
        )
        self.stop_btn.grid(row=3, column=0, sticky="ew", pady=2)
        
        # Capture controls
        capture_frame = ttk.LabelFrame(control_frame, text="Single Frame Capture", padding=10)
        capture_frame.grid(row=1, column=0, sticky="ew", pady=5)
        capture_frame.grid_columnconfigure(0, weight=1)
        
        self.capture_rgb_btn = ttk.Button(
            capture_frame, text="📷 Capture RGB", command=self.capture_rgb
        )
        self.capture_rgb_btn.grid(row=0, column=0, sticky="ew", pady=2)
        
        self.capture_raw_btn = ttk.Button(
            capture_frame, text="📷 Capture RAW", command=self.capture_raw
        )
        self.capture_raw_btn.grid(row=1, column=0, sticky="ew", pady=2)
        
        self.calc_wb_btn = ttk.Button(
            capture_frame, text="⚖ Calculate White Balance", command=self.calculate_white_balance
        )
        self.calc_wb_btn.grid(row=2, column=0, sticky="ew", pady=2)
        
        # Camera preset controls
        preset_frame = ttk.LabelFrame(control_frame, text="Camera Presets", padding=10)
        preset_frame.grid(row=2, column=0, sticky="ew", pady=5)
        preset_frame.grid_columnconfigure(0, weight=1)
        
        # Current preset display
        current_preset_frame = ttk.Frame(preset_frame)
        current_preset_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(current_preset_frame, text="Current:").pack(side="left", padx=(0, 5))
        self.current_preset_label = ttk.Label(current_preset_frame, text="default", 
                                               font=("", 9, "bold"))
        self.current_preset_label.pack(side="left")
        
        # Preset selector
        preset_selector_frame = ttk.Frame(preset_frame)
        preset_selector_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(preset_selector_frame, text="Select:").pack(side="left", padx=(0, 5))
        self.preset_var = tk.StringVar(value="default")
        self.preset_combo = ttk.Combobox(preset_selector_frame, textvariable=self.preset_var,
                                         state="readonly", width=15)
        self.preset_combo["values"] = ["default"]
        self.preset_combo.pack(side="left", fill="x", expand=True)
        
        # Apply preset button
        self.apply_preset_btn = ttk.Button(
            preset_frame, text="✓ Apply Preset", command=self.apply_preset
        )
        self.apply_preset_btn.grid(row=2, column=0, sticky="ew", pady=2)
        
        # Refresh presets button
        self.refresh_presets_btn = ttk.Button(
            preset_frame, text="🔄 Refresh List", command=self.refresh_presets
        )
        self.refresh_presets_btn.grid(row=3, column=0, sticky="ew", pady=2)
        
        # Create custom preset button
        self.create_preset_btn = ttk.Button(
            preset_frame, text="➕ Create Custom", command=self.show_create_preset_dialog
        )
        self.create_preset_btn.grid(row=4, column=0, sticky="ew", pady=2)
        
        # Motor controls
        motor_frame = ttk.LabelFrame(control_frame, text="Manual Motor Control", padding=10)
        motor_frame.grid(row=3, column=0, sticky="ew", pady=5)
        motor_frame.grid_columnconfigure(0, weight=1)
        motor_frame.grid_columnconfigure(1, weight=1)
        
        # Steps input
        steps_subframe = ttk.Frame(motor_frame)
        steps_subframe.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        ttk.Label(steps_subframe, text="Steps:").pack(side="left", padx=(0, 5))
        self.motor_steps_var = tk.StringVar(value="100")
        steps_spinbox = ttk.Spinbox(
            steps_subframe, from_=1, to=5000, textvariable=self.motor_steps_var, width=10
        )
        steps_spinbox.pack(side="left", fill="x", expand=True)
        
        # Forward/Backward buttons
        self.motor_forward_btn = ttk.Button(
            motor_frame, text="⬆ Forward", command=self.move_motor_forward
        )
        self.motor_forward_btn.grid(row=1, column=0, sticky="ew", padx=(0, 2), pady=2)
        
        self.motor_backward_btn = ttk.Button(
            motor_frame, text="⬇ Backward", command=self.move_motor_backward
        )
        self.motor_backward_btn.grid(row=1, column=1, sticky="ew", padx=(2, 0), pady=2)
        
        # Status controls
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding=10)
        status_frame.grid(row=4, column=0, sticky="ew", pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.refresh_btn = ttk.Button(
            status_frame, text="🔄 Refresh Status", command=self.refresh_status
        )
        self.refresh_btn.grid(row=0, column=0, sticky="ew", pady=2)
        
        self.monitor_var = tk.BooleanVar(value=False)
        self.monitor_check = ttk.Checkbutton(
            status_frame, text="Auto Monitor", variable=self.monitor_var,
            command=self.toggle_monitoring
        )
        self.monitor_check.grid(row=1, column=0, sticky="w", pady=2)
        
        # Preview streaming control
        self.preview_stream_var = tk.BooleanVar(value=False)
        self.preview_stream_check = ttk.Checkbutton(
            status_frame, text="Live Preview", variable=self.preview_stream_var,
            command=self.toggle_preview_stream
        )
        self.preview_stream_check.grid(row=2, column=0, sticky="w", pady=2)
        
        # System controls
        system_frame = ttk.LabelFrame(control_frame, text="System", padding=10)
        system_frame.grid(row=5, column=0, sticky="ew", pady=5)
        system_frame.grid_columnconfigure(0, weight=1)
        
        self.shutdown_btn = ttk.Button(
            system_frame, text="⚠ Shutdown Scanner", command=self.shutdown_scanner
        )
        self.shutdown_btn.grid(row=0, column=0, sticky="ew", pady=2)
        
        # Spacer to push everything to top
        control_frame.grid_rowconfigure(6, weight=1)
    
    def _create_preview_panel(self, parent):
        """Create the preview and status panel."""
        preview_frame = ttk.Frame(parent)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        preview_frame.grid_rowconfigure(0, weight=2)
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        
        # Preview area
        preview_container = ttk.LabelFrame(preview_frame, text="Frame Preview", padding=10)
        preview_container.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        preview_container.grid_rowconfigure(0, weight=1)
        preview_container.grid_columnconfigure(0, weight=1)
        
        # Canvas for preview image
        self.preview_canvas = tk.Canvas(
            preview_container, bg="#2b2b2b", highlightthickness=0
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        
        # Placeholder text
        self.preview_canvas.create_text(
            300, 200, text="No preview available\n\nCapture a frame to see preview",
            fill="gray", font=("Arial", 14), tags="placeholder"
        )
        
        # Status display area
        status_container = ttk.LabelFrame(preview_frame, text="Scanner Status", padding=10)
        status_container.grid(row=1, column=0, sticky="nsew")
        status_container.grid_rowconfigure(0, weight=1)
        status_container.grid_columnconfigure(0, weight=1)
        
        # Status text widget
        self.status_text = scrolledtext.ScrolledText(
            status_container, height=10, wrap=tk.WORD, state="disabled",
            font=("Courier", 10)
        )
        self.status_text.grid(row=0, column=0, sticky="nsew")
        
        # Configure text tags for colored output
        self.status_text.tag_config("info", foreground="blue")
        self.status_text.tag_config("success", foreground="green")
        self.status_text.tag_config("warning", foreground="orange")
        self.status_text.tag_config("error", foreground="red")
        self.status_text.tag_config("bold", font=("Courier", 10, "bold"))
    
    def _create_status_bar(self):
        """Create the status bar at the bottom."""
        status_bar = ttk.Frame(self.root)
        status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        
        # Current state
        ttk.Label(status_bar, text="State:").grid(row=0, column=0, padx=5)
        self.state_label = ttk.Label(status_bar, text="idle", foreground="gray")
        self.state_label.grid(row=0, column=1, padx=5)
        
        # Frame count
        ttk.Label(status_bar, text="Frames:").grid(row=0, column=2, padx=(20, 5))
        self.frame_count_label = ttk.Label(status_bar, text="0", foreground="gray")
        self.frame_count_label.grid(row=0, column=3, padx=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            status_bar, mode="indeterminate", length=200
        )
        self.progress_bar.grid(row=0, column=4, padx=20)
    
    # ========== Connection Methods ==========
    
    def try_auto_connect(self):
        """Try to auto-connect on startup."""
        if GRPC_AVAILABLE:
            self.toggle_connection()
    
    def toggle_connection(self):
        """Toggle connection to the scanner."""
        if self.connected:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        """Connect to the scanner server."""
        if not GRPC_AVAILABLE:
            messagebox.showerror(
                "Error",
                "gRPC not available. Please run: poetry run generate-protos"
            )
            return
        
        host = self.host_var.get()
        port = self.port_var.get()
        
        try:
            self.log_status(f"Connecting to {host}:{port}...", "info")
            self.channel = grpc.insecure_channel(f'{host}:{port}')
            self.stub = scanner_pb2_grpc.ScannerServiceStub(self.channel)
            
            # Test connection with status request
            response = self.stub.GetStatus(scanner_pb2.StatusRequest())
            
            self.connected = True
            self.conn_status_label.config(text="● Connected", foreground="green")
            self.connect_btn.config(text="Disconnect")
            self.log_status(f"✓ Connected to scanner", "success")
            
            # Enable buttons
            self.enable_controls(True)
            
            # Load available presets
            self.refresh_presets()
            
            # Start monitoring if checkbox is enabled
            if self.monitor_var.get():
                self.start_monitoring()
            
            # Auto-start live preview on connection
            if not self.preview_streaming:
                self.preview_stream_var.set(True)
                self.start_preview_stream()
                self.log_status("✓ Live preview started automatically", "info")
            
        except Exception as e:
            self.log_status(f"✗ Connection failed: {e}", "error")
            messagebox.showerror("Connection Error", f"Could not connect to scanner:\n{e}")
    
    def disconnect(self):
        """Disconnect from the scanner."""
        if self.monitoring_active:
            self.stop_monitoring()
        
        if self.preview_streaming:
            self.stop_preview_stream()
        
        if self.channel:
            self.channel.close()
        
        self.connected = False
        self.channel = None
        self.stub = None
        
        self.conn_status_label.config(text="● Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        self.log_status("Disconnected from scanner", "info")
        
        # Disable buttons
        self.enable_controls(False)
    
    # ========== Scan Control Methods ==========
    
    def start_scan(self):
        """Start a new scan."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            self.log_status("Starting scan...", "info")
            response = self.stub.StartCapture(scanner_pb2.CaptureRequest())
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.start_btn.config(state="disabled")
                self.pause_btn.config(state="normal")
                self.stop_btn.config(state="normal")
                self.progress_bar.start()
                
                # Enable monitoring automatically
                if not self.monitoring_active:
                    self.monitor_var.set(True)
                    self.start_monitoring()
            else:
                self.log_status(f"✗ {response.message}", "error")
                messagebox.showerror("Scan Error", response.message)
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Error", f"Failed to start scan:\n{e}")
    
    def pause_scan(self):
        """Pause the current scan."""
        if not self.connected:
            return
        
        try:
            self.log_status("Pausing scan...", "info")
            response = self.stub.PauseScan(scanner_pb2.PauseRequest())
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.pause_btn.config(state="disabled")
                self.resume_btn.config(state="normal")
                self.progress_bar.stop()
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
    
    def resume_scan(self):
        """Resume a paused scan."""
        if not self.connected:
            return
        
        try:
            self.log_status("Resuming scan...", "info")
            response = self.stub.ResumeScan(scanner_pb2.ResumeRequest())
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.resume_btn.config(state="disabled")
                self.pause_btn.config(state="normal")
                self.progress_bar.start()
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
    
    def stop_scan(self):
        """Stop/abort the current scan."""
        if not self.connected:
            return
        
        result = messagebox.askyesno(
            "Stop Scan",
            "Are you sure you want to stop the scan?\nThis will abort the current operation."
        )
        
        if not result:
            return
        
        try:
            self.log_status("Stopping scan...", "warning")
            response = self.stub.Shutdown(scanner_pb2.ShutdownRequest())
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.reset_scan_buttons()
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
    
    # ========== Capture Methods ==========
    
    def capture_rgb(self):
        """Capture a single RGB frame."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            self.log_status("Capturing RGB frame...", "info")
            response = self.stub.CaptureFrame(
                scanner_pb2.FrameCaptureRequest(raw=False)
            )
            
            if response.success:
                self.log_status(f"✓ Frame saved: {response.path}", "success")
                # TODO: Load and display the captured frame
                self.load_preview_from_path(response.path)
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Capture Error", f"Failed to capture frame:\n{e}")
    
    def capture_raw(self):
        """Capture a single RAW frame."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            self.log_status("Capturing RAW frame...", "info")
            response = self.stub.CaptureFrame(
                scanner_pb2.FrameCaptureRequest(raw=True)
            )
            
            if response.success:
                self.log_status(f"✓ RAW frame saved: {response.path}", "success")
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Capture Error", f"Failed to capture RAW frame:\n{e}")
    
    def calculate_white_balance(self):
        """Calculate colour gains for white balance calibration."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            self.log_status("Calculating white balance gains...", "info")
            response = self.stub.CalculateColourGains(scanner_pb2.Empty())
            
            if response.success:
                self.log_status(
                    f"✓ Colour gains: R={response.r_gain:.3f}, B={response.b_gain:.3f}", 
                    "success"
                )
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("White Balance Error", f"Failed to calculate colour gains:\n{e}")
    
    # ========== Camera Preset Methods ==========
    
    def refresh_presets(self):
        """Refresh the list of available camera presets."""
        if not self.connected:
            return
        
        try:
            # Get list of presets
            response = self.stub.ListCameraPresets(scanner_pb2.Empty())
            
            if response.success:
                self.preset_combo["values"] = response.preset_names
                self.log_status(f"✓ Loaded {len(response.preset_names)} presets", "success")
                
                # Get current preset
                preset_response = self.stub.GetCameraPreset(scanner_pb2.Empty())
                if preset_response.success:
                    self.current_preset_label.config(text=preset_response.preset_name)
                    self.preset_var.set(preset_response.preset_name)
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error loading presets: {e}", "error")
    
    def apply_preset(self):
        """Apply the selected camera preset."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        preset_name = self.preset_var.get().strip()
        if not preset_name:
            messagebox.showwarning("No Preset Selected", "Please select a preset first")
            return
        
        try:
            self.log_status(f"Applying preset '{preset_name}'...", "info")
            response = self.stub.SetCameraPreset(
                scanner_pb2.SetPresetRequest(preset_name=preset_name)
            )
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.current_preset_label.config(text=preset_name)
            else:
                self.log_status(f"✗ {response.message}", "error")
                messagebox.showerror("Preset Error", response.message)
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Preset Error", f"Failed to apply preset:\n{e}")
    
    def show_create_preset_dialog(self):
        """Show dialog to create a custom camera preset."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Custom Preset")
        dialog.geometry("400x500")
        dialog.resizable(False, False)
        
        # Make it modal
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill="both", expand=True)
        
        # Preset name
        ttk.Label(main_frame, text="Preset Name:", font=("", 10, "bold")).pack(anchor="w", pady=(0, 5))
        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var)
        name_entry.pack(fill="x", pady=(0, 15))
        
        # Create a scrollable frame for controls
        canvas = tk.Canvas(main_frame, height=300)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Control inputs
        ttk.Label(scrollable_frame, text="Control Values:", font=("", 10, "bold")).pack(anchor="w", pady=(0, 10))
        
        controls = {}
        
        # AeEnable
        ae_frame = ttk.Frame(scrollable_frame)
        ae_frame.pack(fill="x", pady=5)
        ttk.Label(ae_frame, text="AeEnable:").pack(side="left", padx=(0, 10))
        ae_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ae_frame, variable=ae_var).pack(side="left")
        controls["AeEnable"] = ae_var
        
        # ExposureTime
        exp_frame = ttk.Frame(scrollable_frame)
        exp_frame.pack(fill="x", pady=5)
        ttk.Label(exp_frame, text="ExposureTime (μs):").pack(side="left", padx=(0, 10))
        exp_var = tk.StringVar(value="10000")
        ttk.Entry(exp_frame, textvariable=exp_var, width=15).pack(side="left")
        controls["ExposureTime"] = exp_var
        
        # AwbEnable
        awb_frame = ttk.Frame(scrollable_frame)
        awb_frame.pack(fill="x", pady=5)
        ttk.Label(awb_frame, text="AwbEnable:").pack(side="left", padx=(0, 10))
        awb_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(awb_frame, variable=awb_var).pack(side="left")
        controls["AwbEnable"] = awb_var
        
        # ColourGains
        cg_frame = ttk.Frame(scrollable_frame)
        cg_frame.pack(fill="x", pady=5)
        ttk.Label(cg_frame, text="ColourGains (R,B):").pack(side="left", padx=(0, 10))
        cg_r_var = tk.StringVar(value="2.2")
        cg_b_var = tk.StringVar(value="1.6")
        ttk.Entry(cg_frame, textvariable=cg_r_var, width=8).pack(side="left", padx=(0, 5))
        ttk.Entry(cg_frame, textvariable=cg_b_var, width=8).pack(side="left")
        controls["ColourGains"] = (cg_r_var, cg_b_var)
        
        # Brightness
        br_frame = ttk.Frame(scrollable_frame)
        br_frame.pack(fill="x", pady=5)
        ttk.Label(br_frame, text="Brightness:").pack(side="left", padx=(0, 10))
        br_var = tk.StringVar(value="0.0")
        ttk.Entry(br_frame, textvariable=br_var, width=15).pack(side="left")
        controls["Brightness"] = br_var
        
        # Contrast
        co_frame = ttk.Frame(scrollable_frame)
        co_frame.pack(fill="x", pady=5)
        ttk.Label(co_frame, text="Contrast:").pack(side="left", padx=(0, 10))
        co_var = tk.StringVar(value="1.0")
        ttk.Entry(co_frame, textvariable=co_var, width=15).pack(side="left")
        controls["Contrast"] = co_var
        
        # Sharpness
        sh_frame = ttk.Frame(scrollable_frame)
        sh_frame.pack(fill="x", pady=5)
        ttk.Label(sh_frame, text="Sharpness:").pack(side="left", padx=(0, 10))
        sh_var = tk.StringVar(value="0.0")
        ttk.Entry(sh_frame, textvariable=sh_var, width=15).pack(side="left")
        controls["Sharpness"] = sh_var
        
        # Saturation
        sa_frame = ttk.Frame(scrollable_frame)
        sa_frame.pack(fill="x", pady=5)
        ttk.Label(sa_frame, text="Saturation:").pack(side="left", padx=(0, 10))
        sa_var = tk.StringVar(value="1.0")
        ttk.Entry(sa_frame, textvariable=sa_var, width=15).pack(side="left")
        controls["Saturation"] = sa_var
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Note about white balance
        note_frame = ttk.Frame(main_frame)
        note_frame.pack(fill="x", pady=(10, 0))
        note_label = ttk.Label(note_frame, text="⚠ Keep ColourGains consistent for stitching!", 
                               foreground="orange", font=("", 9))
        note_label.pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(15, 0))
        
        def create_preset():
            preset_name = name_var.get().strip()
            if not preset_name:
                messagebox.showwarning("Invalid Name", "Please enter a preset name")
                return
            
            try:
                # Build controls dict
                controls_dict = {
                    "AeEnable": str(controls["AeEnable"].get()),
                    "ExposureTime": controls["ExposureTime"].get(),
                    "AwbEnable": str(controls["AwbEnable"].get()),
                    "ColourGains": f"{controls['ColourGains'][0].get()},{controls['ColourGains'][1].get()}",
                    "Brightness": controls["Brightness"].get(),
                    "Contrast": controls["Contrast"].get(),
                    "Sharpness": controls["Sharpness"].get(),
                    "Saturation": controls["Saturation"].get(),
                }
                
                self.log_status(f"Creating preset '{preset_name}'...", "info")
                response = self.stub.CreateCameraPreset(
                    scanner_pb2.CreatePresetRequest(
                        preset_name=preset_name,
                        controls=controls_dict
                    )
                )
                
                if response.success:
                    self.log_status(f"✓ {response.message}", "success")
                    messagebox.showinfo("Success", f"Preset '{preset_name}' created successfully!")
                    dialog.destroy()
                    self.refresh_presets()
                else:
                    self.log_status(f"✗ {response.message}", "error")
                    messagebox.showerror("Error", response.message)
            
            except Exception as e:
                self.log_status(f"✗ Error: {e}", "error")
                messagebox.showerror("Error", f"Failed to create preset:\n{e}")
        
        ttk.Button(button_frame, text="Create", command=create_preset, 
                   style="Accent.TButton").pack(side="left", padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left")
    
    # ========== Motor Control Methods ==========
    
    def move_motor_forward(self):
        """Move motor forward by specified steps."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            steps = int(self.motor_steps_var.get())
            if steps <= 0:
                messagebox.showwarning("Invalid Steps", "Steps must be a positive number")
                return
            
            self.log_status(f"Moving motor forward {steps} steps...", "info")
            response = self.stub.MoveMotor(
                scanner_pb2.MotorMoveRequest(steps=steps)
            )
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
            else:
                self.log_status(f"✗ {response.message}", "error")
                messagebox.showwarning("Motor Error", response.message)
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for steps")
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Motor Error", f"Failed to move motor:\n{e}")
    
    def move_motor_backward(self):
        """Move motor backward by specified steps."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect to the scanner first")
            return
        
        try:
            steps = int(self.motor_steps_var.get())
            if steps <= 0:
                messagebox.showwarning("Invalid Steps", "Steps must be a positive number")
                return
            
            self.log_status(f"Moving motor backward {steps} steps...", "info")
            response = self.stub.MoveMotor(
                scanner_pb2.MotorMoveRequest(steps=-steps)  # Negative for backward
            )
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
            else:
                self.log_status(f"✗ {response.message}", "error")
                messagebox.showwarning("Motor Error", response.message)
        
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for steps")
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Motor Error", f"Failed to move motor:\n{e}")
    
    # ========== Status Methods ==========
    
    def refresh_status(self):
        """Manually refresh the scanner status."""
        if not self.connected:
            return
        
        try:
            response = self.stub.GetStatus(scanner_pb2.StatusRequest())
            
            if response.success:
                self.update_status_display(
                    response.state,
                    response.frame_count,
                    response.message
                )
            else:
                self.log_status(f"✗ Failed to get status: {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
    
    def toggle_monitoring(self):
        """Toggle automatic status monitoring."""
        if self.monitor_var.get():
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """Start monitoring scanner status in background thread."""
        if self.monitoring_active or not self.connected:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.log_status("Status monitoring started", "info")
    
    def stop_monitoring(self):
        """Stop monitoring scanner status."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.log_status("Status monitoring stopped", "info")
    
    def _monitor_loop(self):
        """Background loop for monitoring status."""
        while self.monitoring_active and self.connected:
            try:
                response = self.stub.GetStatus(scanner_pb2.StatusRequest())
                
                if response.success:
                    self.root.after(
                        0,
                        self.update_status_display,
                        response.state,
                        response.frame_count,
                        response.message
                    )
            except Exception as e:
                # Connection lost
                self.root.after(0, self.log_status, f"Monitor error: {e}", "error")
                break
            
            time.sleep(1)  # Poll every second
    
    def update_status_display(self, state, frame_count, message):
        """Update the status display with new information."""
        # Update state label with color
        state_colors = {
            'idle': 'gray',
            'initializing': 'blue',
            'capturing': 'blue',
            'evaluating': 'blue',
            'stitching': 'purple',
            'advancing': 'blue',
            'checking_completion': 'blue',
            'paused': 'orange',
            'finished': 'green',
            'error': 'red',
            'camera_error': 'red',
            'motor_error': 'red'
        }
        
        color = state_colors.get(state, 'gray')
        self.state_label.config(text=state, foreground=color)
        self.frame_count_label.config(text=str(frame_count))
        
        # Log frame count changes
        if frame_count != self.last_frame_count:
            self.log_status(f"Frame count: {frame_count}", "info")
            self.last_frame_count = frame_count
        
        # Auto-start preview when idle
        if state == 'idle' and not self.preview_streaming and self.preview_stream_var.get():
            self.start_preview_stream()
        
        # Stop preview when not idle
        if state != 'idle' and self.preview_streaming:
            self.stop_preview_stream()
        
        # Handle state changes
        if state == 'finished':
            self.reset_scan_buttons()
            self.progress_bar.stop()
            self.log_status("✓ Scan completed!", "success")
            messagebox.showinfo("Scan Complete", f"Scan finished!\nCaptured {frame_count} frames")
        
        elif state in ['error', 'camera_error', 'motor_error']:
            self.reset_scan_buttons()
            self.progress_bar.stop()
            self.log_status(f"✗ Scanner entered error state: {state}", "error")
    
    # ========== Preview Streaming Methods ==========
    
    def toggle_preview_stream(self):
        """Toggle live preview streaming."""
        if self.preview_stream_var.get():
            self.start_preview_stream()
        else:
            self.stop_preview_stream()
    
    def start_preview_stream(self):
        """Start streaming live preview in background thread."""
        if self.preview_streaming or not self.connected:
            return
        
        # Check if scanner is in idle state
        try:
            response = self.stub.GetStatus(scanner_pb2.StatusRequest())
            if response.state != 'idle':
                self.log_status("⚠ Live preview only available in idle state", "warning")
                self.preview_stream_var.set(False)
                return
        except Exception as e:
            self.log_status(f"✗ Failed to check state: {e}", "error")
            self.preview_stream_var.set(False)
            return
        
        self.preview_streaming = True
        self.preview_thread = threading.Thread(target=self._preview_stream_loop, daemon=True)
        self.preview_thread.start()
        self.log_status("📹 Live preview started", "success")
    
    def stop_preview_stream(self):
        """Stop streaming live preview."""
        self.preview_streaming = False
        if self.preview_thread:
            self.preview_thread.join(timeout=2)
        self.log_status("Live preview stopped", "info")
        
        # Clear preview and show placeholder
        self.preview_canvas.delete("all")
        canvas_width = self.preview_canvas.winfo_width() or 600
        canvas_height = self.preview_canvas.winfo_height() or 400
        self.preview_canvas.create_text(
            canvas_width // 2, canvas_height // 2,
            text="No preview available\n\nCapture a frame or enable Live Preview",
            fill="gray", font=("Arial", 14), tags="placeholder"
        )
    
    def _preview_stream_loop(self):
        """Background loop for receiving and displaying preview stream."""
        try:
            # Request preview stream with 20 FPS and 60% quality for faster streaming
            request = scanner_pb2.PreviewRequest(fps=20, quality=60)
            stream = self.stub.StreamPreview(request)
            
            for frame_msg in stream:
                if not self.preview_streaming:
                    break
                
                try:
                    # Decode JPEG data
                    jpeg_bytes = frame_msg.image_data
                    image = Image.open(io.BytesIO(jpeg_bytes))
                    
                    # Update preview on main thread
                    self.root.after(0, self._update_preview_from_image, image)
                    
                except Exception as e:
                    self.log_status(f"Frame decode error: {e}", "error")
                    continue
                    
        except Exception as e:
            if self.preview_streaming:  # Only log if we didn't stop intentionally
                self.root.after(0, self.log_status, f"✗ Preview stream error: {e}", "error")
                self.root.after(0, lambda: self.preview_stream_var.set(False))
        finally:
            self.preview_streaming = False
    
    def _update_preview_from_image(self, image):
        """Update preview canvas with PIL Image (called on main thread)."""
        try:
            # Get canvas size
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            # If canvas not yet rendered, use default size
            if canvas_width <= 1:
                canvas_width = 600
            if canvas_height <= 1:
                canvas_height = 400
            
            # Resize image to fit canvas while maintaining aspect ratio
            img_copy = image.copy()
            img_copy.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img_copy)
            
            # Clear canvas
            self.preview_canvas.delete("all")
            
            # Center image on canvas
            x = canvas_width // 2
            y = canvas_height // 2
            self.preview_canvas.create_image(x, y, image=photo, anchor=tk.CENTER)
            
            # Keep reference to prevent garbage collection
            self.current_preview = photo
            
        except Exception as e:
            self.log_status(f"Preview update error: {e}", "error")
    
    # ========== System Methods ==========
    
    def shutdown_scanner(self):
        """Shutdown the scanner system."""
        if not self.connected:
            return
        
        result = messagebox.askyesno(
            "Shutdown Scanner",
            "Are you sure you want to shutdown the scanner?\n"
            "This will stop all operations and cleanup resources."
        )
        
        if not result:
            return
        
        try:
            self.log_status("Shutting down scanner...", "warning")
            response = self.stub.Shutdown(scanner_pb2.ShutdownRequest())
            
            if response.success:
                self.log_status(f"✓ {response.message}", "success")
                self.reset_scan_buttons()
                messagebox.showinfo("Shutdown", "Scanner shutdown successfully")
            else:
                self.log_status(f"✗ {response.message}", "error")
        
        except Exception as e:
            self.log_status(f"✗ Error: {e}", "error")
            messagebox.showerror("Shutdown Error", f"Failed to shutdown scanner:\n{e}")
    
    # ========== UI Helper Methods ==========
    
    def enable_controls(self, enabled):
        """Enable or disable control buttons based on connection state."""
        state = "normal" if enabled else "disabled"
        
        self.start_btn.config(state=state)
        self.capture_rgb_btn.config(state=state)
        self.capture_raw_btn.config(state=state)
        self.refresh_btn.config(state=state)
        self.shutdown_btn.config(state=state)
        
        if not enabled:
            self.reset_scan_buttons()
    
    def reset_scan_buttons(self):
        """Reset scan control buttons to default state."""
        self.start_btn.config(state="normal" if self.connected else "disabled")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.progress_bar.stop()
    
    def log_status(self, message, level="info"):
        """Log a status message to the status text widget."""
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, formatted_msg, level)
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
    
    def load_preview_from_path(self, image_path):
        """Load and display an image in the preview canvas."""
        try:
            # Load image
            img = Image.open(image_path)
            
            # Get canvas size
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            # If canvas not yet rendered, use default size
            if canvas_width <= 1:
                canvas_width = 600
            if canvas_height <= 1:
                canvas_height = 400
            
            # Resize image to fit canvas while maintaining aspect ratio
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Clear canvas
            self.preview_canvas.delete("all")
            
            # Center image on canvas
            x = canvas_width // 2
            y = canvas_height // 2
            self.preview_canvas.create_image(x, y, image=photo, anchor=tk.CENTER)
            
            # Keep reference to prevent garbage collection
            self.current_preview = photo
            
        except Exception as e:
            self.log_status(f"Failed to load preview: {e}", "error")
    
    def on_closing(self):
        """Handle window closing event."""
        if self.preview_streaming:
            self.stop_preview_stream()
        
        if self.monitoring_active:
            self.stop_monitoring()
        
        if self.connected:
            self.disconnect()
        
        self.root.destroy()


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    
    # Set theme (if available)
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", "dark")
    except:
        pass  # Theme not available, use default
    
    app = ScannerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
