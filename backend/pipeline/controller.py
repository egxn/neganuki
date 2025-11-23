from pathlib import Path
import logging
import cv2

from backend.fsm import ScannerFSM
from backend.camera import IMX477Camera
from backend.motor import Stepper28BYJ48
from backend.pipeline.crop import Cropper
from backend.pipeline.stitcher import Stitcher
from backend.pipeline.evaluator import CaptureEvaluator


class PipelineController:
    """
    Orchestrates the entire scanning workflow:
    - Controls FSM
    - Captures frames
    - Evaluates overlap
    - Crops relevant region
    - Stitches frames
    - Moves the stepper
    - Provides interface for gRPC
    """

    def __init__(
        self,
        output_dir: str,
        camera_config: dict = None,
        motor_pins: dict = None,
        callbacks: dict = None,
        max_frames: int = 100,
        detect_film_end: bool = True,
    ):
        self.log = logging.getLogger("PipelineController")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.max_frames = max_frames
        self.detect_film_end = detect_film_end

        # --- Core components ---
        self.camera = IMX477Camera(resolution=camera_config.get('resolution', (4056, 3040)) if camera_config else (4056, 3040))
        self.motor = Stepper28BYJ48(**(motor_pins or {}))
        self.cropper = Cropper()  # No config required, has default
        self.stitcher = Stitcher()
        self.evaluator = CaptureEvaluator()

        # --- Storage ---
        self.frames = []
        self.current_stitched = None

        # --- FSM ---
        self.fsm = ScannerFSM(callbacks=self._fsm_callbacks(callbacks))

    # ----------------------------------------------------------------------
    # FSM CALLBACKS
    # ----------------------------------------------------------------------

    def _fsm_callbacks(self, user_callbacks):
        """Merge internal callbacks with user-provided ones."""
        cb = user_callbacks.copy() if user_callbacks else {}

        cb.update(
            {
                "on_enter_initializing": self._on_enter_initializing,
                "on_enter_capturing": self._on_enter_capturing,
                "on_enter_evaluating": self._on_enter_evaluating,
                "on_enter_stitching": self._on_enter_stitching,
                "on_enter_advancing": self._on_enter_advancing,
                "on_enter_checking_completion": self._on_enter_checking_completion,
                "on_enter_paused": self._on_enter_paused,
                "on_enter_finished": self._on_enter_finished,
                "on_enter_error": self._on_enter_error,
                "on_enter_camera_error": self._on_enter_camera_error,
                "on_enter_motor_error": self._on_enter_motor_error,
            }
        )
        return cb

    # ----------------------------------------------------------------------
    # ENGINE CALLS FOR EACH STATE
    # ----------------------------------------------------------------------

    def _on_enter_initializing(self):
        self.log.info("Initializing scanner...")
        
        # Initialize camera
        try:
            self.camera.initialize(mode="preview")
            self.log.info("Camera initialized successfully")
        except Exception as e:
            self.log.error(f"Camera initialization failed: {e}")
            self.fsm.fail()
            return
        
        # Reset stitcher for new scan
        self.stitcher.reset()
        
        self.fsm.init_done()

    def _on_enter_capturing(self):
        self.log.info("Capturing frame...")
        self.fsm.reset_retry_count()  # Reset retry counter for new capture
        
        try:
            frame = self.camera.capture_frame()
        except Exception as e:
            self.log.error(f"Camera capture failed: {e}")
            self.fsm.camera_fail()
            return

        if frame is None:
            self.log.error("Camera returned empty frame")
            self.fsm.camera_fail()
            return

        self.frames.append(frame)
        self.fsm.capture_done()

    def _on_enter_evaluating(self):
        self.log.info("Evaluating frame quality...")

        curr_frame = self.frames[-1]
        
        # Check frame quality (sharpness, exposure, etc.)
        is_acceptable = self.evaluator.is_frame_acceptable(curr_frame)

        if not is_acceptable:
            self.log.warning("Frame quality insufficient, retrying...")
            if self.fsm.is_retry_allowed():
                self.fsm.increment_retry_count()
                self.fsm.retry_capture()
            else:
                self.log.error("Max retries reached, failing...")
                self.fsm.fail()
        else:
            self.log.info("Frame accepted")
            self.fsm.accept_capture()

    def _on_enter_stitching(self):
        self.log.info("Stitching frames...")

        self.current_stitched = self.stitcher.stitch(self.frames)

        if self.current_stitched is None:
            self.log.error("Stitch failed.")
            self.fsm.fail()
            return

        out_path = self.output_dir / "stitched_temp.png"
        self.stitcher.save(self.current_stitched, out_path)

        self.log.info(f"Temporary stitched saved to {out_path}")
        self.fsm.stitch_done()

    def _on_enter_advancing(self):
        self.log.info("Advancing stepper...")

        try:
            ok = self.motor.step(50)  # You can later parameterize this
        except Exception as e:
            self.log.error(f"Motor failed with exception: {e}")
            self.fsm.motor_fail()
            return

        if not ok:
            self.log.error("Stepper failed.")
            self.fsm.motor_fail()
            return

        self.fsm.advance_done()

    def _on_enter_checking_completion(self):
        self.log.info("Checking if scan is complete...")
        
        # Check 1: Maximum frame count reached
        if len(self.frames) >= self.max_frames:
            self.log.info(f"Max frames ({self.max_frames}) reached, scan complete!")
            self.fsm.scan_complete()
            return

        # Check 2: Film end detection (if enabled)
        if self.detect_film_end:
            curr_frame = self.frames[-1]
            
            # Convert to grayscale for analysis
            if len(curr_frame.shape) == 3:
                gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = curr_frame
            
            # Check if frame is mostly black (end of film)
            mean_brightness = gray.mean()
            black_threshold = 15.0  # Adjust based on your setup
            
            if mean_brightness < black_threshold:
                self.log.info("Film end detected (dark frame), scan complete!")
                self.fsm.scan_complete()
                return
            
            # Check if frame has very little content/features
            # This could indicate leader or end of film
            edges = self.evaluator._detect_edges(gray)
            edge_density = edges.mean()
            
            if edge_density < 0.01:  # Very few edges detected
                self.log.info("Film end detected (no content), scan complete!")
                self.fsm.scan_complete()
                return
        
        # Otherwise, continue scanning
        self.log.info("More frames needed, continuing scan...")
        self.fsm.more_frames()

    def _on_enter_paused(self):
        self.log.info("Scan paused")
        # Optionally save intermediate state, release hardware resources, etc.

    def _on_enter_finished(self):
        self.log.info("Scan finished successfully")
        # Cleanup, save final results, etc.
        if self.current_stitched is not None:
            final_path = self.output_dir / "final_scan.png"
            self.stitcher.save(self.current_stitched, final_path)
            self.log.info(f"Final scan saved to {final_path}")

    def _on_enter_error(self):
        self.log.error("Entered error state")
        # Cleanup, notify user, attempt recovery, etc.

    def _on_enter_camera_error(self):
        self.log.error("Camera error occurred")
        # Attempt camera recovery
        try:
            self.camera.shutdown()
            self.camera.initialize()
            self.log.info("Camera reinitialized, attempting recovery")
            self.fsm.recover_camera()
        except Exception as e:
            self.log.error(f"Camera recovery failed: {e}")
            self.fsm.fail()

    def _on_enter_motor_error(self):
        self.log.error("Motor error occurred")
        # Attempt motor recovery
        try:
            self.motor.reinitialize()
            self.log.info("Motor reinitialized, attempting recovery")
            self.fsm.recover_motor()
        except Exception as e:
            self.log.error(f"Motor recovery failed: {e}")
            self.fsm.fail()

    # ----------------------------------------------------------------------
    # PUBLIC API FOR gRPC OR LOCAL USE
    # ----------------------------------------------------------------------

    def start_scan(self):
        """Start a new scan session."""
        self.frames = []
        self.current_stitched = None
        self.stitcher.reset()  # Reset stitcher for new scan
        self.fsm.start()

    def pause_scan(self):
        """Pause the current scan."""
        if self.fsm.state in ['capturing', 'evaluating', 'stitching', 'advancing']:
            self.fsm.pause()
            self.log.info("Scan paused")
        else:
            self.log.warning(f"Cannot pause from state: {self.fsm.state}")

    def resume_scan(self):
        """Resume a paused scan."""
        if self.fsm.state == 'paused':
            self.fsm.resume()
            self.log.info("Scan resumed")
        else:
            self.log.warning(f"Cannot resume from state: {self.fsm.state}")

    def finalize(self, output_filename="final_scan.png"):
        """Called when external logic decides scanning is done."""
        if self.current_stitched is None:
            self.log.warning("Trying to finalize without stitched frame.")

        final_path = self.output_dir / output_filename
        self.stitcher.save(self.current_stitched, final_path)
        self.fsm.abort()  # Changed from finish() to abort()
        return final_path

    def current_state(self):
        return self.fsm.state

    def abort(self):
        self.fsm.abort()
