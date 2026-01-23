"""
coordinate_transform.py

Coordinate Transformation Utilities
====================================

Handles transformation of detection coordinates between different image spaces:
- Original image space (variable size, e.g., 4000x3000)
- Rectified image space (after perspective warp)
- Dataset image space (512x512 letterbox)

Critical for maintaining geometric accuracy when converting CV detections
to neural network training labels.
"""

import cv2
import numpy as np


def transform_page_corners(corners_original, scale, offset_x, offset_y):
    """
    Transform page corners from original image space to 512x512 dataset space.

    Args:
        corners_original (np.ndarray): Array of shape (4, 2) or (4, 1, 2)
                                       containing corner coordinates in original pixel space
        scale (float): Scaling factor from resize_with_letterbox
        offset_x (int): Horizontal offset from resize_with_letterbox
        offset_y (int): Vertical offset from resize_with_letterbox

    Returns:
        list: List of 4 [x, y] coordinate pairs in 512x512 space

    Example:
        >>> corners_orig = np.array([[100, 150], [3900, 140], [3920, 2860], [80, 2880]])
        >>> corners_512 = transform_page_corners(corners_orig, 0.128, 0, 64)
        >>> # corners_512 ~ [[13, 83], [499, 82], [502, 430], [10, 432]]

    Formula:
        x_512 = x_original * scale + offset_x
        y_512 = y_original * scale + offset_y
    """
    # Handle different input shapes (4,2) or (4,1,2)
    if corners_original.ndim == 3:
        corners_original = corners_original.reshape(-1, 2)

    corners_512 = []
    for corner in corners_original:
        x_orig, y_orig = corner[0], corner[1]
        x_512 = int(x_orig * scale + offset_x)
        y_512 = int(y_orig * scale + offset_y)

        # Clamp to valid range [0, 511]
        x_512 = np.clip(x_512, 0, 511)
        y_512 = np.clip(y_512, 0, 511)

        corners_512.append([x_512, y_512])

    return corners_512


def inverse_transform_fold_to_original(x_fold, img_height_rectified, M):
    """
    Transform fold line from rectified space back to original image space.

    The fold is detected as a vertical line at x=x_fold in the rectified (warped)
    image. This function applies the inverse transformation to find where that
    vertical line was in the original image (where it will be INCLINED).

    Args:
        x_fold (int): X coordinate of vertical fold line in rectified image
        img_height_rectified (int): Height of rectified image in pixels
        M (np.ndarray): Affine transformation matrix (2x3) from warp_image()

    Returns:
        tuple: (fold_point1, fold_point2)
            - fold_point1: (x, y) tuple for top of fold line in original space
            - fold_point2: (x, y) tuple for bottom of fold line in original space

    Example:
        >>> M = np.array([[0.99, -0.05, 12], [0.05, 0.99, -8]])
        >>> p1, p2 = inverse_transform_fold_to_original(256, 1000, M)
        >>> # p1 ~ (243, 12), p2 ~ (293, 1002)  <- Notice inclination!

    Algorithm:
        1. Define fold line in rectified space as vertical line:
           - point1_rect = (x_fold, 0) <- top
           - point2_rect = (x_fold, img_height_rectified) <- bottom

        2. Apply inverse transformation M^(-1):
           For affine transform: [x', y', 1]^T = M * [x, y, 1]^T
           Inverse: [x, y, 1]^T = M^(-1) * [x', y', 1]^T

        3. Return transformed points in original image coordinates
    """
    if M is None:
        # No transformation matrix - fold coordinates are already in original space
        # This shouldn't happen in normal flow, but handle gracefully
        return (x_fold, 0), (x_fold, img_height_rectified)

    # Define fold line endpoints in rectified space (vertical line)
    point1_rect = np.array([x_fold, 0], dtype=np.float32)  # Top
    point2_rect = np.array([x_fold, img_height_rectified], dtype=np.float32)  # Bottom

    # Compute inverse transformation matrix
    M_inv = cv2.invertAffineTransform(M)

    # Apply inverse transformation to both points
    # For affine: [x', y'] = M * [x, y, 1]
    # Inverse: [x, y] = M_inv * [x', y', 1]

    # Convert to homogeneous coordinates
    point1_rect_h = np.array([point1_rect[0], point1_rect[1], 1.0], dtype=np.float32)
    point2_rect_h = np.array([point2_rect[0], point2_rect[1], 1.0], dtype=np.float32)

    # Apply inverse transform
    point1_orig_h = M_inv @ point1_rect_h
    point2_orig_h = M_inv @ point2_rect_h

    # Convert back to image coordinates (drop homogeneous component)
    fold_point1 = (int(point1_orig_h[0]), int(point1_orig_h[1]))
    fold_point2 = (int(point2_orig_h[0]), int(point2_orig_h[1]))

    return fold_point1, fold_point2


def transform_fold_to_512(fold_p1_original, fold_p2_original, scale, offset_x, offset_y):
    """
    Transform fold line points from original image space to 512x512 dataset space.

    Args:
        fold_p1_original (tuple): (x, y) for point 1 in original coordinates
        fold_p2_original (tuple): (x, y) for point 2 in original coordinates
        scale (float): Scaling factor from resize_with_letterbox
        offset_x (int): Horizontal offset from resize_with_letterbox
        offset_y (int): Vertical offset from resize_with_letterbox

    Returns:
        tuple: (fold_p1_512, fold_p2_512)
            - fold_p1_512: [x, y] list for point 1 in 512x512 space
            - fold_p2_512: [x, y] list for point 2 in 512x512 space

    Example:
        >>> p1_orig = (245, 15)
        >>> p2_orig = (290, 2985)
        >>> p1_512, p2_512 = transform_fold_to_512(p1_orig, p2_orig, 0.128, 0, 64)
        >>> # p1_512 ~ [31, 66], p2_512 ~ [37, 446]

    Formula (same as page corners):
        x_512 = x_original * scale + offset_x
        y_512 = y_original * scale + offset_y
    """
    x1, y1 = fold_p1_original
    x2, y2 = fold_p2_original

    # Transform point 1
    x1_512 = int(x1 * scale + offset_x)
    y1_512 = int(y1 * scale + offset_y)

    # Transform point 2
    x2_512 = int(x2 * scale + offset_x)
    y2_512 = int(y2 * scale + offset_y)

    # Clamp to valid range [0, 511]
    x1_512 = np.clip(x1_512, 0, 511)
    y1_512 = np.clip(y1_512, 0, 511)
    x2_512 = np.clip(x2_512, 0, 511)
    y2_512 = np.clip(y2_512, 0, 511)

    return [x1_512, y1_512], [x2_512, y2_512]


def compute_fold_line_full_pipeline(x_fold, rectified_img, M, scale, offset_x, offset_y):
    """
    Complete pipeline: Transform fold from rectified space to 512x512 dataset space.

    This is a convenience function that combines inverse transformation and
    resizing transformation into a single call.

    Args:
        x_fold (int): X coordinate of fold in rectified image
        rectified_img (np.ndarray): Rectified image (to get height)
        M (np.ndarray): Transformation matrix (2x3) from warp_image
        scale (float): Scaling factor for resize
        offset_x (int): Horizontal offset for resize
        offset_y (int): Vertical offset for resize

    Returns:
        tuple: (fold_p1_512, fold_p2_512)
            Two [x, y] lists defining fold line in 512x512 space

    Pipeline:
        1. Rectified space -> Original space (inverse M)
        2. Original space -> 512x512 space (scale + offset)
    """
    # Step 1: Inverse transform from rectified to original
    img_height_rect = rectified_img.shape[0]
    fold_p1_orig, fold_p2_orig = inverse_transform_fold_to_original(
        x_fold, img_height_rect, M
    )

    # Step 2: Transform from original to 512x512
    fold_p1_512, fold_p2_512 = transform_fold_to_512(
        fold_p1_orig, fold_p2_orig, scale, offset_x, offset_y
    )

    return fold_p1_512, fold_p2_512


def validate_coordinates_in_range(coords, max_value=512):
    """
    Validate that coordinates are within expected range.

    Args:
        coords (list): List of coordinate pairs [[x1, y1], [x2, y2], ...]
        max_value (int): Maximum valid coordinate value (default: 512)

    Returns:
        bool: True if all coordinates are valid

    Raises:
        ValueError: If any coordinate is out of range
    """
    for i, (x, y) in enumerate(coords):
        if not (0 <= x < max_value):
            raise ValueError(f"Coordinate {i}: x={x} out of range [0, {max_value})")
        if not (0 <= y < max_value):
            raise ValueError(f"Coordinate {i}: y={y} out of range [0, {max_value})")
    return True


# Test function for development
if __name__ == "__main__":
    print("Testing coordinate transformations...")

    # Test case 1: Page corners transformation
    print("\n[Test 1] Page corners transformation")
    corners_orig = np.array([
        [100, 150],
        [3900, 140],
        [3920, 2860],
        [80, 2880]
    ])
    scale = 512 / 4000  # 0.128
    offset_x = 0
    offset_y = 64

    corners_512 = transform_page_corners(corners_orig, scale, offset_x, offset_y)
    print(f"Original corners shape: {corners_orig.shape}")
    print(f"Transformed corners: {corners_512}")
    validate_coordinates_in_range(corners_512)
    print("Page corners transformation valid")

    # Test case 2: Fold line inverse transformation
    print("\n[Test 2] Fold line inverse transformation")
    # Create a simple rotation matrix (5 degrees)
    angle = 5
    M = cv2.getRotationMatrix2D((2000, 1500), angle, 1.0)
    x_fold = 256
    img_height_rect = 1000

    fold_p1_orig, fold_p2_orig = inverse_transform_fold_to_original(
        x_fold, img_height_rect, M
    )
    print(f"Fold in rectified space: x={x_fold}, top=(x,0), bottom=(x,{img_height_rect})")
    print(f"Fold in original space: top={fold_p1_orig}, bottom={fold_p2_orig}")
    print("Inverse transformation completed")

    # Test case 3: Fold transformation to 512x512
    print("\n[Test 3] Fold transformation to 512x512")
    fold_p1_512, fold_p2_512 = transform_fold_to_512(
        fold_p1_orig, fold_p2_orig, scale, offset_x, offset_y
    )
    print(f"Fold in 512x512 space: point1={fold_p1_512}, point2={fold_p2_512}")
    validate_coordinates_in_range([fold_p1_512, fold_p2_512])
    print("Fold transformation to 512x512 valid")

    print("\nAll coordinate transformation tests passed!")
