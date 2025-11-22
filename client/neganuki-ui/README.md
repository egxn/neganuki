# Neganuki Scanner GUI

Graphical user interface for the Neganuki film scanner built with Tkinter.

## Features

### Connection Management
- ✅ Easy server connection with host/port configuration
- ✅ Visual connection status indicator
- ✅ Auto-connect on startup
- ✅ Connection state management

### Scan Controls
- ✅ **Start Scan** - Begin full scanning operation
- ✅ **Pause/Resume** - Control scan flow
- ✅ **Stop** - Abort current scan
- ✅ Visual progress indicator

### Frame Capture
- ✅ **Capture RGB** - Single preview frame with live preview
- ✅ **Capture RAW** - Single RAW Bayer frame
- ✅ Preview display in GUI

### Status Monitoring
- ✅ **Manual Refresh** - Get current scanner state on demand
- ✅ **Auto Monitor** - Continuous background status polling
- ✅ **Live Preview** - Real-time camera preview stream (idle state only)
- ✅ Real-time state updates (idle, capturing, stitching, etc.)
- ✅ Frame count tracking
- ✅ Color-coded status indicators

### Preview Panel
- ✅ Live frame preview display
- ✅ Automatic image scaling to fit window
- ✅ Maintains aspect ratio
- ✅ Updates after each capture

### Status Log
- ✅ Scrollable log with timestamps
- ✅ Color-coded messages (info, success, warning, error)
- ✅ All operations logged

### System Control
- ✅ Scanner shutdown
- ✅ Resource cleanup
- ✅ Confirmation dialogs for destructive operations

---

## Installation

### Requirements

```bash
# From project root
poetry install
```

### Dependencies

The GUI requires:
- `tkinter` (usually included with Python)
- `Pillow` (PIL) for image handling
- `grpcio` for scanner communication

Add Pillow if not already in dependencies:

```bash
poetry add Pillow
```

---

## Running the GUI

### From Project Root

```bash
poetry run python client/neganuki-ui/scanner_gui.py
```

### Make Executable

```bash
cd client/neganuki-ui
chmod +x scanner_gui.py
./scanner_gui.py
```

### With Poetry Shell

```bash
poetry shell
cd client/neganuki-ui
python scanner_gui.py
```

---

## Usage Guide

### 1. Connect to Scanner

1. Enter scanner host (default: `localhost`)
2. Enter port (default: `50051`)
3. Click **Connect**
4. Wait for green "Connected" indicator

### 2. Start a Scan

1. Click **▶ Start Scan**
2. Progress bar will indicate activity
3. Enable **Auto Monitor** to see real-time updates
4. Frame count updates automatically

### 3. Control Scan

- **⏸ Pause** - Temporarily pause scanning
- **⏵ Resume** - Continue after pause
- **⏹ Stop** - Abort current scan (with confirmation)

### 4. Capture Test Frames

- **📷 Capture RGB** - Preview frame (displayed in preview panel)
- **📷 Capture RAW** - RAW Bayer data (saved to disk)

### 5. Live Preview

- **Live Preview** checkbox - Enable real-time camera streaming
- Only available when scanner is in **idle** state
- Automatically stops when scan starts
- 10 FPS stream with JPEG compression
- No disk writes, pure memory streaming

### 6. Monitor Status

- **🔄 Refresh Status** - Manual status check
- **Auto Monitor** checkbox - Continuous polling (1 sec interval)

Status colors:
- 🔵 Blue: Active operations (capturing, evaluating, etc.)
- 🟢 Green: Completed successfully
- 🟠 Orange: Paused
- 🔴 Red: Error states
- ⚪ Gray: Idle

### 7. View Preview

- Preview panel shows live stream or last captured frame
- Enable **Live Preview** for real-time camera feed
- Image automatically scaled to fit
- Click **Capture RGB** to save and update preview

### 8. Monitor Logs

- Status log shows all operations with timestamps
- Color-coded messages:
  - Blue: Information
  - Green: Success
  - Orange: Warnings
  - Red: Errors

---

## Keyboard Shortcuts

While no keyboard shortcuts are currently implemented, you can add them by modifying the code:

```python
# Example: Add Ctrl+S to start scan
root.bind('<Control-s>', lambda e: app.start_scan())
```

---

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Connection: [localhost] [50051] [Connect] ● Connected      │
├─────────────────────┬───────────────────────────────────────┤
│ Scanner Controls    │  Frame Preview                        │
│                     │                                       │
│ Scan Operations:    │  [Preview Canvas - 600x400]          │
│ ▶ Start Scan        │                                       │
│ ⏸ Pause             │                                       │
│ ⏵ Resume            │                                       │
│ ⏹ Stop              │                                       │
│                     ├───────────────────────────────────────┤
│ Single Frame:       │  Scanner Status                       │
│ 📷 Capture RGB      │                                       │
│ 📷 Capture RAW      │  [Status Log - scrollable]           │
│                     │  [12:34:56] Starting scan...          │
│ Status:             │  [12:34:58] Frame count: 5            │
│ 🔄 Refresh          │  [12:35:00] Scan complete!            │
│ ☑ Auto Monitor      │                                       │
│                     │                                       │
│ System:             │                                       │
│ ⚠ Shutdown Scanner  │                                       │
├─────────────────────┴───────────────────────────────────────┤
│ State: capturing | Frames: 12 | [Progress Bar]             │
└─────────────────────────────────────────────────────────────┘
```

---

## Customization

### Change Window Size

```python
self.root.geometry("1280x960")  # Larger window
```

### Modify Preview Stream Settings

```python
# In _preview_stream_loop method
request = scanner_pb2.PreviewRequest(fps=15, quality=85)  # Higher FPS and quality
```

### Modify Poll Interval

```python
time.sleep(0.5)  # Poll every 500ms instead of 1 second
```

### Change Default Connection

```python
self.host_var = tk.StringVar(value="192.168.1.100")
self.port_var = tk.StringVar(value="50051")
```

### Add Custom Theme

The GUI attempts to load the Azure theme. You can use any ttk theme:

```python
# Download azure.tcl theme
# Place in same directory as scanner_gui.py
root.tk.call("source", "azure.tcl")
root.tk.call("set_theme", "dark")  # or "light"
```

---

## Troubleshooting

### GUI Doesn't Start

```bash
# Check if tkinter is installed
python -c "import tkinter; print('Tkinter OK')"

# On Ubuntu/Debian if missing:
sudo apt-get install python3-tk
```

### Connection Failed

- Ensure scanner server is running:
  ```bash
  poetry run python backend/grpc/server.py
  ```
- Check firewall settings
- Verify host and port are correct

### Preview Not Showing

- Ensure Pillow is installed:
  ```bash
  poetry add Pillow
  ```
- Check scanner is in idle state for live preview
- Check image path in status log for captured frames
- Verify captured image exists on disk

### Preview Stream Lag

- Reduce FPS in preview request (default: 10)
- Lower JPEG quality (default: 75)
- Check network latency if using remote connection
- Ensure scanner is in idle state

### High CPU Usage

- Disable Auto Monitor when not actively scanning
- Disable Live Preview when not needed
- Increase poll interval in `_monitor_loop()`
- Reduce preview stream FPS

### Window Too Small/Large

- Resize window manually (it's resizable)
- Or change `self.root.geometry()` in code

---

## Future Enhancements

### Planned Features

- [x] Live camera preview stream
- [ ] Preview of stitched frames
- [ ] Configuration panel for scan parameters
- [ ] Scan history/gallery
- [ ] Export settings
- [ ] Keyboard shortcuts
- [ ] Multiple scanner management
- [ ] Batch operations
- [ ] Statistics dashboard
- [ ] Recording/playback of preview stream

### Contributing

To add new features:

1. Add UI elements in `_setup_ui()` methods
2. Create handler methods
3. Connect with gRPC calls via `self.stub`
4. Update status log and preview as needed

---

## Architecture

### Main Components

1. **ScannerGUI** - Main application class
   - Connection management
   - UI setup and layout
   - Event handlers

2. **Connection Frame** - Top bar
   - Host/port input
   - Connect button
   - Status indicator

3. **Control Panel** - Left side
   - Scan controls
   - Capture buttons
   - Status controls
   - System controls

4. **Preview Panel** - Right side
   - Canvas for frame preview
   - Status log with scrolling

5. **Status Bar** - Bottom
   - Current state
   - Frame count
   - Progress indicator

### Threading

- Main thread: UI and event handling
- Background thread: Status monitoring (when enabled)
- Background thread: Preview streaming (when enabled)
- Uses `root.after()` for thread-safe UI updates

### Preview Stream Protocol

1. Client requests stream with desired FPS and quality
2. Server checks scanner state (must be idle)
3. Server captures frames from camera at requested rate
4. Frames encoded as JPEG and streamed via gRPC
5. Client decodes and displays frames in real-time
6. Stream automatically stops when scanner leaves idle state

---

## License

Part of the Neganuki Film Scanner project.
