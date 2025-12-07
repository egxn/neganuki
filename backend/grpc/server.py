# backend/grpc/server.py
import time
import grpc
import cv2
import numpy as np
import logging
from concurrent import futures
from pathlib import Path
from typing import Iterator

# Setup logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GRPCServer")

# Try multiple possible locations for generated protos (adjust if needed)
try:
    from backend.grpc.generated import scanner_pb2, scanner_pb2_grpc
    logger.info("✓ Protobuf modules loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import protobuf modules: {e}")
    logger.error("Run: poetry run generate-protos")
    scanner_pb2 = None
    scanner_pb2_grpc = None
except Exception as e:
    logger.error(f"Unexpected error loading protobuf modules: {e}")
    scanner_pb2 = None
    scanner_pb2_grpc = None

# Import the PipelineController implemented previously
try:
    from backend.pipeline.controller import PipelineController
except Exception:
    from backend.pipeline.controller import PipelineController  # try again for linter

# Setup logging
logger = logging.getLogger("GRPCServer")

# Helper to save NumPy image as PNG
def _save_frame_as_png(frame: np.ndarray, out_dir: Path, prefix: str = "frame") -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = out_dir / f"{prefix}_{ts}.png"
    # Convert BGR (OpenCV) to RGB for correct colors if needed; cv2.imwrite expects BGR, so keep as-is.
    cv2.imwrite(str(path), frame)
    return str(path)


class ScannerServiceImpl:
    """
    Implementation wrapper that will be adapted to the generated servicer class below.
    Exposes methods that match proto names.
    """

    def __init__(self, controller: PipelineController):
        self.controller = controller
        self.logger = logging.getLogger("ScannerServiceImpl")

    def StartCapture(self, request):
        """Start the FSM-driven full capture pipeline (non-blocking; FSM runs callbacks)."""
        try:
            self.logger.info("StartCapture called")
            self.controller.start_scan()
            return True, "Scan started successfully"
        except Exception as e:
            self.logger.error(f"StartCapture failed: {e}")
            return False, f"Start failed: {e}"

    def GetStatus(self, request):
        try:
            state = self.controller.current_state()
            frame_count = len(self.controller.frames)
            return True, state, "", frame_count
        except Exception as e:
            self.logger.error(f"GetStatus failed: {e}")
            return False, "error", f"Error: {e}", 0

    def PauseScan(self, request):
        """Pause the current scan."""
        try:
            self.logger.info("PauseScan called")
            self.controller.pause_scan()
            return True, "Scan paused"
        except Exception as e:
            self.logger.error(f"PauseScan failed: {e}")
            return False, f"Pause failed: {e}"

    def ResumeScan(self, request):
        """Resume a paused scan."""
        try:
            self.logger.info("ResumeScan called")
            self.controller.resume_scan()
            return True, "Scan resumed"
        except Exception as e:
            self.logger.error(f"ResumeScan failed: {e}")
            return False, f"Resume failed: {e}"

    def CaptureFrame(self, request):
        """
        Capture a single frame immediately (bypassing FSM).
        Returns path to saved frame.
        """
        try:
            self.logger.info(f"CaptureFrame called (raw={request.raw})")
            
            if request.raw:
                # Capture RAW frame
                self.logger.info("Starting RAW frame capture...")
                self.logger.debug("Current camera mode: %s", self.controller.camera.mode)
                
                # Generate path in output directory (same as RGB captures)
                # Use .tiff extension (will be converted to .png if tifffile not available)
                self.controller.output_dir.mkdir(parents=True, exist_ok=True)
                ts = int(time.time() * 1000)
                raw_path = self.controller.output_dir / f"capture_raw_{ts}.tiff"
                self.logger.info(f"RAW will be saved to: {raw_path} (or .png if tifffile not available)")
                
                result = self.controller.camera.capture_raw(save_dng=True, dng_path=str(raw_path))
                
                self.logger.debug("RAW capture result: bayer=%s, meta=%s, dng_path=%s",
                                 "available" if result.get('bayer') is not None else "None",
                                 "available" if result.get('meta') is not None else "None",
                                 result.get('dng_path'))
                
                if result['dng_path'] is None:
                    self.logger.error("RAW capture failed: dng_path is None")
                    # Check if raw_arr was captured but save failed
                    if result.get('bayer') is not None:
                        self.logger.error("Bayer data was captured but file save failed")
                    else:
                        self.logger.error("Camera capture itself failed, no raw data available")
                    return False, "", "RAW capture failed - no file saved"
                
                self.logger.info(f"✓ RAW frame captured successfully: {result['dng_path']}")
                return True, result['dng_path'], "RAW frame captured"
            else:
                # Capture preview frame
                self.logger.info("Starting RGB frame capture...")
                frame = self.controller.camera.capture_frame()
                
                if frame is None:
                    self.logger.error("RGB capture failed: camera returned None")
                    return False, "", "No frame captured"
                
                self.logger.debug("Frame captured: shape=%s, dtype=%s", frame.shape, frame.dtype)
                out_path = _save_frame_as_png(frame, self.controller.output_dir, prefix="capture")
                self.logger.info(f"✓ RGB frame saved to: {out_path}")
                return True, out_path, "Frame captured"
                
        except Exception as e:
            self.logger.error(f"CaptureFrame failed with exception: {e}", exc_info=True)
            return False, "", f"Capture failed: {e}"

    def Shutdown(self, request):
        try:
            self.logger.info("Shutdown called")
            
            # If paused, resume first to allow proper shutdown
            if self.controller.current_state() == 'paused':
                self.controller.resume_scan()
            
            self.controller.abort()
            
            # Cleanup resources
            try:
                self.controller.camera.shutdown()
                self.logger.info("Camera shutdown complete")
            except Exception as e:
                self.logger.warning(f"Camera shutdown warning: {e}")
            
            try:
                self.controller.motor.cleanup()
                self.logger.info("Motor cleanup complete")
            except Exception as e:
                self.logger.warning(f"Motor cleanup warning: {e}")
            
            return True, "Shutdown completed"
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            return False, f"Shutdown failed: {e}"

    def StreamPreview(self, request) -> Iterator:
        """
        Stream live preview frames as JPEG encoded data.
        Only works when scanner is in idle state.
        Yields PreviewFrame messages until client disconnects.
        """
        try:
            fps = request.fps if request.fps > 0 else 10
            quality = request.quality if 1 <= request.quality <= 100 else 75
            frame_interval = 1.0 / fps
            
            self.logger.info(f"StreamPreview started (fps={fps}, quality={quality})")
            
            while True:
                start_time = time.time()
                
                # Only stream if in idle state
                current_state = self.controller.current_state()
                if current_state != 'idle':
                    self.logger.debug(f"Preview streaming paused - state: {current_state}")
                    time.sleep(0.5)
                    continue
                
                # Get frame from camera
                frame = self.controller.camera.get_preview_stream_frame()
                
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Encode as JPEG
                try:
                    # OpenCV expects BGR, convert from RGB if needed
                    if len(frame.shape) == 3 and frame.shape[2] == 3:
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    else:
                        frame_bgr = frame
                    
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                    success, buffer = cv2.imencode('.jpg', frame_bgr, encode_param)
                    
                    if not success:
                        self.logger.warning("Failed to encode frame as JPEG")
                        continue
                    
                    jpeg_data = buffer.tobytes()
                    height, width = frame.shape[:2]
                    timestamp = int(time.time() * 1000)
                    
                    yield jpeg_data, width, height, timestamp
                    
                except Exception as e:
                    self.logger.error(f"Frame encoding error: {e}")
                    continue
                
                # Rate limiting
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            self.logger.error(f"StreamPreview error: {e}")
            return

    def MoveMotor(self, request):
        """
        Move the motor manually by a specified number of steps.
        Positive steps = forward, negative steps = backward.
        Only works when scanner is in idle state.
        """
        try:
            steps = request.steps
            
            # Check if scanner is idle
            current_state = self.controller.current_state()
            if current_state != 'idle':
                return False, f"Cannot move motor in state: {current_state}. Must be in idle state."
            
            if steps == 0:
                return False, "Steps cannot be zero"
            
            direction = "forward" if steps > 0 else "backward"
            abs_steps = abs(steps)
            
            self.logger.info(f"MoveMotor called: {abs_steps} steps {direction}")
            
            # Move the motor using step method
            # direction: 1 = forward (CW), -1 = backward (CCW)
            motor_direction = 1 if steps > 0 else -1
            success = self.controller.motor.step(abs_steps, motor_direction)
            
            if not success:
                return False, f"Motor step failed"
            
            return True, f"Motor moved {abs_steps} steps {direction}"
            
        except Exception as e:
            self.logger.error(f"MoveMotor failed: {e}")
            return False, f"Motor move failed: {e}"
    
    def CalculateColourGains(self, request):
        """
        Calculate white balance colour gains from a RAW capture.
        Returns R and B gains relative to G.
        """
        try:
            self.logger.info("CalculateColourGains called")
            
            # Check if scanner is idle
            current_state = self.controller.current_state()
            if current_state != 'idle':
                return False, f"Cannot calculate gains in state: {current_state}. Must be in idle state.", 0.0, 0.0
            
            # Call camera's calculate_colour_gains method
            r_gain, b_gain = self.controller.camera.calculate_colour_gains()
            
            self.logger.info(f"✓ Colour gains calculated: R={r_gain:.3f}, B={b_gain:.3f}")
            return True, f"Gains calculated: R={r_gain:.3f}, B={b_gain:.3f}", r_gain, b_gain
            
        except Exception as e:
            self.logger.error(f"CalculateColourGains failed: {e}")
            return False, f"Calculation failed: {e}", 0.0, 0.0
    
    def SetCameraPreset(self, request):
        """Set camera controls to a named preset."""
        try:
            preset_name = request.preset_name
            self.logger.info(f"SetCameraPreset called: '{preset_name}'")
            
            # Check if scanner is idle
            current_state = self.controller.current_state()
            if current_state != 'idle':
                return False, f"Cannot change preset in state: {current_state}. Must be in idle state."
            
            # Log available presets for debugging
            available = self.controller.camera.get_available_presets()
            self.logger.debug(f"Available presets: {available}")
            
            # Apply the preset
            success = self.controller.camera.set_preset(preset_name)
            
            if success:
                return True, f"Preset '{preset_name}' applied successfully"
            else:
                return False, f"Unknown preset: {preset_name}"
                
        except Exception as e:
            self.logger.error(f"SetCameraPreset failed: {e}", exc_info=True)
            return False, f"Failed to set preset: {e}"
    
    def GetCameraPreset(self, request):
        """Get information about the current camera preset."""
        try:
            self.logger.info("GetCameraPreset called")
            
            preset_info = self.controller.camera.get_preset_info()
            preset_name = preset_info.get("name", "unknown")
            controls = preset_info.get("controls", {})
            
            # Convert controls to string representation with proper formatting
            controls_str = {}
            for k, v in controls.items():
                if k == "ColourGains" and isinstance(v, tuple):
                    # Format without spaces for easier parsing
                    controls_str[k] = f"{v[0]},{v[1]}"
                else:
                    controls_str[k] = str(v)
            
            return True, f"Current preset: {preset_name}", preset_name, controls_str
            
        except Exception as e:
            self.logger.error(f"GetCameraPreset failed: {e}")
            return False, f"Failed to get preset: {e}", "", {}
    
    def ListCameraPresets(self, request):
        """List all available camera presets."""
        try:
            self.logger.info("ListCameraPresets called")
            
            presets = self.controller.camera.get_available_presets()
            
            return True, f"Found {len(presets)} presets", presets
            
        except Exception as e:
            self.logger.error(f"ListCameraPresets failed: {e}")
            return False, f"Failed to list presets: {e}", []
    
    def CreateCameraPreset(self, request):
        """Create a new custom camera preset."""
        try:
            preset_name = request.preset_name
            controls_str = dict(request.controls)
            
            self.logger.info(f"CreateCameraPreset called: {preset_name}")
            
            # Check if scanner is idle
            current_state = self.controller.current_state()
            if current_state != 'idle':
                return False, f"Cannot create preset in state: {current_state}. Must be in idle state."
            
            # Parse controls from string format
            controls = {}
            for key, value_str in controls_str.items():
                # Parse different types
                if key in ("AeEnable", "AwbEnable"):
                    controls[key] = value_str.lower() in ("true", "1", "yes")
                elif key == "ColourGains":
                    # Parse tuple format: "(1.5, 1.2)" or "1.5,1.2"
                    value_str = value_str.strip("()").replace(" ", "")
                    parts = value_str.split(",")
                    if len(parts) != 2:
                        return False, f"ColourGains must have 2 values, got: {value_str}"
                    controls[key] = (float(parts[0]), float(parts[1]))
                elif key == "ExposureTime":
                    controls[key] = int(value_str)
                else:
                    controls[key] = float(value_str)
            
            # Create the preset
            success = self.controller.camera.create_custom_preset(preset_name, controls)
            
            if success:
                return True, f"Preset '{preset_name}' created successfully"
            else:
                return False, f"Failed to create preset '{preset_name}'"
                
        except Exception as e:
            self.logger.error(f"CreateCameraPreset failed: {e}")
            return False, f"Failed to create preset: {e}"

    def SetCameraControls(self, request):
        """Set camera controls directly without using a preset."""
        try:
            self.logger.info("SetCameraControls called")
            
            # Build controls dict from request
            controls = {
                "AeEnable": request.ae_enable,
                "ExposureTime": request.exposure_time,
                "AwbEnable": request.awb_enable,
                "ColourGains": (request.r_gain, request.b_gain),
                "Brightness": request.brightness,
                "Contrast": request.contrast,
                "Sharpness": request.sharpness,
                "Saturation": request.saturation,
            }
            
            self.logger.info(f"Applying controls: {controls}")
            self.controller.camera.apply_manual_controls(overrides=controls)
            
            return True, "Camera controls applied successfully"
            
        except Exception as e:
            self.logger.error(f"SetCameraControls failed: {e}")
            return False, f"Failed to set camera controls: {e}"


# If generated gRPC classes exist, map them to service implementation
if scanner_pb2 is not None and scanner_pb2_grpc is not None:

    class GRPCServer:
        def __init__(self, controller: PipelineController, host: str = "[::]", port: int = 50051):
            self.controller = controller
            self.host = host
            self.port = port
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=6))
            self._impl = ScannerServiceImpl(controller)

            # Define and attach the servicer dynamically
            class Servicer(scanner_pb2_grpc.ScannerServiceServicer):
                # Implement methods matching proto
                def StartCapture(inner_self, request, context):
                    ok, msg = self._impl.StartCapture(request)
                    return scanner_pb2.CaptureResponse(success=ok, message=msg)

                def GetStatus(inner_self, request, context):
                    ok, state, msg, frame_count = self._impl.GetStatus(request)
                    return scanner_pb2.StatusResponse(
                        success=ok,
                        state=state,
                        message=msg,
                        frame_count=frame_count
                    )

                def PauseScan(inner_self, request, context):
                    ok, msg = self._impl.PauseScan(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)

                def ResumeScan(inner_self, request, context):
                    ok, msg = self._impl.ResumeScan(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)

                def CaptureFrame(inner_self, request, context):
                    ok, path, msg = self._impl.CaptureFrame(request)
                    return scanner_pb2.FrameCaptureResponse(success=ok, path=path, message=msg)

                def Shutdown(inner_self, request, context):
                    ok, msg = self._impl.Shutdown(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)

                def StreamStatus(inner_self, request, context):
                    # Server streaming of status updates until client cancels
                    try:
                        while not context.is_active():
                            break
                        
                        while context.is_active():
                            state = self._impl.controller.current_state()
                            frame_count = len(self._impl.controller.frames)
                            update = scanner_pb2.StateUpdate(
                                state=state,
                                message="",
                                frame_count=frame_count
                            )
                            yield update
                            time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"StreamStatus error: {e}")
                        return

                def StreamPreview(inner_self, request, context):
                    # Server streaming of preview frames
                    try:
                        for jpeg_data, width, height, timestamp in self._impl.StreamPreview(request):
                            if not context.is_active():
                                break
                            
                            frame = scanner_pb2.PreviewFrame(
                                image_data=jpeg_data,
                                width=width,
                                height=height,
                                timestamp=timestamp
                            )
                            yield frame
                    except Exception as e:
                        logger.error(f"StreamPreview gRPC error: {e}")
                        return

                def MoveMotor(inner_self, request, context):
                    ok, msg = self._impl.MoveMotor(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)
                
                def CalculateColourGains(inner_self, request, context):
                    ok, msg, r_gain, b_gain = self._impl.CalculateColourGains(request)
                    return scanner_pb2.ColourGainsResponse(
                        success=ok, 
                        message=msg, 
                        r_gain=r_gain, 
                        b_gain=b_gain
                    )
                
                def SetCameraPreset(inner_self, request, context):
                    ok, msg = self._impl.SetCameraPreset(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)
                
                def GetCameraPreset(inner_self, request, context):
                    ok, msg, preset_name, controls = self._impl.GetCameraPreset(request)
                    return scanner_pb2.PresetInfoResponse(
                        success=ok,
                        message=msg,
                        preset_name=preset_name,
                        controls=controls
                    )
                
                def ListCameraPresets(inner_self, request, context):
                    ok, msg, presets = self._impl.ListCameraPresets(request)
                    return scanner_pb2.PresetListResponse(
                        success=ok,
                        message=msg,
                        preset_names=presets
                    )
                
                def CreateCameraPreset(inner_self, request, context):
                    ok, msg = self._impl.CreateCameraPreset(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)
                
                def SetCameraControls(inner_self, request, context):
                    ok, msg = self._impl.SetCameraControls(request)
                    return scanner_pb2.BasicResponse(success=ok, message=msg)

            scanner_pb2_grpc.add_ScannerServiceServicer_to_server(Servicer(), self.server)
            self.server.add_insecure_port(f"{self.host}:{self.port}")

        def start(self):
            self.server.start()
            logger.info(f"gRPC server started on {self.host}:{self.port}")

        def stop(self, grace=5):
            self.server.stop(grace)
            logger.info("gRPC server stopped")

else:
    # Fallback stub if generated protos are missing
    class GRPCServer:
        def __init__(self, controller, host="[::]", port=50051):
            raise RuntimeError("Generated protobuf modules not found. Generate them before running the server.")


# Convenience CLI runner
def run_server(controller: PipelineController, host: str = "[::]", port: int = 50051):
    server = GRPCServer(controller, host, port)
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description='Film Scanner gRPC Server')
    parser.add_argument('--host', default='[::]', help='Server host (default: [::])')
    parser.add_argument('--port', type=int, default=50051, help='Server port (default: 50051)')
    parser.add_argument('--output-dir', default='./output', help='Output directory for scans')
    parser.add_argument('--motor-pins', default='17,18,27,22', 
                        help='Motor GPIO pins IN1-IN4 (default: 17,18,27,22)')
    parser.add_argument('--motor-delay', type=float, default=0.002,
                        help='Delay between motor steps in seconds (default: 0.002)')
    
    args = parser.parse_args()
    
    # Parse motor pins
    motor_pins = tuple(map(int, args.motor_pins.split(',')))
    
    # Import required modules
    try:
        from backend.pipeline.controller import PipelineController
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure you have generated the protobuf files: poetry run generate-protos")
        exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Initializing scanner components...")
    
    try:
        # Prepare motor configuration
        motor_config = {
            'pins': motor_pins,
            'delay': args.motor_delay
        }
        
        # Prepare camera configuration
        camera_config = {
            'resolution': (4056, 3040)
        }
        
        # Initialize pipeline controller (it creates camera and motor internally)
        controller = PipelineController(
            output_dir=str(output_dir),
            camera_config=camera_config,
            motor_pins=motor_config,
            max_frames=100,
            detect_film_end=True
        )
        logger.info("✓ Pipeline controller initialized")
        
        # Start gRPC server
        logger.info(f"Starting gRPC server on {args.host}:{args.port}")
        run_server(controller, host=args.host, port=args.port)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
