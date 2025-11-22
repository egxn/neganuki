"""
Pipeline package for the DIY film scanner.

This package contains the components responsible for:
- Cutting each frame region (crop)
- Stitching multiple captures into a linear mosaic (stitcher)
- Evaluating whether a new capture is required (evaluator)
- Managing the entire step-by-step capture/scanning process (controller)
"""

from .crop import Cropper
from .stitcher import Stitcher
from .evaluator import CaptureEvaluator

# PipelineController may be implemented later; pre-declare for stable imports.
try:
    from .controller import PipelineController
except ImportError:
    PipelineController = None  # Allows imports before implementation


__all__ = [
    "Cropper",
    "Stitcher",
    "CaptureEvaluator",
    "PipelineController",
]
