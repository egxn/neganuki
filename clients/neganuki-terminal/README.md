# Raspberry Pi Scanner Client

Python client applications for controlling the film scanner via gRPC.

## Installation

From the project root:

```bash
cd client/raspberry-pi
poetry install
```

## Client Applications

### 1. Scanner Client Library (`scanner_client.py`)

Core client library for programmatic control.

**Usage Example:**

```python
from scanner_client import ScannerClient

# Connect to scanner
client = ScannerClient(host='localhost', port=50051)
client.connect()

# Start scan
client.start_scan()

# Wait for completion
client.wait_for_completion()

# Get final status
status = client.get_status()
print(f"Captured {status['frame_count']} frames")

# Disconnect
client.disconnect()
```

**Command Line Usage:**

```bash
# Full scan
poetry run python scanner_client.py --action scan

# Get status
poetry run python scanner_client.py --action status

# Capture single frame
poetry run python scanner_client.py --action capture

# Capture RAW frame
poetry run python scanner_client.py --action capture --raw

# Stream status updates
poetry run python scanner_client.py --action stream

# Test workflow
poetry run python scanner_client.py --action test

# Connect to remote scanner
poetry run python scanner_client.py --host 192.168.1.100 --port 50051 --action scan
```

---

### 2. Interactive Scanner (`interactive_scanner.py`)

Terminal-based menu-driven interface.

**Launch:**

```bash
poetry run python interactive_scanner.py
```

**Features:**
- Color-coded status display
- Menu-driven interface
- Real-time status streaming
- Pause/resume control
- Single frame capture (RGB and RAW)
- Easy connection management

**Menu Options:**
1. Start Full Scan
2. Get Status
3. Pause Scan
4. Resume Scan
5. Capture Single Frame (RGB)
6. Capture Single Frame (RAW)
7. Stream Status Updates
8. Shutdown Scanner
9. Reconnect
0. Exit

---

### 3. Simple Scan (`simple_scan.py`)

Quick scanning for automation and simple tasks.

**Usage:**

```bash
# Quick scan with defaults
poetry run python simple_scan.py

# Test frame capture
poetry run python simple_scan.py --test

# RAW test capture
poetry run python simple_scan.py --test --raw

# Monitor ongoing scan
poetry run python simple_scan.py --monitor

# Remote scanner
poetry run python simple_scan.py --host 192.168.1.100
```

**Make executable:**

```bash
chmod +x simple_scan.py
./simple_scan.py
```

---

## API Reference

### ScannerClient Methods

#### Connection Management

- `connect()` - Establish connection to scanner
- `disconnect()` - Close connection
- `connected` - Connection status property

#### Scanning Operations

- `start_scan()` - Start the scanning process
- `pause_scan()` - Pause current scan
- `resume_scan()` - Resume paused scan
- `wait_for_completion(poll_interval=1.0)` - Wait for scan to finish

#### Status and Monitoring

- `get_status()` - Get current scanner status
  - Returns: `{'state': str, 'message': str, 'frame_count': int}`
- `stream_status(callback=None)` - Real-time status updates

#### Frame Capture

- `capture_frame(raw=False)` - Capture single frame
  - `raw=False`: RGB preview frame
  - `raw=True`: RAW Bayer data
  - Returns: Path to saved frame

#### System Control

- `shutdown()` - Shutdown scanner and cleanup

---

## Examples

### Example 1: Automated Scanning

```python
#!/usr/bin/env python3
from scanner_client import ScannerClient

def automated_scan():
    client = ScannerClient()
    
    if not client.connect():
        return
    
    try:
        # Capture test frame first
        print("Capturing test frame...")
        test_path = client.capture_frame(raw=False)
        print(f"Test frame: {test_path}")
        
        # Start full scan
        print("Starting full scan...")
        if client.start_scan():
            client.wait_for_completion()
            
            # Get final status
            status = client.get_status()
            print(f"Scan complete! {status['frame_count']} frames captured")
    
    finally:
        client.disconnect()

if __name__ == '__main__':
    automated_scan()
```

### Example 2: Status Monitoring

```python
#!/usr/bin/env python3
from scanner_client import ScannerClient
import time

def monitor_with_alerts():
    client = ScannerClient()
    
    if not client.connect():
        return
    
    try:
        client.start_scan()
        
        # Monitor with custom alerts
        while True:
            status = client.get_status()
            
            if status:
                print(f"State: {status['state']}, Frames: {status['frame_count']}")
                
                # Alert on errors
                if 'error' in status['state']:
                    print("⚠️  ERROR DETECTED!")
                    break
                
                # Complete
                if status['state'] == 'finished':
                    print("✓ Scan finished!")
                    break
            
            time.sleep(2)
    
    finally:
        client.disconnect()

if __name__ == '__main__':
    monitor_with_alerts()
```

### Example 3: Batch Capture

```python
#!/usr/bin/env python3
from scanner_client import ScannerClient
import time

def capture_batch(count=10, interval=2):
    """Capture multiple test frames with interval."""
    client = ScannerClient()
    
    if not client.connect():
        return
    
    try:
        frames = []
        
        for i in range(count):
            print(f"Capturing frame {i+1}/{count}...")
            path = client.capture_frame(raw=False)
            
            if path:
                frames.append(path)
                print(f"  ✓ Saved: {path}")
            else:
                print(f"  ✗ Failed")
            
            if i < count - 1:
                time.sleep(interval)
        
        print(f"\nCaptured {len(frames)}/{count} frames")
        return frames
    
    finally:
        client.disconnect()

if __name__ == '__main__':
    capture_batch(count=5, interval=3)
```

---

## Troubleshooting

### Connection Refused

```bash
# Ensure server is running
poetry run python backend/grpc/server.py

# Check if port is open
netstat -tuln | grep 50051
```

### Import Errors

```bash
# Regenerate proto files
poetry run generate-protos

# Reinstall dependencies
poetry install --sync
```

### Permission Errors

If running on Raspberry Pi:

```bash
# Add user to gpio group
sudo usermod -aG gpio $USER

# Reboot
sudo reboot
```

---

## Development

### Running Tests

```bash
# Test connection
poetry run python scanner_client.py --action status

# Test full workflow
poetry run python scanner_client.py --action test
```

### Custom Client Development

Extend `ScannerClient` for custom workflows:

```python
from scanner_client import ScannerClient

class CustomScanner(ScannerClient):
    def scan_with_preview(self):
        """Custom scanning with preview captures."""
        self.connect()
        
        # Capture preview
        preview = self.capture_frame(raw=False)
        
        # Start scan if preview looks good
        self.start_scan()
        self.wait_for_completion()
        
        self.disconnect()
```

---

## License

Part of the Neganuki Film Scanner project.
