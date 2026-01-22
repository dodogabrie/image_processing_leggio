"""
debug_visualizer.py

Debug Visualization Generator
==============================

Creates debug images showing detected page corners and fold lines
    overlaid on 512x512 letterboxed images. Useful for validating
coordinate transformations and detection quality.

Color coding:
- Green: Page detection (corners and boundary)
- Red: Fold detection (line)
- White: Text labels
"""

import cv2
import numpy as np


def draw_debug_visualization(
    img_512,
    page_corners_512,
    fold_p1_512,
    fold_p2_512,
    page_present,
    fold_present,
    filename=""
):
    """
    Draw detection overlays on 512x512 image for debugging.

    Creates a visual representation of all detections with clear color coding.
    Page corners are shown as green circles with labels, fold line as red line.

    Args:
        img_512 (np.ndarray): Letterboxed image, shape (512, 512, 3) in BGR
        page_corners_512 (list): List of 4 [x, y] corners or None
        fold_p1_512 (list): [x, y] for fold point 1 or None
        fold_p2_512 (list): [x, y] for fold point 2 or None
        page_present (bool): True if page was detected
        fold_present (bool): True if fold was detected
        filename (str): Optional filename to display on image

    Returns:
        np.ndarray: Debug image with overlays, shape (512, 512, 3)

    Visual Elements:
        - Page corners: Green circles (radius=5)
        - Page corner labels: White text "P1", "P2", "P3", "P4"
        - Page boundary: Green polyline connecting corners
        - Fold line: Red line (thickness=2)
        - Status text: White text showing detection status
        - Filename: White text in top-left corner

    Color Scheme:
        - Green (0, 255, 0): Page detection
        - Red (0, 0, 255): Fold detection
        - White (255, 255, 255): Text and labels
    """
    # Create a copy to avoid modifying original
    debug_img = img_512.copy()

    # Define colors (BGR format)
    GREEN = (0, 255, 0)
    RED = (0, 0, 255)
    WHITE = (255, 255, 255)

    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1

    # Draw filename in top-left corner
    if filename:
        cv2.putText(
            debug_img,
            filename,
            (10, 20),
            font,
            font_scale,
            WHITE,
            font_thickness,
            cv2.LINE_AA
        )

    # Draw page detection if present
    if page_present and page_corners_512 is not None:
        # Convert corners to numpy array for easier manipulation
        corners = np.array(page_corners_512, dtype=np.int32)

        # Draw page boundary as closed polygon
        cv2.polylines(
            debug_img,
            [corners],
            isClosed=True,
            color=GREEN,
            thickness=2,
            lineType=cv2.LINE_AA
        )

        # Draw corners as circles with labels
        corner_labels = ["P1", "P2", "P3", "P4"]
        for i, (corner, label) in enumerate(zip(corners, corner_labels)):
            x, y = corner[0], corner[1]

            # Draw circle at corner point
            cv2.circle(
                debug_img,
                (x, y),
                radius=5,
                color=GREEN,
                thickness=-1,  # Filled circle
                lineType=cv2.LINE_AA
            )

            # Draw label next to corner (offset to avoid overlap)
            label_offset_x = 10 if i < 2 else -30  # Right for top corners, left for bottom
            label_offset_y = -10 if i % 2 == 0 else 20  # Up for left corners, down for right

            cv2.putText(
                debug_img,
                label,
                (x + label_offset_x, y + label_offset_y),
                font,
                0.6,
                WHITE,
                font_thickness + 1,
                cv2.LINE_AA
            )

    # Draw fold line if present
    if fold_present and fold_p1_512 is not None and fold_p2_512 is not None:
        x1, y1 = fold_p1_512
        x2, y2 = fold_p2_512

        # Draw fold line (notice: it will be INCLINED in original space!)
        cv2.line(
            debug_img,
            (x1, y1),
            (x2, y2),
            color=RED,
            thickness=2,
            lineType=cv2.LINE_AA
        )

        # Draw small circles at fold line endpoints
        cv2.circle(debug_img, (x1, y1), radius=4, color=RED, thickness=-1, lineType=cv2.LINE_AA)
        cv2.circle(debug_img, (x2, y2), radius=4, color=RED, thickness=-1, lineType=cv2.LINE_AA)

        # Add "FOLD" label near the middle of the line
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        cv2.putText(
            debug_img,
            "FOLD",
            (mid_x + 10, mid_y),
            font,
            0.5,
            WHITE,
            font_thickness + 1,
            cv2.LINE_AA
        )

    # Add detection status text at bottom
    status_y = 500
    if page_present:
        cv2.putText(
            debug_img,
            "Page: DETECTED",
            (10, status_y),
            font,
            0.4,
            GREEN,
            font_thickness,
            cv2.LINE_AA
        )
    else:
        cv2.putText(
            debug_img,
            "Page: NOT DETECTED",
            (10, status_y),
            font,
            0.4,
            WHITE,
            font_thickness,
            cv2.LINE_AA
        )

    if fold_present:
        cv2.putText(
            debug_img,
            "Fold: DETECTED",
            (200, status_y),
            font,
            0.4,
            RED,
            font_thickness,
            cv2.LINE_AA
        )
    else:
        cv2.putText(
            debug_img,
            "Fold: NOT DETECTED",
            (200, status_y),
            font,
            0.4,
            WHITE,
            font_thickness,
            cv2.LINE_AA
        )

    return debug_img


def save_debug_image(debug_img, output_path):
    """
    Save debug visualization image to disk.

    Args:
        debug_img (np.ndarray): Debug image from draw_debug_visualization()
        output_path (str): Full path to output image file

    Returns:
        bool: True if save successful

    Example:
        >>> debug_img = draw_debug_visualization(...)
        >>> save_debug_image(debug_img, "_AI_training/debug/IMG_001_debug.jpg")
        True
    """
    try:
        # Ensure output directory exists
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save with high quality
        cv2.imwrite(output_path, debug_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return True

    except Exception as e:
        print(f"[ERROR] Failed to save debug image to {output_path}: {e}")
        return False


def create_side_by_side_comparison(original_512, debug_512):
    """
    Create side-by-side comparison of original and debug images.

    Args:
        original_512 (np.ndarray): Original letterboxed image (512, 512, 3)
        debug_512 (np.ndarray): Debug image with overlays (512, 512, 3)

    Returns:
        np.ndarray: Combined image (512, 1024, 3) showing both side-by-side
    """
    # Concatenate horizontally
    combined = np.hstack([original_512, debug_512])

    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(combined, "ORIGINAL", (180, 30), font, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(combined, "DEBUG", (700, 30), font, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    return combined


def add_grid_overlay(img_512, grid_size=64):
    """
    Add a reference grid to image for coordinate validation.

    Useful for verifying coordinate accuracy during development.

    Args:
        img_512 (np.ndarray): Input image (512, 512, 3)
        grid_size (int): Grid spacing in pixels (default: 64)

    Returns:
        np.ndarray: Image with grid overlay
    """
    img_with_grid = img_512.copy()
    color = (128, 128, 128)  # Gray
    thickness = 1

    # Draw vertical lines
    for x in range(0, 512, grid_size):
        cv2.line(img_with_grid, (x, 0), (x, 512), color, thickness)

    # Draw horizontal lines
    for y in range(0, 512, grid_size):
        cv2.line(img_with_grid, (0, y), (512, y), color, thickness)

    # Add coordinate labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    for x in range(0, 512, grid_size * 2):
        cv2.putText(img_with_grid, str(x), (x + 2, 12), font, 0.3, (255, 255, 255), 1)

    for y in range(0, 512, grid_size * 2):
        cv2.putText(img_with_grid, str(y), (2, y + 12), font, 0.3, (255, 255, 255), 1)

    return img_with_grid


# Test function for development
if __name__ == "__main__":
    print("Testing debug visualization...")

    # Create a test image (512x512 with some content)
    test_img = np.ones((512, 512, 3), dtype=np.uint8) * 200  # Light gray background

    # Add some fake content
    cv2.rectangle(test_img, (50, 80), (460, 430), (100, 150, 200), -1)

    # Test case 1: Full detection
    print("\n[Test 1] Full detection (page + fold)")
    page_corners = [[45, 32], [478, 28], [482, 488], [41, 492]]
    fold_p1 = [256, 35]
    fold_p2 = [262, 485]

    debug_img_1 = draw_debug_visualization(
        test_img,
        page_corners,
        fold_p1,
        fold_p2,
        page_present=True,
        fold_present=True,
        filename="IMG_001.jpg"
    )
    print(f"Debug image shape: {debug_img_1.shape}")
    print("Full detection visualization created")

    # Test case 2: Page only
    print("\n[Test 2] Page only (no fold)")
    debug_img_2 = draw_debug_visualization(
        test_img,
        page_corners,
        None,
        None,
        page_present=True,
        fold_present=False,
        filename="IMG_002.jpg"
    )
    print("Page-only visualization created")

    # Test case 3: No detection
    print("\n[Test 3] No detection")
    debug_img_3 = draw_debug_visualization(
        test_img,
        None,
        None,
        None,
        page_present=False,
        fold_present=False,
        filename="IMG_003.jpg"
    )
    print("No-detection visualization created")

    # Test case 4: Side-by-side comparison
    print("\n[Test 4] Side-by-side comparison")
    comparison = create_side_by_side_comparison(test_img, debug_img_1)
    print(f"Comparison image shape: {comparison.shape}")
    print("Side-by-side comparison created")

    # Test case 5: Grid overlay
    print("\n[Test 5] Grid overlay")
    grid_img = add_grid_overlay(test_img)
    print(f"Grid image shape: {grid_img.shape}")
    print("Grid overlay created")

    print("\nAll debug visualization tests passed!")
