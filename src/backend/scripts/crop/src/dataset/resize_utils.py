"""
resize_utils.py

Image Resizing Utilities for Dataset Generation
===============================================

Provides letterbox resizing functionality that preserves aspect ratio
while creating fixed-size images with black padding.

This is critical for geometric accuracy in page/fold detection tasks,
as it maintains correct proportions and angles.
"""

import cv2
import numpy as np


def resize_with_letterbox(img, target_size=512):
    """
    Resize image to target_size x target_size with letterbox padding.

    Preserves aspect ratio by scaling to fit within target dimensions,
    then adds black padding to create a square image. This maintains
    geometric accuracy for page corners and fold line detection.

    Args:
        img (np.ndarray): Input image in BGR format, shape (H, W, 3)
        target_size (int): Target dimension for output square image (default: 512)

    Returns:
        tuple: (resized_img, scale, offset_x, offset_y)
            - resized_img (np.ndarray): Letterboxed image, shape (target_size, target_size, 3)
            - scale (float): Scaling factor applied to original image
            - offset_x (int): Horizontal padding offset (left padding in pixels)
            - offset_y (int): Vertical padding offset (top padding in pixels)

    Example:
        >>> img = cv2.imread("scan.jpg")  # 4000x3000
        >>> resized, scale, ox, oy = resize_with_letterbox(img, 512)
        >>> # resized.shape = (512, 512, 3)
        >>> # scale ~ 0.128 (512/4000)
        >>> # ox = 0, oy = 64 (centered padding)

    Algorithm:
        1. Calculate aspect ratio and determine scale to fit within target_size
        2. Resize image maintaining aspect ratio
        3. Calculate padding needed to center image
        4. Create black canvas and place resized image in center
        5. Return letterboxed image with transformation parameters
    """
    original_height, original_width = img.shape[:2]

    # Calculate scaling factor to fit within target_size
    scale = min(target_size / original_width, target_size / original_height)

    # Calculate new dimensions
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    # Resize image maintaining aspect ratio
    resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # Calculate padding to center the image
    pad_x = (target_size - new_width) // 2
    pad_y = (target_size - new_height) // 2

    # Create black canvas
    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)

    # Place resized image in center of canvas
    canvas[pad_y:pad_y + new_height, pad_x:pad_x + new_width] = resized

    return canvas, scale, pad_x, pad_y


def get_content_region(scale, offset_x, offset_y, original_width, original_height, target_size=512):
    """
    Calculate the content region (non-padded area) in the letterboxed image.

    Useful for models that need to focus attention on actual image content
    rather than black padding.

    Args:
        scale (float): Scaling factor from resize_with_letterbox
        offset_x (int): Horizontal offset from resize_with_letterbox
        offset_y (int): Vertical offset from resize_with_letterbox
        original_width (int): Original image width in pixels
        original_height (int): Original image height in pixels
        target_size (int): Target size used for letterboxing (default: 512)

    Returns:
        tuple: (x_start, y_start, x_end, y_end) defining content bounding box

    Example:
        >>> region = get_content_region(0.128, 0, 64, 4000, 3000, 512)
        >>> # region = (0, 64, 512, 448)
        >>> # Content occupies: x[0:512], y[64:448]
    """
    content_width = int(original_width * scale)
    content_height = int(original_height * scale)

    x_start = offset_x
    y_start = offset_y
    x_end = offset_x + content_width
    y_end = offset_y + content_height

    return x_start, y_start, x_end, y_end


def validate_resize_params(scale, offset_x, offset_y, target_size=512):
    """
    Validate resize parameters to ensure they're within expected ranges.

    Args:
        scale (float): Scaling factor
        offset_x (int): Horizontal offset
        offset_y (int): Vertical offset
        target_size (int): Target image size

    Returns:
        bool: True if parameters are valid

    Raises:
        ValueError: If parameters are invalid
    """
    if scale <= 0 or scale > 1:
        raise ValueError(f"Scale must be in range (0, 1], got {scale}")

    if offset_x < 0 or offset_x >= target_size:
        raise ValueError(f"offset_x must be in range [0, {target_size}), got {offset_x}")

    if offset_y < 0 or offset_y >= target_size:
        raise ValueError(f"offset_y must be in range [0, {target_size}), got {offset_y}")

    return True


# Test function for development
if __name__ == "__main__":
    print("Testing resize_with_letterbox...")

    # Test case 1: Landscape image
    landscape = np.random.randint(0, 255, (3000, 4000, 3), dtype=np.uint8)
    resized, scale, ox, oy = resize_with_letterbox(landscape, 512)
    print(f"\nLandscape 4000x3000:")
    print(f"  Output shape: {resized.shape}")
    print(f"  Scale: {scale:.4f}")
    print(f"  Offsets: x={ox}, y={oy}")
    validate_resize_params(scale, ox, oy)

    # Test case 2: Portrait image
    portrait = np.random.randint(0, 255, (4000, 3000, 3), dtype=np.uint8)
    resized, scale, ox, oy = resize_with_letterbox(portrait, 512)
    print(f"\nPortrait 3000x4000:")
    print(f"  Output shape: {resized.shape}")
    print(f"  Scale: {scale:.4f}")
    print(f"  Offsets: x={ox}, y={oy}")
    validate_resize_params(scale, ox, oy)

    # Test case 3: Square image
    square = np.random.randint(0, 255, (3000, 3000, 3), dtype=np.uint8)
    resized, scale, ox, oy = resize_with_letterbox(square, 512)
    print(f"\nSquare 3000x3000:")
    print(f"  Output shape: {resized.shape}")
    print(f"  Scale: {scale:.4f}")
    print(f"  Offsets: x={ox}, y={oy}")
    validate_resize_params(scale, ox, oy)

    print("\nAll tests passed!")
