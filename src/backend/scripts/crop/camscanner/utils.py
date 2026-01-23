"""
Utility functions and wrappers for existing codebase components.

Provides clean interface to contour detection, fold detection, and image I/O.
"""

import sys
import os
from pathlib import Path
from typing import Union, Tuple, Optional

import cv2
import numpy as np
from PIL import Image

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import from existing codebase
from src.contour_detector.detect import find_page_contour
from src.contour_detector.transform import warp_image
from src.contour_detector.preprocess import preprocess_image
from src.fold_detection import detect_fold_brightness_profile
from src.image_io import load_image as _load_image_original


def load_image(image_input: Union[str, Path, np.ndarray, Image.Image]) -> np.ndarray:
    """
    Load and normalize image from various input types.

    Args:
        image_input: File path, numpy array, or PIL Image

    Returns:
        np.ndarray: BGR image (OpenCV format)
    """
    if isinstance(image_input, (str, Path)):
        # Load from file path
        return _load_image_original(str(image_input))
    elif isinstance(image_input, np.ndarray):
        # Already numpy array
        return image_input.copy()
    elif isinstance(image_input, Image.Image):
        # Convert PIL to OpenCV
        img_array = np.array(image_input)
        # Convert RGB to BGR if needed
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        return img_array
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")


def detect_page_boundary(
    img: np.ndarray, debug: bool = False
) -> Tuple[Optional[np.ndarray], Optional[float]]:
    """
    Detect document page boundary (4 corners).

    Args:
        img: Input image
        debug: Enable debug output

    Returns:
        tuple: (contour, angle) or (None, None) if not found
            - contour: 4-point contour in clockwise order
            - angle: Estimated rotation angle in degrees
    """
    try:
        # Preprocess image
        thresh, border_rgb = preprocess_image(img)

        # Find page contour
        contour, angle = find_page_contour(
            thresh, show_step_by_step=debug, original_image=img
        )

        if contour is None:
            return None, None

        return contour, angle

    except Exception as e:
        if debug:
            print(f"[Utils] Page boundary detection failed: {e}")
        return None, None


def apply_perspective_correction(
    img: np.ndarray,
    contour: np.ndarray,
    border: int = 150,
    debug: bool = False
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Apply perspective correction to document.

    Args:
        img: Input image
        contour: 4-point contour
        border: Border pixels to add
        debug: Enable debug output

    Returns:
        tuple: (warped_image, transform_matrix) or (None, None)
    """
    try:
        warped, crop_no_rotation, transform_M = warp_image(
            img, contour, border_pixels=border, scale_factor=1.0
        )
        # warp_image returns rotation matrix M, not perspective transform matrix
        # For fold coordinate transformation, we can't use this directly
        # Return None as transform matrix (will handle fold coords differently)
        return warped, None
    except Exception as e:
        if debug:
            print(f"[Utils] Perspective correction failed: {e}")
        return None, None


def detect_fold_brightness(
    img: np.ndarray, side: str = "center", debug: bool = False
) -> Tuple[Optional[int], float]:
    """
    Detect fold using brightness profile analysis.

    Args:
        img: Input image
        side: Expected fold location ('left', 'right', 'center')
        debug: Enable debug output

    Returns:
        tuple: (fold_x_position, quality_score)
    """
    try:
        fold_x, angle, slope, intercept, quality = detect_fold_brightness_profile(
            img, side=side, debug=debug
        )
        return fold_x, quality
    except Exception as e:
        if debug:
            print(f"[Utils] Brightness fold detection failed: {e}")
        return None, 0.0


def calculate_aspect_ratio(contour: np.ndarray) -> float:
    """
    Calculate aspect ratio of contour bounding box.

    Args:
        contour: 4-point contour

    Returns:
        float: aspect ratio (width / height)
    """
    points = contour.reshape(-1, 2)
    x_coords = points[:, 0]
    y_coords = points[:, 1]

    width = np.max(x_coords) - np.min(x_coords)
    height = np.max(y_coords) - np.min(y_coords)

    if height == 0:
        return 0.0

    return width / height


def get_contour_bounds(contour: np.ndarray) -> Tuple[int, int, int, int]:
    """
    Get bounding box of contour.

    Args:
        contour: 4-point contour

    Returns:
        tuple: (min_x, min_y, max_x, max_y)
    """
    points = contour.reshape(-1, 2)
    min_x = int(np.min(points[:, 0]))
    max_x = int(np.max(points[:, 0]))
    min_y = int(np.min(points[:, 1]))
    max_y = int(np.max(points[:, 1]))

    return min_x, min_y, max_x, max_y


def get_page_center_x(contour: np.ndarray) -> int:
    """
    Get center X coordinate of page contour.

    Args:
        contour: 4-point contour

    Returns:
        int: Center X coordinate
    """
    points = contour.reshape(-1, 2)
    return int(np.mean(points[:, 0]))


def get_page_width(contour: np.ndarray) -> int:
    """
    Get width of page contour.

    Args:
        contour: 4-point contour

    Returns:
        int: Width in pixels
    """
    points = contour.reshape(-1, 2)
    return int(np.max(points[:, 0]) - np.min(points[:, 0]))


def is_valid_contour(contour: np.ndarray, img_shape: tuple) -> bool:
    """
    Check if contour is valid (not too small or too large).

    Args:
        contour: 4-point contour
        img_shape: Image shape (height, width, channels)

    Returns:
        bool: True if valid
    """
    if contour is None:
        return False

    h, w = img_shape[:2]
    img_area = h * w

    # Calculate contour area
    contour_area = cv2.contourArea(contour)

    # Should cover at least 10% of image but not more than 98%
    min_area = img_area * 0.10
    max_area = img_area * 0.98

    return min_area <= contour_area <= max_area


def page_covers_full_image(contour: np.ndarray, img_shape: tuple, threshold: float = 0.9) -> bool:
    """
    Check if page contour covers most of the image.

    Args:
        contour: 4-point contour
        img_shape: Image shape
        threshold: Coverage threshold (0.0-1.0)

    Returns:
        bool: True if page covers >= threshold of image
    """
    if contour is None:
        return False

    h, w = img_shape[:2]
    img_area = h * w
    contour_area = cv2.contourArea(contour)

    coverage = contour_area / img_area
    return coverage >= threshold


def calculate_fold_position_ratio(fold_x: int, contour: np.ndarray) -> float:
    """
    Calculate fold position as ratio within page boundaries.

    Args:
        fold_x: Fold X coordinate
        contour: Page contour

    Returns:
        float: Position ratio 0.0-1.0 (0=left edge, 0.5=center, 1.0=right edge)
    """
    min_x, _, max_x, _ = get_contour_bounds(contour)
    page_width = max_x - min_x

    if page_width == 0:
        return 0.5

    # Calculate position relative to page
    position = (fold_x - min_x) / page_width

    # Clamp to 0-1
    return max(0.0, min(1.0, position))


def split_at_fold(
    img: np.ndarray, fold_x: int, fold_border: int = 50
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Split image at fold line into left and right parts.

    Args:
        img: Input image
        fold_x: Fold X coordinate
        fold_border: Border pixels around fold

    Returns:
        tuple: (left_image, right_image)
    """
    h, w = img.shape[:2]

    # Left side: from 0 to fold_x + border
    left_end = min(w, fold_x + fold_border)
    left_side = img[:, :left_end]

    # Right side: from fold_x - border to end
    right_start = max(0, fold_x - fold_border)
    right_side = img[:, right_start:]

    return left_side, right_side


def crop_to_fold(
    img: np.ndarray, fold_x: int, fold_side: str, fold_border: int = 50
) -> np.ndarray:
    """
    Crop image to one side of fold (for partial books).

    Args:
        img: Input image
        fold_x: Fold X coordinate
        fold_side: Which side to keep ('left' or 'right')
        fold_border: Border pixels around fold

    Returns:
        np.ndarray: Cropped image
    """
    h, w = img.shape[:2]

    if fold_side == "left":
        # Keep left side (fold on right edge)
        end_x = min(w, fold_x + fold_border)
        return img[:, :end_x]
    else:  # right
        # Keep right side (fold on left edge)
        start_x = max(0, fold_x - fold_border)
        return img[:, start_x:]
