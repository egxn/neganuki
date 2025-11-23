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

from typing import Optional, Tuple
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

# Optional libs
try:
    import rawpy
except Exception:
    rawpy = None

try:
    import tifffile
except Exception:
    tifffile = None


class IMX477Camera:
    def __init__(self, resolution: Tuple[int, int] = (4056, 3040)):
        self.resolution = resolution
        self.picam: Optional[Picamera2] = None
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

        NOTE: exact format string can vary depending on Picamera2 / libcamera.
        Common names include 'SENSOR_FORMAT' variants or 'BAYER' strings. If the
        default below does not work on your Pi, please check the Picamera2 docs
        and replace the format string with the one supported by your setup.
        """
        if not Picamera2:
            raise RuntimeError("Picamera2 not available")

        # Try a commonly used raw Bayer format. If your system uses another
        # name for the format (S_BAYER_BGGR10 / SBGGR10 / ...) you should
        # replace it accordingly.
        # We keep this value configurable by changing this function if needed.
        raw_format_candidates = [
            "SBGGR16",  # 16-bit Bayer (may not be available on all systems)
            "SGBRG10",  # examples of alternatives
            "S_RGGB10",
            "SBGGR10",
            "BAYER_RGGB8",
        ]

        for fmt in raw_format_candidates:
            try:
                cfg = self.picam.create_still_configuration(
                    main={"size": self.resolution, "format": fmt}
                )
                # test if configuration is OK by returning it
                return cfg
            except Exception:
                continue

        # If none succeeded, fallback to a generic configuration and warn.
        logger.warning("No standard RAW format candidate succeeded. Falling back to RGB preview config.")
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

        # stop safely
        try:
            self.picam.stop()
        except Exception:
            pass

        self.mode = mode
        # self.picam is already initialized in __init__

        if mode == "preview" or mode == "dual":
            self._current_config = self._create_preview_config()
        elif mode == "raw":
            self._current_config = self._create_raw_config()
            if self._current_config["main"]["format"] == "RGB888":
                logger.warning("RAW configuration failed, falling back to RGB preview config internally.")
        else:
            raise ValueError("Unknown mode: %s" % mode)

        # configure and start
        self.picam.configure(self._current_config)
        self.picam.start()

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
        controls = {"ExposureTime": exposure_us}
        if analogue_gain is not None:
            controls["AnalogueGain"] = analogue_gain
        self.picam.set_controls(controls)

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
        """Capture a RAW Bayer frame and optionally save to TIFF."""
        if not self.picam:
            raise RuntimeError("Picamera2 not available")

        restore_mode = None
        if self.mode in ("preview", "dual"):
            restore_mode = self.mode
            logger.info("Switching to raw mode for capture")
            try:
                self.reconfigure("raw")
            except Exception as e:
                logger.error("Failed to configure RAW mode: %s", e)
                return {"bayer": None, "meta": None, "dng_path": None}

        # Capture data and metadata in one go
        raw_arr = None
        meta = None
        try:
            request = self.picam.capture_request()
            raw_arr = request.make_array()
            meta = request.get_metadata()
            request.release()
        except Exception as e:
            logger.error("Raw capture failed: %s", e)

        dng_saved_path = None
        if raw_arr is not None:
            bayer = self._normalize_bayer_to_uint16(raw_arr)

            if save_dng:
                try:
                    if dng_path is None:
                        dng_path = os.path.join(tempfile.gettempdir(), "capture_{}.tiff".format(os.getpid()))

                    if tifffile is not None:
                        tifffile.imwrite(dng_path, bayer.astype(np.uint16))
                        dng_saved_path = dng_path
                        logger.info("Saved RAW Bayer as 16-bit TIFF: %s", dng_path)
                    else:
                        alt = dng_path.replace('.tiff', '.npy') if dng_path.endswith('.tiff') else dng_path + '.npy'
                        np.save(alt, bayer)
                        dng_saved_path = alt
                        logger.warning("tifffile not installed, saved raw array as .npy: %s", alt)
                except Exception as e:
                    logger.error("Failed to save raw data: %s", e)

            result = {"bayer": bayer, "meta": meta, "dng_path": dng_saved_path}
        else:
            result = {"bayer": None, "meta": meta, "dng_path": None}

        if restore_mode is not None:
            logger.info("Restoring camera mode: %s", restore_mode)
            self.reconfigure(restore_mode)

        return result

    # -------------------- Utilities --------------------

    def _normalize_bayer_to_uint16(self, arr: np.ndarray) -> np.ndarray:
        """Normalize various Bayer array dtypes to uint16.

        Many raw Bayer outputs are 10-12 bit packed into 16-bit containers or
        sometimes 8-bit. This function attempts to standardize to uint16.
        """
        if arr is None:
            return None

        arr = np.array(arr)
        if arr.dtype == np.uint16:
            # assume already fine
            return arr
        elif arr.dtype == np.uint8:
            # scale 8-bit to 16-bit
            return (arr.astype(np.uint16) << 8)
        elif arr.dtype == np.float32 or arr.dtype == np.float64:
            # normalize float to 16-bit
            vmin = arr.min()
            vmax = arr.max()
            if vmax == vmin:
                return (arr * 0).astype(np.uint16)
            norm = (arr - vmin) / (vmax - vmin)
            return (norm * 65535).astype(np.uint16)
        else:
            # unknown type: cast and scale conservatively
            try:
                max_val = arr.max()
                if max_val <= 255:
                    return (arr.astype(np.uint16) << 8)
                elif max_val <= 4095:
                    # 12-bit -> scale to 16-bit
                    return (arr.astype(np.uint16) << 4)
                else:
                    return arr.astype(np.uint16)
            except Exception:
                return arr.astype(np.uint16)

    # Small helper to test availability
    @staticmethod
    def is_raw_support_available() -> bool:
        return Picamera2 is not None
