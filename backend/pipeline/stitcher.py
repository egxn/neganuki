import cv2
import numpy as np
import logging
from typing import List, Optional
from pathlib import Path


class Stitcher:
    """
    Mosaics multiple frames taken sequentially along the film
    using feature-based image stitching.

    Designed for vertical or horizontal linear scans but works for general cases.
    """

    def __init__(self, detector: str = "ORB"):
        """
        detector: "ORB" or "SIFT"
        """
        self.log = logging.getLogger("Stitcher")
        
        if detector.upper() == "SIFT":
            self.detector = cv2.SIFT_create()
        else:
            # ORB is free, fast, and good for consistent exposures
            self.detector = cv2.ORB_create(nfeatures=2000)

        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.frames: List[np.ndarray] = []  # original frames
        self.transforms: List[np.ndarray] = []  # cumulative transforms

        # Start with identity transform
        self.transforms.append(np.eye(3, dtype=np.float32))

    def reset(self):
        """Remove all frames and restart stitching session."""
        self.frames.clear()
        self.transforms = [np.eye(3, dtype=np.float32)]

    def add_frame(self, frame: np.ndarray):
        """
        Add a new frame to the stitcher.
        If it is the first frame, no stitching is done yet.
        """
        if frame is None or frame.size == 0:
            return

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if not self.frames:
            self.frames.append(frame)
            return

        # Previous frame
        prev_frame = self.frames[-1]
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        # Find features
        kp1, des1 = self.detector.detectAndCompute(prev_gray, None)
        kp2, des2 = self.detector.detectAndCompute(frame_gray, None)

        if des1 is None or des2 is None:
            self.log.warning("Could not compute descriptors")
            self.frames.append(frame)
            # Keep previous transform (duplicate)
            self.transforms.append(self.transforms[-1].copy())
            return

        # Match
        matches = self.matcher.match(des1, des2)
        matches = sorted(matches, key=lambda m: m.distance)

        if len(matches) < 10:
            self.log.warning("Not enough matches, appending frame without transform")
            self.frames.append(frame)
            self.transforms.append(self.transforms[-1].copy())
            return

        # Extract matched keypoints
        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        # Find homography
        H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)

        if H is None:
            self.log.warning("Homography failed")
            self.frames.append(frame)
            self.transforms.append(self.transforms[-1].copy())
            return

        # Cumulative transform = previous * H
        cumulative = self.transforms[-1] @ H
        self.transforms.append(cumulative)
        self.frames.append(frame)

    def stitch(self, frames: List[np.ndarray]) -> Optional[np.ndarray]:
        """
        Stitch a list of frames and return the final mosaic.
        This is a convenience method that resets, adds all frames, and builds.
        
        :param frames: List of frames to stitch
        :return: Stitched mosaic image or None if failed
        """
        self.reset()
        for frame in frames:
            self.add_frame(frame)
        return self.build()

    def build(self) -> Optional[np.ndarray]:
        """
        Build the final stitched image.
        Returns None if no images exist.
        """
        if not self.frames:
            return None

        if len(self.frames) == 1:
            return self.frames[0]

        # Compute output bounds
        corners = []
        for frame, H in zip(self.frames, self.transforms):
            h, w = frame.shape[:2]
            pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
            warped = cv2.perspectiveTransform(pts, H)
            corners.append(warped)

        corners = np.concatenate(corners, axis=0)
        [xmin, ymin] = np.min(corners[:, 0, :], axis=0).astype(int)
        [max_x, max_y] = np.max(corners[:, 0, :], axis=0).astype(int)

        # Output size
        width = max_x - xmin
        height = max_y - ymin

        # Translation to avoid negative indices
        translate = np.array([[1, 0, -xmin],
                              [0, 1, -ymin],
                              [0, 0, 1]], dtype=np.float32)

        # Build empty canvas
        mosaic = np.zeros((height, width, 3), dtype=np.uint8)

        # Warp each image and blend
        for frame, H in zip(self.frames, self.transforms):
            warp_mat = translate @ H
            warped = cv2.warpPerspective(frame, warp_mat, (width, height))

            mask = (warped.sum(axis=2) > 0)
            mosaic[mask] = warped[mask]

        return mosaic
    
    def save(self, image: np.ndarray, path: Path) -> bool:
        """
        Save stitched image to disk.
        
        :param image: Image to save
        :param path: Output path
        :return: True if successful, False otherwise
        """
        if image is None:
            self.log.error("Cannot save None image")
            return False
        
        try:
            cv2.imwrite(str(path), image)
            self.log.info(f"Saved stitched image to {path}")
            return True
        except Exception as e:
            self.log.error(f"Failed to save image: {e}")
            return False
