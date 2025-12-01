"""Simple stitching experiment runner.

This script loads all images under ``data/sample`` (sorted alphabetically),
rotates each frame by -90 degrees, aligns them using a selectable backend,
and saves a stitched composite into ``output``.

Usage:
    poetry run python -m decoupled_algorithms.scan --method ecc

Methods:
    - ecc   (default): Enhanced Correlation Coefficient alignment
    - orb   : ORB feature matching + homography
    - sift  : SIFT feature matching + homography (requires OpenCV with contrib)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import logging
import sys
import time
from pathlib import Path
from typing import List

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
LOGGER = logging.getLogger(__name__)
LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

def _load_images(data_dir: Path) -> List[np.ndarray]:
    paths = sorted(p for p in data_dir.glob("*") if p.is_file())
    if not paths:
        raise FileNotFoundError(f"No images found in {data_dir}. Drop sample frames there.")

    images = []
    for path in paths:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Failed to read image: {path}")
        images.append(img)
    return images


def _rotate_minus_90(image: np.ndarray) -> np.ndarray:
    return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)


def _align_ecc(
    reference: np.ndarray,
    target: np.ndarray,
    *,
    max_iterations: int = 750,
    epsilon: float = 1e-6,
) -> np.ndarray:
    base_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)

    base_gray = base_gray.astype(np.float32) / 255.0
    target_gray = target_gray.astype(np.float32) / 255.0

    warp_mode = cv2.MOTION_HOMOGRAPHY
    warp_matrix = np.eye(3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iterations, epsilon)

    start = time.perf_counter()
    try:
        correlation, warp_matrix = cv2.findTransformECC(
            base_gray,
            target_gray,
            warp_matrix,
            warp_mode,
            criteria,
            None,
            5,
        )
    except cv2.error as exc:
        raise RuntimeError(f"ECC alignment failed: {exc}") from exc
    finally:
        duration = time.perf_counter() - start
        LOGGER.debug("ECC alignment took %.3fs", duration)

    LOGGER.debug("ECC correlation score %.6f", correlation)

    return warp_matrix


def _align_orb(reference: np.ndarray, target: np.ndarray) -> np.ndarray:
    orb = cv2.ORB_create(5000)
    base_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)

    kps1, des1 = orb.detectAndCompute(base_gray, None)
    kps2, des2 = orb.detectAndCompute(target_gray, None)
    if des1 is None or des2 is None:
        raise RuntimeError("ORB failed to find descriptors.")

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    if len(matches) < 10:
        raise RuntimeError("Not enough ORB matches for homography.")

    matches = sorted(matches, key=lambda m: m.distance)[:200]
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, status = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None or status is None or status.sum() < 10:
        raise RuntimeError("Homography estimation failed for ORB matches.")

    return H.astype(np.float32)


def _align_sift(reference: np.ndarray, target: np.ndarray) -> np.ndarray:
    if not hasattr(cv2, "SIFT_create"):
        raise RuntimeError("SIFT is unavailable. Install opencv-contrib-python to enable it.")

    sift = cv2.SIFT_create()
    base_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)

    kps1, des1 = sift.detectAndCompute(base_gray, None)
    kps2, des2 = sift.detectAndCompute(target_gray, None)
    if des1 is None or des2 is None:
        raise RuntimeError("SIFT failed to find descriptors.")

    matcher = cv2.BFMatcher()
    knn_matches = matcher.knnMatch(des1, des2, k=2)

    good_matches = []
    for m, n in knn_matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    if len(good_matches) < 10:
        raise RuntimeError("Not enough SIFT matches for homography.")

    src_pts = np.float32([kps1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    H, status = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None or status is None or status.sum() < 10:
        raise RuntimeError("Homography estimation failed for SIFT matches.")

    return H.astype(np.float32)


ALIGNERS = {
    "ecc": _align_ecc,
    "orb": _align_orb,
    "sift": _align_sift,
}


def _render_progress(label: str, current: int, total: int) -> None:
    if total <= 0:
        return

    bar_len = 30
    fraction = current / total
    fraction = max(0.0, min(1.0, fraction))
    filled = int(bar_len * fraction)
    bar = "#" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r{label} [{bar}] {current}/{total}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def _configure_logging(level: str) -> None:
    numeric = LOG_LEVELS.get(level.lower())
    if numeric is None:
        raise ValueError(f"Unknown log level '{level}'. Choose from {list(LOG_LEVELS)}")

    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=numeric, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger().setLevel(numeric)
    LOGGER.debug("Logging configured at %s", level.upper())


def _average_composite(images: List[np.ndarray], masks: List[np.ndarray]) -> np.ndarray:
    if not images:
        raise ValueError("No images provided for compositing.")

    height, width = images[0].shape[:2]
    accum = np.zeros((height, width, 3), dtype=np.float32)
    counts = np.zeros((height, width, 1), dtype=np.float32)

    for img, mask in zip(images, masks):
        if img.shape[:2] != (height, width):
            raise ValueError("All images must share the same canvas size for compositing.")
        if mask.shape != (height, width):
            raise ValueError("Mask shape mismatch during compositing.")

        mask_f = mask.astype(np.float32)[..., None]
        accum += img.astype(np.float32) * mask_f
        counts += mask_f

    zero_mask = counts == 0.0
    counts[zero_mask] = 1.0
    averaged = accum / counts
    averaged[zero_mask.repeat(3, axis=2)] = 0.0
    return np.clip(averaged, 0.0, 255.0).astype(np.uint8)


def run(
    method: str = "ecc",
    *,
    log_level: str | None = None,
    ecc_max_iter: int | None = None,
    ecc_epsilon: float | None = None,
) -> Path:
    method = method.lower()
    if method not in ALIGNERS:
        raise ValueError(f"Unknown method '{method}'. Choose from {list(ALIGNERS)}")

    if log_level:
        _configure_logging(log_level)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = _load_images(DATA_DIR)
    LOGGER.info("Loaded %d frames from %s", len(images), DATA_DIR)
    rotated = [_rotate_minus_90(img) for img in images]
    LOGGER.info("Applied -90 degree rotation to all frames")

    base = rotated[0]
    warp_matrices: List[np.ndarray] = [np.eye(3, dtype=np.float32)]

    align_fn = ALIGNERS[method]
    if method == "ecc":
        max_iter = ecc_max_iter or 750
        eps = ecc_epsilon or 1e-6

        def ecc_wrapper(base_img: np.ndarray, target_img: np.ndarray) -> np.ndarray:
            return _align_ecc(base_img, target_img, max_iterations=max_iter, epsilon=eps)

        align_fn = ecc_wrapper
        LOGGER.debug("Configured ECC max_iter=%d epsilon=%g", max_iter, eps)
    else:
        LOGGER.debug("Using default parameters for %s aligner", method.upper())

    LOGGER.info("Using %s aligner", method.upper())
    total_to_align = len(rotated) - 1
    progress_label = f"Aligning with {method.upper()}"

    for idx in range(1, len(rotated)):
        reference_img = rotated[idx - 1]
        reference_warp = warp_matrices[idx - 1]
        target_img = rotated[idx]

        _render_progress(progress_label, idx - 1, total_to_align)
        LOGGER.debug("Aligning frame %d/%d (target #%d relative to #%d)", idx, total_to_align, idx + 1, idx)

        local_warp = align_fn(reference_img, target_img).astype(np.float32)
        cumulative_warp = reference_warp @ local_warp
        warp_matrices.append(cumulative_warp)

        _render_progress(progress_label, idx, total_to_align)

    height, width = base.shape[:2]
    corners = np.array(
        [[0.0, 0.0], [width, 0.0], [width, height], [0.0, height]],
        dtype=np.float32,
    )
    transformed_corners = []
    for warp in warp_matrices:
        pts = cv2.perspectiveTransform(corners[None, :, :], warp)
        transformed_corners.append(pts[0])

    all_corners = np.vstack(transformed_corners)
    min_x = float(np.floor(all_corners[:, 0].min()))
    min_y = float(np.floor(all_corners[:, 1].min()))
    max_x = float(np.ceil(all_corners[:, 0].max()))
    max_y = float(np.ceil(all_corners[:, 1].max()))

    canvas_width = int(np.ceil(max_x - min_x))
    canvas_height = int(np.ceil(max_y - min_y))
    if canvas_width <= 0 or canvas_height <= 0:
        raise RuntimeError("Computed invalid composite canvas size.")

    translate = np.array(
        [[1.0, 0.0, -min_x], [0.0, 1.0, -min_y], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )
    LOGGER.info("Composite canvas size %dx%d before orientation correction", canvas_width, canvas_height)

    warped_images: List[np.ndarray] = []
    masks: List[np.ndarray] = []
    ones_mask = np.ones((height, width), dtype=np.uint8)

    for idx, (img, warp) in enumerate(zip(rotated, warp_matrices), start=1):
        warp_shifted = translate @ warp
        try:
            warped = cv2.warpPerspective(img, warp_shifted, (canvas_width, canvas_height), flags=cv2.INTER_LINEAR)
            mask = cv2.warpPerspective(ones_mask, warp_shifted, (canvas_width, canvas_height), flags=cv2.INTER_NEAREST)
        except cv2.error as exc:
            raise RuntimeError(f"Warping frame {idx} failed: {exc}") from exc
        warped_images.append(warped)
        masks.append(mask)

    stitched = _average_composite(warped_images, masks)
    LOGGER.info("Composite generated from %d aligned frames", len(warped_images))

    stitched = cv2.rotate(stitched, cv2.ROTATE_90_CLOCKWISE)
    LOGGER.info(
        "Restored stitched image to original orientation (%dx%d)",
        stitched.shape[1],
        stitched.shape[0],
    )

    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"neganuki_{method}_{timestamp}.tiff"
    success = cv2.imwrite(str(out_path), stitched)
    if not success:
        raise RuntimeError(f"Failed to write output image to {out_path}")
    LOGGER.info("Saved stitched output to %s", out_path)
    print(f"Saved stitched output to {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Neganuki stitching playground")
    parser.add_argument("--method", choices=ALIGNERS.keys(), default="ecc", help="Alignment method")
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS.keys(),
        default="info",
        help="Logging verbosity",
    )
    parser.add_argument(
        "--ecc-max-iter",
        type=int,
        default=750,
        help="Maximum iterations for ECC (only applies when --method ecc)",
    )
    parser.add_argument(
        "--ecc-epsilon",
        type=float,
        default=1e-6,
        help="Convergence epsilon for ECC (only applies when --method ecc)",
    )
    args = parser.parse_args()

    run(
        args.method,
        log_level=args.log_level,
        ecc_max_iter=args.ecc_max_iter,
        ecc_epsilon=args.ecc_epsilon,
    )


if __name__ == "__main__":
    main()
