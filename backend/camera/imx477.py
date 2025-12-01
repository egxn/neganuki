"""IMX477 camera wrapper with preview / RAW / dual support.

This module provides a pragmatic implementation that works on a Raspberry Pi
with Picamera2. It aims to offer three modes:

- preview: fast RGB preview (RGB888)
- raw: configure camera to capture Bayer RAW frames
- dual: keep a fast preview mode but reconfigure to RAW when a raw capture is requested

Notes:
- Exact raw format strings and behaviour depend on the installed Picamera2 / libcamera
  version and the specific camera board. The code includes fallbacks and clear
  error messages where a platform-specific tweak might be needed.
- Saving to DNG is attempted via `rawpy` when available. As fallback, the raw
  Bayer array is saved as a 16-bit TIFF using `tifffile` if available.

Dependencies (optional): rawpy, tifffile
"""

from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
import tempfile
import os
import numpy as np
from loguru import logger

try:
    import cv2
except Exception:
    cv2 = None

try:
    from picamera2 import Picamera2
    from picamera2.encoders import JpegEncoder
    from picamera2 import Preview
except Exception as e:
    Picamera2 = None

if TYPE_CHECKING:
    from picamera2 import Picamera2 as Picamera2Type
else:
    Picamera2Type = Any

try:
    import libcamera
except Exception:
    libcamera = None

# Optional libs
try:
    import rawpy
except Exception:
    rawpy = None

try:
    import tifffile
except Exception:
    tifffile = None


DEFAULT_MANUAL_CONTROLS: Dict[str, Any] = {
    "AeEnable": False,
    "ExposureTime": 10000,
    "AwbEnable": False,
    "ColourGains": (1.5, 1.2),
    "Brightness": 0.0,
    "Contrast": 1.0,
    "Sharpness": 0.0,
    "Saturation": 1.0,
}


class IMX477Camera:
    def __init__(self, resolution: Tuple[int, int] = (4056, 3040)):
        self.resolution = resolution
        self.picam: Optional[Picamera2Type] = None
        self.mode = "preview"  # preview | raw | dual
        self._current_config = None

        if Picamera2:
            self.picam = Picamera2()

    # -------------------- Configuration helpers --------------------

    def _create_preview_config(self):
        """Create a typical preview/still RGB configuration.

        This is safe and fast for on-screen preview and conventional capture.
        """
        if not Picamera2:
            raise RuntimeError("Picamera2 not available")

        config = self.picam.create_still_configuration(
            main={"size": self.resolution, "format": "RGB888"}
        )
        return config

    def _create_raw_config(self):
        """Create a RAW (Bayer) configuration.

        Uses Picamera2's sensor_modes to find available RAW formats.
        IMX477 typically supports 12-bit RAW formats.
        """
        if not Picamera2:
            raise RuntimeError("Picamera2 not available")

        try:
            # Get available sensor modes to find RAW formats
            sensor_modes = self.picam.sensor_modes
            logger.info(f"Available sensor modes: {len(sensor_modes)}")
            
            # Look for RAW mode - typically the first mode is full resolution RAW
            raw_mode = None
            for mode in sensor_modes:
                logger.debug(f"Sensor mode: {mode}")
                # IMX477 RAW modes typically have format like 'SRGGB10' or 'SRGGB12'
                if 'format' in mode and any(x in str(mode.get('format', '')) for x in ['SRGGB', 'SBGGR', 'SGRBG', 'SGBRG', 'RGGB', 'BGGR']):
                    raw_mode = mode
                    logger.info(f"Found RAW mode: {mode}")
                    break
            
            if raw_mode:
                # Create configuration using the sensor's native RAW mode
                cfg = self.picam.create_still_configuration(
                    raw={"size": self.resolution},
                    display=None,
                    encode=None,
                )
                logger.info(f"Created RAW configuration with native sensor mode")
                return cfg
                
        except Exception as e:
            logger.warning(f"Failed to create RAW config using sensor modes: {e}")

        # Fallback: Try common RAW format strings
        raw_format_candidates = [
            "SRGGB12",  # IMX477 native 12-bit RAW
            "SRGGB10",  # 10-bit alternative
            "SBGGR12",
            "SBGGR10",
            "SGBRG12",
            "SGBRG10",
        ]

        for fmt in raw_format_candidates:
            try:
                logger.debug(f"Trying RAW format: {fmt}")
                cfg = self.picam.create_still_configuration(
                    raw={"size": self.resolution, "format": fmt},
                    display=None,
                )
                logger.info(f"Successfully created RAW config with format: {fmt}")
                return cfg
            except Exception as e:
                logger.debug(f"Format {fmt} not available: {e}")
                continue

        # Last resort: use raw without specifying format (let Picamera2 choose)
        try:
            cfg = self.picam.create_still_configuration(
                raw={"size": self.resolution},
                display=None,
            )
            logger.info("Created RAW configuration with auto-format")
            return cfg
        except Exception as e:
            logger.warning(f"Failed to create any RAW configuration: {e}")

        # If all else fails, fallback to RGB preview config
        logger.warning("No RAW format available. Falling back to RGB preview config.")
        return self._create_preview_config()

    def reconfigure(self, mode: str):
        """Reconfigure the camera to the requested mode.

        mode: 'preview', 'raw', or 'dual'

        For 'dual' we keep the camera in preview mode most of the time and
        temporarily switch to RAW when capture_raw() is called. For simplicity
        here we treat 'dual' as 'preview' during normal operation; capture_raw
        will reconfigure to raw/revert when needed.
        """
        if not self.picam:
            raise RuntimeError("Picamera2 not available on this system")

        logger.info(f"Reconfiguring camera from '{self.mode}' to '{mode}'")

        # stop safely
        try:
            logger.debug("Stopping camera...")
            self.picam.stop()
            logger.debug("Camera stopped successfully")
        except Exception as e:
            logger.debug(f"Camera stop returned: {e} (may already be stopped)")

        # Create configuration for requested mode
        if mode == "preview" or mode == "dual":
            logger.debug("Creating preview configuration...")
            self._current_config = self._create_preview_config()
        elif mode == "raw":
            logger.debug("Creating RAW configuration...")
            self._current_config = self._create_raw_config()
            
            # Check if we actually got a RAW config or fallback
            config_format = self._current_config.get("main", {}).get("format", "")
            if "RGB" in config_format:
                logger.warning("RAW configuration unavailable, using RGB fallback")
                raise RuntimeError(f"RAW mode not available on this system (got {config_format} instead)")
            else:
                logger.info(f"RAW configuration created with format: {config_format}")
        else:
            raise ValueError("Unknown mode: %s" % mode)

        # configure and start
        try:
            logger.debug(f"Applying configuration: {self._current_config}")
            self.picam.configure(self._current_config)
            logger.debug("Configuration applied, starting camera...")
            self.picam.start()
            logger.info(f"Camera started successfully in '{mode}' mode")
            self.mode = mode
            # Apply manual controls after the camera has started
            self.apply_manual_controls()
        except Exception as e:
            logger.error(f"Failed to configure and start camera: {e}", exc_info=True)
            raise

    # -------------------- Public API --------------------

    def initialize(self, mode: str = "preview"):
        """Initialize camera in given mode (preview | raw | dual)."""
        self.reconfigure(mode)
        logger.info("Camera initialized in mode: %s", mode)

    def shutdown(self):
        if self.picam:
            try:
                self.picam.stop()
            except Exception:
                pass
            self.picam = None
            logger.info("Camera stopped")

    def set_white_balance(self, gains: Tuple[float, float]):
        """Set fixed white balance gains (callable while camera running)."""
        if not self.picam:
            raise RuntimeError("Camera not initialized")
        controls = {"AwbEnable": False, "ColourGains": gains}
        self.picam.set_controls(controls)

    def set_exposure(self, exposure_us: int, analogue_gain: Optional[float] = None):
        """Set exposure time (microseconds) and optional analogue gain."""
        if not self.picam:
            raise RuntimeError("Camera not initialized")
        controls = {"AeEnable": False, "ExposureTime": exposure_us}
        if analogue_gain is not None:
            controls["AnalogueGain"] = analogue_gain
        self.picam.set_controls(controls)
        logger.debug("Manual exposure controls applied: %s", controls)

    def calculate_colour_gains(self, output_path: Optional[str] = None) -> Tuple[float, float]:
        """Capture a RAW frame, analyze Bayer pattern, and compute white balance gains.

        Returns (R_gain, B_gain) tuple suitable for ColourGains control.
        
        Steps:
        1. Capture RAW Bayer array directly
        2. Extract RGGB channels from Bayer pattern (assuming RGGB layout)
        3. Compute mean per channel
        4. Calculate gains relative to green: R_gain = mean_G / mean_R, B_gain = mean_G / mean_B
        """
        if not self.picam:
            raise RuntimeError("Camera not initialized")

        logger.info("Capturing RAW frame for colour gain calculation...")
        
        # Capture RAW and optionally save for debugging
        save_for_debug = output_path is not None
        result = self.capture_raw(save_dng=save_for_debug, dng_path=output_path)
        
        if result.get("bayer") is None:
            raise RuntimeError("Failed to capture RAW Bayer data")

        sensor_data = result["bayer"]
        logger.debug(f"Raw sensor data shape: {sensor_data.shape}, dtype: {sensor_data.dtype}")

        # Extract RGGB channels assuming standard Bayer pattern (R at 0,0; G at 0,1 and 1,0; B at 1,1)
        R = sensor_data[0::2, 0::2].astype(np.float64)
        G1 = sensor_data[0::2, 1::2].astype(np.float64)
        G2 = sensor_data[1::2, 0::2].astype(np.float64)
        B = sensor_data[1::2, 1::2].astype(np.float64)

        # Combine the two green channels
        G = (G1 + G2) / 2.0

        # Compute means
        mean_R = R.mean()
        mean_G = G.mean()
        mean_B = B.mean()

        logger.debug(f"Channel means: R={mean_R:.2f}, G={mean_G:.2f}, B={mean_B:.2f}")

        if mean_R == 0 or mean_B == 0:
            raise RuntimeError("Zero mean detected in R or B channel; cannot compute gains")

        # Calculate gains relative to green
        R_gain = mean_G / mean_R
        B_gain = mean_G / mean_B

        # Round to 3 decimals
        R_gain = round(R_gain, 3)
        B_gain = round(B_gain, 3)

        logger.info(f"Computed ColourGains: R_gain={R_gain}, B_gain={B_gain}")
        return (R_gain, B_gain)

    def apply_manual_controls(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        """Apply fixed manual controls for consistent capture settings.

        Parameters follow Picamera2 control names. Any overrides provided will
        update the defaults prior to applying them.
        """
        if not self.picam:
            logger.debug("apply_manual_controls called before camera initialization")
            return

        controls: Dict[str, Any] = dict(DEFAULT_MANUAL_CONTROLS)
        if overrides:
            controls.update(overrides)

        try:
            available: set[str] = set()
            if hasattr(self.picam, "camera_controls"):
                try:
                    available = set(self.picam.camera_controls.keys())
                except Exception:
                    available = set()

            unsupported = []
            manual_exposure_supported = bool(libcamera) and hasattr(
                getattr(libcamera, "controls", object()), "ExposureTimeMode"
            )
            manual_gain_supported = bool(libcamera) and hasattr(
                getattr(libcamera, "controls", object()), "AnalogueGainMode"
            )
            manual_awb_supported = bool(libcamera) and hasattr(
                getattr(libcamera, "controls", object()), "AwbMode"
            )

            if available:
                filtered_controls = {}
                for key, value in controls.items():
                    if key in available:
                        filtered_controls[key] = value
                    else:
                        unsupported.append(key)
                controls_to_apply = filtered_controls
            else:
                controls_to_apply = controls

            if not manual_exposure_supported:
                for key in ("AeEnable", "ExposureTime"):
                    if key in controls_to_apply:
                        controls_to_apply.pop(key, None)
                        if key not in unsupported:
                            unsupported.append(key)

            if not manual_gain_supported:
                for key in ("AnalogueGain", "GainEnable"):
                    if key in controls_to_apply:
                        controls_to_apply.pop(key, None)
                        if key not in unsupported:
                            unsupported.append(key)

            if not manual_awb_supported:
                for key in ("AwbEnable", "ColourGains"):
                    if key in controls_to_apply:
                        controls_to_apply.pop(key, None)
                        if key not in unsupported:
                            unsupported.append(key)

            if unsupported:
                logger.warning(
                    "Skipping unsupported controls for this pipeline: %s",
                    ", ".join(sorted(unsupported)),
                )

            if not controls_to_apply:
                logger.warning("No supported manual controls to apply on this pipeline")
                return

            self.picam.set_controls(controls_to_apply)
            logger.info(
                "Manual controls applied to Picamera2 instance: %s",
                controls_to_apply,
            )
        except Exception as exc:
            logger.warning("Failed to apply manual controls: %s", exc)

    def capture_frame(self) -> np.ndarray:
        """Capture an RGB frame (NumPy array)."""
        if not self.picam:
            raise RuntimeError("Camera not initialized")

        # If currently in raw-only mode, temporarily reconfigure to preview
        # to capture an RGB frame, or we capture and attempt to demosaic.
        if self.mode == "raw":
            logger.info("Temporarily reconfiguring to preview for capture_frame")
            self.reconfigure("preview")

        frame = self.picam.capture_array()
        # ensure array is a NumPy array
        return np.array(frame)

    def get_preview_stream_frame(self) -> Optional[np.ndarray]:
        """Get a single frame from the preview stream without stopping/starting.
        
        This is optimized for continuous streaming when camera is already running
        in preview mode. Returns a downscaled frame for faster network transmission.
        Returns None if camera is not in preview mode or not running.
        """
        if not self.picam:
            return None
        
        # Only stream in preview or dual mode
        if self.mode not in ("preview", "dual"):
            return None
        
        try:
            # Use capture_array for lightweight frame grab
            frame = self.picam.capture_array()
            
            # Downscale to 1/4 resolution for faster streaming (1014x760 instead of 4056x3040)
            # This makes encoding and network transfer much faster
            if cv2 is not None:
                height, width = frame.shape[:2]
                new_width = width // 4
                new_height = height // 4
                frame_small = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                return np.array(frame_small)
            else:
                # If cv2 not available, return full resolution
                return np.array(frame)
        except Exception as e:
            logger.debug(f"Preview stream frame capture failed: {e}")
            return None

    def capture_raw(self, save_dng: bool = True, dng_path: Optional[str] = None) -> dict:
        """Capture a RAW Bayer frame and optionally save to TIFF.
        
        Uses switch_mode_and_capture_array to temporarily capture RAW
        without fully reconfiguring the camera.
        """
        logger.info("Starting RAW capture (save_dng=%s, dng_path=%s)", save_dng, dng_path)
        
        if not self.picam:
            logger.error("RAW capture failed: Picamera2 not available")
            raise RuntimeError("Picamera2 not available")

        # Create a RAW configuration for the capture
        logger.info("Creating RAW configuration for capture...")
        raw_config = self._create_raw_config()
        
        # Check if we actually got RAW or fallback RGB
        config_format = raw_config.get("main", {}).get("format", "")
        logger.info(f"RAW config format: {config_format}")
        
        # Capture data and metadata using switch_mode
        raw_arr = None
        meta = None
        capture_success = False
        
        try:
            logger.info("Using switch_mode_and_capture_array for RAW capture...")
            
            # This method temporarily switches to RAW mode, captures, and switches back
            # It's designed exactly for this use case!
            request = self.picam.switch_mode_and_capture_array(raw_config)
            raw_arr = request
            
            # Try to get metadata if available
            try:
                meta = self.picam.capture_metadata()
            except:
                meta = {}
            
            if raw_arr is not None:
                logger.info("RAW capture successful: array shape=%s, dtype=%s", 
                           raw_arr.shape, raw_arr.dtype)
                capture_success = True
            else:
                logger.warning("switch_mode_and_capture_array returned None")
                
        except AttributeError:
            # switch_mode_and_capture_array not available, try alternative
            logger.warning("switch_mode_and_capture_array not available, trying manual stop/start method")
            
            try:
                # Stop preview
                logger.debug("Stopping camera for RAW capture...")
                self.picam.stop()
                
                # Configure for RAW
                logger.debug("Configuring for RAW...")
                self.picam.configure(raw_config)
                
                # Start in RAW mode
                logger.debug("Starting camera in RAW mode...")
                self.picam.start()
                
                # Capture
                logger.debug("Capturing RAW array...")
                request = self.picam.capture_request()
                raw_arr = request.make_array()
                meta = request.get_metadata()
                request.release()
                
                if raw_arr is not None:
                    logger.info("RAW capture successful: array shape=%s, dtype=%s", 
                               raw_arr.shape, raw_arr.dtype)
                    capture_success = True
                
                # Restart in preview mode
                logger.debug("Restarting in preview mode...")
                self.picam.stop()
                preview_config = self._create_preview_config()
                self.picam.configure(preview_config)
                self.picam.start()
                logger.info("Camera restored to preview mode")
                
            except Exception as e:
                logger.error("Manual RAW capture failed: %s", e, exc_info=True)
                
                # Try to restore preview mode
                try:
                    logger.info("Attempting to restore preview mode after error...")
                    self.picam.stop()
                    preview_config = self._create_preview_config()
                    self.picam.configure(preview_config)
                    self.picam.start()
                    logger.info("Preview mode restored")
                except Exception as restore_error:
                    logger.error("Failed to restore preview mode: %s", restore_error)
                    
        except Exception as e:
            logger.error("RAW capture failed: %s", e, exc_info=True)

        dng_saved_path = None
        if raw_arr is not None:
            logger.debug("Processing captured raw array...")
            bayer = self._normalize_bayer_to_uint16(raw_arr)
            logger.info("Raw array normalized to uint16: shape=%s", bayer.shape if bayer is not None else "None")

            if save_dng:
                logger.debug("Attempting to save raw data to file...")
                try:
                    if dng_path is None:
                        dng_path = os.path.join(tempfile.gettempdir(), "capture_{}.tiff".format(os.getpid()))
                        logger.debug("No path specified, using temporary path: %s", dng_path)
                    else:
                        # Ensure parent directory exists
                        parent_dir = os.path.dirname(dng_path)
                        if parent_dir and not os.path.exists(parent_dir):
                            logger.debug("Creating parent directory: %s", parent_dir)
                            os.makedirs(parent_dir, exist_ok=True)
                        logger.debug("Using specified path: %s", dng_path)

                    if tifffile is not None:
                        logger.debug("Saving with tifffile as 16-bit TIFF...")
                        tifffile.imwrite(dng_path, bayer.astype(np.uint16))
                        dng_saved_path = dng_path
                        logger.info("✓ Saved RAW Bayer as 16-bit TIFF: %s (size: %d bytes)", 
                                   dng_path, os.path.getsize(dng_path) if os.path.exists(dng_path) else 0)
                    elif cv2 is not None:
                        logger.warning("tifffile library not installed, using OpenCV to save as 16-bit PNG")
                        # Use cv2 to save as 16-bit PNG instead
                        png_path = dng_path.replace('.tiff', '.png') if dng_path.endswith('.tiff') else dng_path + '.png'
                        cv2.imwrite(png_path, bayer.astype(np.uint16))
                        dng_saved_path = png_path
                        logger.info("✓ Saved RAW Bayer as 16-bit PNG: %s (size: %d bytes)", 
                                   png_path, os.path.getsize(png_path) if os.path.exists(png_path) else 0)
                    else:
                        logger.error("Neither tifffile nor cv2 available, cannot save RAW data to image file")
                        # Fall back to numpy array
                        npy_path = dng_path.replace('.tiff', '.npy') if dng_path.endswith('.tiff') else dng_path + '.npy'
                        np.save(npy_path, bayer)
                        dng_saved_path = npy_path
                        logger.warning("Saved raw array as .npy: %s (size: %d bytes)", 
                                     npy_path, os.path.getsize(npy_path) if os.path.exists(npy_path) else 0)
                except Exception as e:
                    logger.error("Failed to save raw data to disk: %s", e, exc_info=True)
            else:
                logger.info("save_dng=False, skipping file save")

            result = {"bayer": bayer, "meta": meta, "dng_path": dng_saved_path}
            logger.info("RAW capture complete: bayer=%s, meta_keys=%s, saved_to=%s", 
                       "available" if bayer is not None else "None",
                       list(meta.keys()) if meta else "None",
                       dng_saved_path)
        else:
            logger.warning("Raw array is None, capture failed")
            result = {"bayer": None, "meta": meta, "dng_path": None}

        return result

    # -------------------- Utilities --------------------

    def _normalize_bayer_to_uint16(self, arr: np.ndarray) -> np.ndarray:
        """Normalize various Bayer array dtypes to uint16.

        Many raw Bayer outputs are 10-12 bit packed into 16-bit containers or
        sometimes 8-bit. This function attempts to standardize to uint16.
        """
        if arr is None:
            logger.warning("_normalize_bayer_to_uint16 received None array")
            return None

        arr = np.array(arr)
        logger.debug("Normalizing Bayer array: shape=%s, dtype=%s, min=%s, max=%s", 
                    arr.shape, arr.dtype, arr.min(), arr.max())
        
        if arr.dtype == np.uint16:
            # assume already fine
            logger.debug("Array already uint16, no conversion needed")
            return arr
        elif arr.dtype == np.uint8:
            # scale 8-bit to 16-bit
            logger.info("Converting uint8 to uint16 (bit shift left by 8)")
            result = (arr.astype(np.uint16) << 8)
            logger.debug("Conversion complete: new range [%d, %d]", result.min(), result.max())
            return result
        elif arr.dtype == np.float32 or arr.dtype == np.float64:
            # normalize float to 16-bit
            logger.info("Converting float to uint16 (normalizing to [0, 65535])")
            vmin = arr.min()
            vmax = arr.max()
            logger.debug("Float range: [%f, %f]", vmin, vmax)
            if vmax == vmin:
                logger.warning("Float array has constant value, returning zeros")
                return (arr * 0).astype(np.uint16)
            norm = (arr - vmin) / (vmax - vmin)
            result = (norm * 65535).astype(np.uint16)
            logger.debug("Conversion complete: new range [%d, %d]", result.min(), result.max())
            return result
        else:
            # unknown type: cast and scale conservatively
            logger.warning("Unknown dtype %s, attempting conservative conversion", arr.dtype)
            try:
                max_val = arr.max()
                logger.debug("Array max value: %d", max_val)
                if max_val <= 255:
                    logger.info("Max value <= 255, treating as 8-bit (shift left by 8)")
                    return (arr.astype(np.uint16) << 8)
                elif max_val <= 4095:
                    # 12-bit -> scale to 16-bit
                    logger.info("Max value <= 4095, treating as 12-bit (shift left by 4)")
                    return (arr.astype(np.uint16) << 4)
                else:
                    logger.info("Max value > 4095, direct cast to uint16")
                    return arr.astype(np.uint16)
            except Exception as e:
                logger.error("Conversion failed, falling back to direct cast: %s", e)
                return arr.astype(np.uint16)

    # Small helper to test availability
    @staticmethod
    def is_raw_support_available() -> bool:
        return Picamera2 is not None
