"""
Raspberry Pi Scanner Client
============================

Interactive client to control the film scanner via gRPC.
Provides both CLI and programmatic interfaces.
"""

import grpc
import os
import shutil
import subprocess
import time
import sys
from pathlib import Path

# Add backend to path for proto imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

try:
    from backend.grpc.generated import scanner_pb2, scanner_pb2_grpc
except ImportError:
    print("ERROR: Generated protobuf files not found.")
    print("Please run: poetry run generate-protos")
    sys.exit(1)


class ScannerClient:
    """
    Client for controlling the film scanner via gRPC.
    
    Usage:
        client = ScannerClient(host='localhost', port=50051)
        client.connect()
        client.start_scan()
        client.wait_for_completion()
        client.disconnect()
    """
    
    def __init__(self, host: str = 'localhost', port: int = 50051):
        self.host = host
        self.port = port
        self.channel = None
        self.stub = None
        self.connected = False
    
    def connect(self):
        """Establish connection to the gRPC server."""
        try:
            self.channel = grpc.insecure_channel(f'{self.host}:{self.port}')
            self.stub = scanner_pb2_grpc.ScannerServiceStub(self.channel)
            self.connected = True
            print(f"✓ Connected to scanner at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close the gRPC connection."""
        if self.channel:
            self.channel.close()
            self.connected = False
            print("✓ Disconnected from scanner")
    
    def start_scan(self):
        """Start the scanning process."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False
        
        try:
            response = self.stub.StartCapture(scanner_pb2.CaptureRequest())
            if response.success:
                print(f"✓ Scan started: {response.message}")
                return True
            else:
                print(f"✗ Failed to start scan: {response.message}")
                return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False
    
    def get_status(self):
        """Get current scanner status."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return None
        
        try:
            response = self.stub.GetStatus(scanner_pb2.StatusRequest())
            if response.success:
                return {
                    'state': response.state,
                    'message': response.message,
                    'frame_count': response.frame_count
                }
            else:
                print(f"✗ Failed to get status: {response.message}")
                return None
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return None
    
    def pause_scan(self):
        """Pause the current scan."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False
        
        try:
            response = self.stub.PauseScan(scanner_pb2.PauseRequest())
            if response.success:
                print(f"✓ Scan paused: {response.message}")
                return True
            else:
                print(f"✗ Failed to pause: {response.message}")
                return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False
    
    def resume_scan(self):
        """Resume a paused scan."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False
        
        try:
            response = self.stub.ResumeScan(scanner_pb2.ResumeRequest())
            if response.success:
                print(f"✓ Scan resumed: {response.message}")
                return True
            else:
                print(f"✗ Failed to resume: {response.message}")
                return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False
    
    def capture_frame(self, raw: bool = False):
        """
        Capture a single frame.
        
        :param raw: If True, capture RAW Bayer data. If False, capture RGB preview.
        :return: Path to saved frame or None
        """
        if not self.connected:
            print("✗ Not connected to scanner")
            return None
        
        try:
            response = self.stub.CaptureFrame(
                scanner_pb2.FrameCaptureRequest(raw=raw)
            )
            if response.success:
                print(f"✓ Frame captured: {response.path}")
                return response.path
            else:
                print(f"✗ Capture failed: {response.message}")
                return None
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return None

    def move_motor(self, steps: int):
        """Move motor by steps (positive=forward, negative=backward)."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False

        try:
            response = self.stub.MoveMotor(scanner_pb2.MotorMoveRequest(steps=steps))
            if response.success:
                print(f"✓ Motor moved: {response.message}")
                return True
            print(f"✗ Motor move failed: {response.message}")
            return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False

    def calculate_colour_gains(self):
        """Calculate white balance gains from a RAW capture."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return None

        try:
            response = self.stub.CalculateColourGains(scanner_pb2.Empty())
            if response.success:
                gains = {'r_gain': response.r_gain, 'b_gain': response.b_gain}
                print(f"✓ Colour gains: R={response.r_gain:.4f}, B={response.b_gain:.4f}")
                return gains
            print(f"✗ Could not calculate gains: {response.message}")
            return None
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return None

    def set_camera_preset(self, preset_name: str):
        """Set camera controls from a named preset."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False

        try:
            response = self.stub.SetCameraPreset(
                scanner_pb2.SetPresetRequest(preset_name=preset_name)
            )
            if response.success:
                print(f"✓ Preset applied: {response.message}")
                return True
            print(f"✗ Failed to apply preset: {response.message}")
            return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False

    def get_camera_preset(self):
        """Get currently active camera preset and effective controls."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return None

        try:
            response = self.stub.GetCameraPreset(scanner_pb2.Empty())
            if response.success:
                info = {
                    'preset_name': response.preset_name,
                    'controls': dict(response.controls),
                }
                print(f"✓ Current preset: {response.preset_name}")
                return info
            print(f"✗ Failed to get preset: {response.message}")
            return None
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return None

    def list_camera_presets(self):
        """List available camera presets."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return None

        try:
            response = self.stub.ListCameraPresets(scanner_pb2.Empty())
            if response.success:
                presets = list(response.preset_names)
                print(f"✓ Available presets: {', '.join(presets) if presets else '(none)'}")
                return presets
            print(f"✗ Failed to list presets: {response.message}")
            return None
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return None

    def create_camera_preset(self, preset_name: str, controls: dict):
        """Create a camera preset from control values."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False

        try:
            response = self.stub.CreateCameraPreset(
                scanner_pb2.CreatePresetRequest(
                    preset_name=preset_name,
                    controls={k: str(v) for k, v in controls.items()}
                )
            )
            if response.success:
                print(f"✓ Preset created: {response.message}")
                return True
            print(f"✗ Failed to create preset: {response.message}")
            return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False

    def set_camera_controls(self, **controls):
        """Set camera controls directly using named kwargs."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False

        request_kwargs = {}
        for field in [
            'ae_enable', 'exposure_time', 'awb_enable', 'r_gain', 'b_gain',
            'brightness', 'contrast', 'sharpness', 'saturation'
        ]:
            if controls.get(field) is not None:
                request_kwargs[field] = controls[field]

        if not request_kwargs:
            print("✗ No camera controls provided")
            return False

        try:
            response = self.stub.SetCameraControls(
                scanner_pb2.CameraControlsRequest(**request_kwargs)
            )
            if response.success:
                print(f"✓ Controls applied: {response.message}")
                return True
            print(f"✗ Failed to set controls: {response.message}")
            return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False

    def stream_preview(self, fps: int = 10, quality: int = 75,
                      output_dir: str = 'output/preview', max_frames: int = 0):
        """
        Stream preview frames and save them as JPEG files.

        :param fps: requested stream fps
        :param quality: JPEG quality 1-100
        :param output_dir: directory where frames are stored
        :param max_frames: stop after this many frames (0 = infinite)
        """
        if not self.connected:
            print("✗ Not connected to scanner")
            return 0

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        saved = 0
        print(f"Streaming preview into: {out_path} (Ctrl+C to stop)")
        try:
            request = scanner_pb2.PreviewRequest(fps=fps, quality=quality)
            for frame in self.stub.StreamPreview(request):
                ts = frame.timestamp if frame.timestamp else int(time.time() * 1000)
                frame_path = out_path / f"preview_{ts}_{saved:05d}.jpg"
                frame_path.write_bytes(frame.image_data)
                saved += 1

                print(
                    f"Saved {frame_path.name} ({frame.width}x{frame.height})",
                    end='\r',
                    flush=True,
                )

                if max_frames > 0 and saved >= max_frames:
                    break

            print()
            print(f"✓ Preview stream finished. Frames saved: {saved}")
            return saved
        except grpc.RpcError as e:
            print(f"\n✗ Preview stream error: {e.details()}")
            return saved
        except KeyboardInterrupt:
            print(f"\n✓ Stopped preview stream. Frames saved: {saved}")
            return saved

    @staticmethod
    def detect_ssh_client_host():
        """Detect SSH client host using SSH_CONNECTION/SSH_CLIENT env vars."""
        ssh_connection = os.environ.get('SSH_CONNECTION', '').strip()
        if ssh_connection:
            parts = ssh_connection.split()
            if parts:
                return parts[0]

        ssh_client = os.environ.get('SSH_CLIENT', '').strip()
        if ssh_client:
            parts = ssh_client.split()
            if parts:
                return parts[0]

        return None

    def copy_file_to_host(self, file_path: str, target_host: str = None,
                          target_user: str = None, target_path: str = '.'):
        """
        Pull a file FROM the scanner (Pi) TO the local machine via scp.

        The file lives on the gRPC server (self.host). We pull it here so no
        SSH keys from Pi→PC are required; only PC→Pi (which the user already has).

        :param file_path:   Path of the file on the Pi.
        :param target_host: Unused — kept for API compatibility. The source host
                            is always self.host (the gRPC server).
        :param target_user: SSH username for the Pi (default: current local user).
        :param target_path: Local destination directory or path.
        """
        if shutil.which('scp') is None:
            print("✗ 'scp' command not found")
            return False

        scanner_host = self.host
        user_prefix = f"{target_user}@" if target_user else ""
        remote_src = f"{user_prefix}{scanner_host}:{file_path}"

        local_dest = Path(target_path).expanduser()
        local_dest.mkdir(parents=True, exist_ok=True)

        cmd = ['scp', '-p', remote_src, str(local_dest)]

        try:
            print(f"Pulling {Path(file_path).name} from {remote_src} → {local_dest} ...")
            print(f"  cmd: scp -p {remote_src} {local_dest}")
            completed = subprocess.run(cmd, check=False)
            if completed.returncode == 0:
                print(f"✓ File saved to {local_dest / Path(file_path).name}")
                return True

            print(f"✗ scp failed (exit code {completed.returncode})")
            return False
        except Exception as e:
            print(f"✗ Copy failed: {e}")
            return False

    def capture_and_copy_to_host(self, raw: bool = False, target_host: str = None,
                                 target_user: str = None, target_path: str = '.'):
        """Capture a frame and copy it to a remote host via scp."""
        captured_path = self.capture_frame(raw=raw)
        if not captured_path:
            return False

        return self.copy_file_to_host(
            file_path=captured_path,
            target_host=target_host,
            target_user=target_user,
            target_path=target_path,
        )
    
    def shutdown(self):
        """Shutdown the scanner and cleanup resources."""
        if not self.connected:
            print("✗ Not connected to scanner")
            return False
        
        try:
            response = self.stub.Shutdown(scanner_pb2.ShutdownRequest())
            if response.success:
                print(f"✓ Scanner shutdown: {response.message}")
                return True
            else:
                print(f"✗ Shutdown failed: {response.message}")
                return False
        except grpc.RpcError as e:
            print(f"✗ RPC error: {e.details()}")
            return False
    
    def stream_status(self, callback=None):
        """
        Stream real-time status updates.
        
        :param callback: Optional callback function(state, message, frame_count)
        """
        if not self.connected:
            print("✗ Not connected to scanner")
            return
        
        try:
            print("Streaming status updates (Ctrl+C to stop)...")
            for update in self.stub.StreamStatus(scanner_pb2.StatusRequest()):
                if callback:
                    callback(update.state, update.message, update.frame_count)
                else:
                    print(f"[{update.state}] Frames: {update.frame_count} | {update.message}")
                
                # Stop if scan is finished
                if update.state in ['finished', 'error']:
                    break
        except grpc.RpcError as e:
            print(f"✗ Stream error: {e.details()}")
        except KeyboardInterrupt:
            print("\n✓ Stopped streaming")
    
    def wait_for_completion(self, poll_interval: float = 1.0):
        """
        Wait for the scan to complete by polling status.
        
        :param poll_interval: Seconds between status checks
        """
        if not self.connected:
            print("✗ Not connected to scanner")
            return False
        
        print("Waiting for scan to complete...")
        try:
            while True:
                status = self.get_status()
                if status:
                    state = status['state']
                    frame_count = status['frame_count']
                    
                    print(f"[{state}] Frames captured: {frame_count}", end='\r')
                    
                    if state in ['finished', 'error']:
                        print()  # New line
                        if state == 'finished':
                            print(f"✓ Scan completed! Total frames: {frame_count}")
                            return True
                        else:
                            print(f"✗ Scan failed in error state")
                            return False
                
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n✗ Interrupted by user")
            return False


def main():
    """CLI for scanner control over local terminal or SSH."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Client')
    parser.add_argument('--host', default='localhost', help='Scanner host (default: localhost)')
    parser.add_argument('--port', type=int, default=50051, help='Scanner port (default: 50051)')
    parser.add_argument('--action', choices=[
        'scan', 'status', 'capture', 'stream', 'test', 'move-motor',
        'calc-gains', 'preset-get', 'preset-list', 'preset-set',
        'preset-create', 'set-controls', 'preview', 'copy'
    ],
                        default='scan', help='Action to perform')
    parser.add_argument('--raw', action='store_true', help='Capture RAW frames (for capture action)')
    parser.add_argument('--steps', type=int, help='Motor steps for move-motor (positive/negative)')
    parser.add_argument('--preset-name', help='Preset name for preset-set / preset-create')
    parser.add_argument('--controls', default='',
                        help='Comma-separated key=value controls (example: exposure_time=9000,brightness=0.1)')
    parser.add_argument('--ae-enable', type=int, choices=[0, 1], help='Set ae_enable control (0/1)')
    parser.add_argument('--exposure-time', type=int, help='Set exposure_time control')
    parser.add_argument('--awb-enable', type=int, choices=[0, 1], help='Set awb_enable control (0/1)')
    parser.add_argument('--r-gain', type=float, help='Set red gain')
    parser.add_argument('--b-gain', type=float, help='Set blue gain')
    parser.add_argument('--brightness', type=float, help='Set brightness')
    parser.add_argument('--contrast', type=float, help='Set contrast')
    parser.add_argument('--sharpness', type=float, help='Set sharpness')
    parser.add_argument('--saturation', type=float, help='Set saturation')
    parser.add_argument('--fps', type=int, default=10, help='Preview fps')
    parser.add_argument('--quality', type=int, default=75, help='Preview JPEG quality')
    parser.add_argument('--preview-dir', default='output/preview', help='Directory for preview frames')
    parser.add_argument('--max-frames', type=int, default=0,
                        help='Stop preview after N frames (0 = infinite)')
    parser.add_argument('--copy-to-host', action='store_true',
                        help='After capture, copy resulting file to host connected by SSH')
    parser.add_argument('--copy-path', default='.',
                        help='Remote destination path for scp (default: current directory on remote host)')
    parser.add_argument('--copy-user', default=None,
                        help='Remote username for scp (default: current username on remote host)')
    parser.add_argument('--copy-host', default=None,
                        help='Remote host for scp (default: auto-detect SSH client host)')
    parser.add_argument('--path', default=None,
                        help='File path for action=copy')
    
    args = parser.parse_args()
    
    client = ScannerClient(host=args.host, port=args.port)
    
    if not client.connect():
        sys.exit(1)
    
    try:
        controls_map = {}
        if args.controls:
            for item in args.controls.split(','):
                part = item.strip()
                if not part:
                    continue
                if '=' not in part:
                    print(f"✗ Invalid --controls entry: '{part}' (expected key=value)")
                    sys.exit(2)
                key, value = part.split('=', 1)
                controls_map[key.strip()] = value.strip()

        typed_controls = {
            'ae_enable': bool(args.ae_enable) if args.ae_enable is not None else None,
            'exposure_time': args.exposure_time,
            'awb_enable': bool(args.awb_enable) if args.awb_enable is not None else None,
            'r_gain': args.r_gain,
            'b_gain': args.b_gain,
            'brightness': args.brightness,
            'contrast': args.contrast,
            'sharpness': args.sharpness,
            'saturation': args.saturation,
        }

        for key, value in controls_map.items():
            if key in ['ae_enable', 'awb_enable']:
                typed_controls[key] = value.lower() in ('1', 'true', 'yes', 'on')
            elif key == 'exposure_time':
                typed_controls[key] = int(value)
            elif key in ['r_gain', 'b_gain', 'brightness', 'contrast', 'sharpness', 'saturation']:
                typed_controls[key] = float(value)
            else:
                # Keep unknown keys as raw strings to preserve forward compatibility.
                typed_controls[key] = value

        if args.action == 'scan':
            # Full scan workflow
            print("\n=== Starting Full Scan ===\n")
            if client.start_scan():
                client.wait_for_completion()
        
        elif args.action == 'status':
            # Get current status
            status = client.get_status()
            if status:
                print(f"\nScanner Status:")
                print(f"  State: {status['state']}")
                print(f"  Frames: {status['frame_count']}")
                print(f"  Message: {status['message']}")
        
        elif args.action == 'capture':
            # Capture single frame
            print(f"\n=== Capturing {'RAW' if args.raw else 'RGB'} Frame ===\n")
            if args.copy_to_host:
                client.capture_and_copy_to_host(
                    raw=args.raw,
                    target_host=args.copy_host,
                    target_user=args.copy_user,
                    target_path=args.copy_path,
                )
            else:
                client.capture_frame(raw=args.raw)
        
        elif args.action == 'stream':
            # Stream status updates
            print("\n=== Streaming Status Updates ===\n")
            client.stream_status()
        
        elif args.action == 'test':
            # Test workflow: start, pause, resume, wait
            print("\n=== Testing Scanner Workflow ===\n")
            
            print("1. Starting scan...")
            if not client.start_scan():
                sys.exit(1)
            
            time.sleep(3)
            
            print("\n2. Getting status...")
            status = client.get_status()
            if status:
                print(f"   State: {status['state']}, Frames: {status['frame_count']}")
            
            print("\n3. Pausing scan...")
            client.pause_scan()
            
            time.sleep(2)
            
            print("\n4. Resuming scan...")
            client.resume_scan()
            
            print("\n5. Waiting for completion...")
            client.wait_for_completion()

        elif args.action == 'move-motor':
            if args.steps is None:
                print("✗ --steps is required for action=move-motor")
                sys.exit(2)
            client.move_motor(args.steps)

        elif args.action == 'calc-gains':
            client.calculate_colour_gains()

        elif args.action == 'preset-get':
            preset_info = client.get_camera_preset()
            if preset_info:
                print(f"Preset: {preset_info['preset_name']}")
                for key, value in sorted(preset_info['controls'].items()):
                    print(f"  {key}={value}")

        elif args.action == 'preset-list':
            presets = client.list_camera_presets()
            if presets is not None:
                for name in presets:
                    print(f"- {name}")

        elif args.action == 'preset-set':
            if not args.preset_name:
                print("✗ --preset-name is required for action=preset-set")
                sys.exit(2)
            client.set_camera_preset(args.preset_name)

        elif args.action == 'preset-create':
            if not args.preset_name:
                print("✗ --preset-name is required for action=preset-create")
                sys.exit(2)
            preset_controls = {k: v for k, v in typed_controls.items() if v is not None}
            if not preset_controls:
                print("✗ preset-create requires at least one control via flags or --controls")
                sys.exit(2)
            client.create_camera_preset(args.preset_name, preset_controls)

        elif args.action == 'set-controls':
            client.set_camera_controls(**typed_controls)

        elif args.action == 'preview':
            client.stream_preview(
                fps=args.fps,
                quality=args.quality,
                output_dir=args.preview_dir,
                max_frames=args.max_frames,
            )

        elif args.action == 'copy':
            if not args.path:
                print("✗ --path is required for action=copy")
                sys.exit(2)
            client.copy_file_to_host(
                file_path=args.path,
                target_host=args.copy_host,
                target_user=args.copy_user,
                target_path=args.copy_path,
            )
    
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
