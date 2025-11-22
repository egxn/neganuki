import cv2
import numpy as np

class CaptureEvaluator:
    """
    Evaluates frame quality and determines overlap for film scanning.
    
    Provides two main functions:
    1. Quality check: is_frame_acceptable() - checks sharpness, exposure, etc.
    2. Overlap analysis: needs_more_captures() - checks if frames overlap sufficiently
    """

    def __init__(
        self,
        strip_ratio: float = 0.12,          # fraction of image height to compare
        diff_threshold: float = 8.0,        # minimal mean abs-diff to consider "new area"
        orb_threshold: int = 40,            # minimal new keypoints to detect new content
        sharpness_threshold: float = 100.0, # Laplacian variance threshold for blur detection
        brightness_min: float = 30.0,       # minimum acceptable mean brightness
        brightness_max: float = 225.0       # maximum acceptable mean brightness
    ):
        self.strip_ratio = strip_ratio
        self.diff_threshold = diff_threshold
        self.orb_threshold = orb_threshold
        self.sharpness_threshold = sharpness_threshold
        self.brightness_min = brightness_min
        self.brightness_max = brightness_max
        self.orb = cv2.ORB_create(nfeatures=1000)

    def is_frame_acceptable(self, frame: np.ndarray) -> bool:
        """
        Check if a single frame meets quality standards.
        
        Returns True if frame is acceptable (sharp, well-exposed).
        Returns False if frame should be recaptured.
        """
        if frame is None or frame.size == 0:
            return False

        # Convert to grayscale for analysis
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # 1. Check sharpness using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < self.sharpness_threshold:
            return False  # Too blurry

        # 2. Check exposure (brightness)
        mean_brightness = np.mean(gray)
        
        if mean_brightness < self.brightness_min or mean_brightness > self.brightness_max:
            return False  # Under or overexposed

        return True

    def needs_more_captures(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> bool:
        """
        Returns True if another capture is necessary.
        False if current frame already contains enough new information.
        """

        if prev_frame is None or curr_frame is None:
            return True

        # Resize to same size if small differences exist
        if prev_frame.shape != curr_frame.shape:
            curr_frame = cv2.resize(curr_frame, (prev_frame.shape[1], prev_frame.shape[0]))

        h, w = prev_frame.shape[:2]
        strip_h = int(h * self.strip_ratio)

        prev_strip = prev_frame[-strip_h:, :]
        curr_strip = curr_frame[:strip_h, :]

        # Convert to grayscale
        prev_g = cv2.cvtColor(prev_strip, cv2.COLOR_BGR2GRAY)
        curr_g = cv2.cvtColor(curr_strip, cv2.COLOR_BGR2GRAY)

        # A. Mean absolute difference
        diff = np.mean(np.abs(prev_g.astype(np.float32) - curr_g.astype(np.float32)))

        if diff >= self.diff_threshold:
            # Sufficient difference => new information => no more captures needed
            return False

        # B. Keypoint backup detection
        kp1, des1 = self.orb.detectAndCompute(prev_g, None)
        kp2, des2 = self.orb.detectAndCompute(curr_g, None)

        if des1 is None or des2 is None:
            # If ORB fails, be conservative: continue capturing
            return True

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)

        # New keypoints = keypoints not well-matched
        new_points = len(kp2) - len(matches)

        if new_points >= self.orb_threshold:
            return False  # enough new points => frame contains new content

        # Otherwise more capture is needed
        return True

    def _detect_edges(self, gray_frame: np.ndarray) -> np.ndarray:
        """
        Helper method to detect edges in a grayscale frame.
        Returns binary edge map normalized to [0, 1].
        """
        edges = cv2.Canny(gray_frame, 50, 150)
        return edges / 255.0  # Normalize to [0, 1]
