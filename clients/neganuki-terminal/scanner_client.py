"""
Raspberry Pi Scanner Client
============================

Interactive client to control the film scanner via gRPC.
Provides both CLI and programmatic interfaces.
"""

import grpc
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
    """Interactive CLI for the scanner client."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Film Scanner Client')
    parser.add_argument('--host', default='localhost', help='Scanner host (default: localhost)')
    parser.add_argument('--port', type=int, default=50051, help='Scanner port (default: 50051)')
    parser.add_argument('--action', choices=['scan', 'status', 'capture', 'stream', 'test'],
                        default='scan', help='Action to perform')
    parser.add_argument('--raw', action='store_true', help='Capture RAW frames (for capture action)')
    
    args = parser.parse_args()
    
    client = ScannerClient(host=args.host, port=args.port)
    
    if not client.connect():
        sys.exit(1)
    
    try:
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
    
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
