"""
page_processor.py

Document Page Processing Integration Module
==========================================

This module provides intelligent page processing that combines contour detection
with document format analysis. It determines if an image requires perspective
correction and cropping based on document format detection (A3 landscape).

Key Function:
- process_page_if_needed: Main processing function that detects A3 landscape
  and applies contour-based correction when appropriate

Integration Design:
- Isolated module that doesn't modify existing codebase
- Uses existing contour_detector and extract_doc_size components
- Provides clean interface for crop.py and main.py integration
- Falls back gracefully when processing isn't needed

Author: [Generated Integration Module]
Version: 1.0
"""

from PIL import Image

from .contour_detector.detect import find_page_contour
from .contour_detector.preprocess import preprocess_image
from .contour_detector.transform import warp_image


def extract_image_metadata(img_array):
    """
    Extract DPI and size information from image array.

    Args:
        img_array (np.ndarray): Input image array

    Returns:
        tuple: (width_px, height_px, dpi_x, dpi_y) or (None, None, None, None) if failed
    """
    try:
        height, width = img_array.shape[:2]
        # For arrays, we don't have DPI info, so return pixel dimensions only
        # DPI will need to be estimated or provided externally
        return width, height, None, None
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return None, None, None, None


def calculate_physical_dimensions(width_px, height_px, dpi_x, dpi_y):
    """
    Calculate physical dimensions from pixel dimensions and DPI.

    Args:
        width_px, height_px: Pixel dimensions
        dpi_x, dpi_y: DPI values

    Returns:
        tuple: (width_cm, height_cm) or (None, None) if cannot calculate
    """
    if dpi_x is None or dpi_y is None:
        return None, None

    try:
        dpi_x_float = float(dpi_x)
        dpi_y_float = float(dpi_y)

        width_inches = width_px / dpi_x_float
        height_inches = height_px / dpi_y_float
        width_cm = width_inches * 2.54
        height_cm = height_inches * 2.54

        return width_cm, height_cm
    except Exception as e:
        print(f"Error calculating physical dimensions: {e}")
        return None, None


def is_a3_landscape_format(width_cm, height_cm, tolerance=0.15):
    """
    Check if dimensions match A3 landscape format.

    Args:
        width_cm, height_cm: Physical dimensions in centimeters
        tolerance: Size tolerance (15% default)

    Returns:
        bool: True if matches A3 landscape
    """
    if width_cm is None or height_cm is None:
        return False

    # A3 dimensions: 29.7 x 42.0 cm
    # A3 landscape: 42.0 x 29.7 cm (width > height)
    a3_landscape_w, a3_landscape_h = 42.0, 29.7

    # Check orientation (landscape)
    is_landscape = width_cm > height_cm
    if not is_landscape:
        return False

    # Check size match with tolerance
    w_diff = abs(width_cm - a3_landscape_w) / a3_landscape_w
    h_diff = abs(height_cm - a3_landscape_h) / a3_landscape_h

    return w_diff <= tolerance and h_diff <= tolerance


def detect_document_format(image_path, debug=False, document_contour=None):
    """
    Detect if image contains A3 format using exact same logic as test_lab.
    If document_contour is provided, uses the contour dimensions instead of full image.

    Args:
        image_path (str): Path to image file
        debug (bool): Print debug information
        document_contour (np.ndarray): Optional contour of detected document

    Returns:
        bool: True if A3 format detected
    """
    try:
        # Use exact same PIL logic as test_lab
        with Image.open(image_path) as pil_img:
            # Extract DPI using EXACT same logic as test_lab
            dpi_x = dpi_y = None
            if hasattr(pil_img, "info") and "dpi" in pil_img.info:
                dpi_info = pil_img.info["dpi"]
                if isinstance(dpi_info, tuple) and len(dpi_info) >= 2:
                    dpi_x, dpi_y = dpi_info[0], dpi_info[1]
                else:
                    dpi_x = dpi_y = dpi_info
                if debug:
                    print(f"DPI: {dpi_info}")
            elif hasattr(pil_img, "tag") and "dpi" in pil_img.tag:
                dpi_info = pil_img.tag["dpi"]
                dpi_x = dpi_y = dpi_info
                if debug:
                    print(f"DPI (from tag): {dpi_info}")

            # Determine which dimensions to use
            if document_contour is not None:
                # Use contour-detected document dimensions
                import cv2

                x, y, w, h = cv2.boundingRect(document_contour)
                width_px, height_px = w, h
                if debug:
                    print(f"Using contour-detected document dimensions: {w}x{h}px")
                    print(f"Document position in image: x={x}, y={y}")
            else:
                # Use full image dimensions (original behavior)
                width_px, height_px = pil_img.size
                if debug:
                    print(f"Using full image dimensions: {width_px}x{height_px}px")

        if dpi_x is None or dpi_y is None:
            if debug:
                print("No DPI information found")
            return False

        # Calculate physical dimensions
        width_cm, height_cm = calculate_physical_dimensions(
            width_px, height_px, dpi_x, dpi_y
        )

        if width_cm is None:
            if debug:
                print("Could not calculate physical dimensions")
            return False

        if debug:
            print(f"Physical dimensions: {width_cm:.1f} x {height_cm:.1f} cm")
            print(f"Pixel dimensions: {width_px} x {height_px}")
            print(f"DPI: {dpi_x} x {dpi_y}")

        # STEP 1: Check A3 landscape by physical dimensions
        is_a3_physical = is_a3_landscape_format(width_cm, height_cm)

        if debug:
            print(
                f"Step 1 - Physical dimensions check: {'[OK] A3 landscape' if is_a3_physical else '[NO] Not A3 landscape'}"
            )

        # STEP 2: If step 1 fails, try aspect ratio fallback
        is_a3_aspect = False
        if not is_a3_physical:
            aspect_ratio = width_px / height_px
            a3_landscape_ratio = 42.0 / 29.7  # approx 1.414
            tolerance = 0.03  # 3% tolerance (more restrictive)
            min_ratio = a3_landscape_ratio * (1 - tolerance)
            max_ratio = a3_landscape_ratio * (1 + tolerance)

            is_a3_aspect = min_ratio <= aspect_ratio <= max_ratio

            if debug:
                print("Step 2 - Aspect ratio check:")
                print(f"  Document aspect ratio: {aspect_ratio:.3f}")
                print(f"  A3 landscape target: {a3_landscape_ratio:.3f}")
                print(f"  Acceptable range: {min_ratio:.3f} - {max_ratio:.3f}")
                print(
                    f"  Result: {'[OK] A3 landscape (by aspect ratio)' if is_a3_aspect else '[NO] Not A3 landscape'}"
                )

        # Final result: A3 detected by either method
        is_a3_detected = is_a3_physical or is_a3_aspect

        # Also check for A4 portrait for additional debug info
        a4_portrait_w, a4_portrait_h = 21.0, 29.7
        is_a4_portrait = False
        if width_cm < height_cm:  # Portrait orientation
            w_diff = abs(width_cm - a4_portrait_w) / a4_portrait_w
            h_diff = abs(height_cm - a4_portrait_h) / a4_portrait_h
            is_a4_portrait = w_diff <= 0.15 and h_diff <= 0.15

        if debug:
            print("\n[RESULT] FINAL RESULT:")
            if is_a3_detected:
                method = "physical dimensions" if is_a3_physical else "aspect ratio"
                print(f"[OK] DETECTED: A3 landscape format (by {method})")
            elif is_a4_portrait:
                print("[INFO] DETECTED: A4 portrait format (not A3 landscape)")
            else:
                print("[NO] NOT A3 landscape format")

        return is_a3_detected

    except Exception as e:
        if debug:
            print(f"Error in format detection: {e}")
        return False


def calculate_document_coverage(page_contour, img_shape):
    """
    Calculate what percentage of the image is covered by the detected document.

    Args:
        page_contour (np.ndarray): Detected page contour
        img_shape (tuple): Image shape (height, width, channels)

    Returns:
        float: Coverage percentage (0.0 to 1.0)
    """
    try:
        import cv2

        # Calculate total image area
        img_height, img_width = img_shape[:2]
        total_area = img_width * img_height

        # Calculate document area from contour
        document_area = cv2.contourArea(page_contour)

        # Calculate coverage percentage
        coverage = document_area / total_area

        return coverage

    except Exception as e:
        print(f"Error calculating document coverage: {e}")
        return 0.0


def process_page_if_needed(img, image_path=None, debug=False, contour_border=150, coverage_threshold=0.90, max_processing_size=1080):
    """
    Process page with contour detection if needed based on document analysis.

    This function intelligently determines if the image needs perspective correction
    and cropping based on document format analysis and coverage percentage.
    Skips processing if document already fills most of the image (≥90% by default).

    Args:
        img (np.ndarray): Input BGR image
        image_path (str): Path to image file for format detection
        debug (bool): Enable debug output
        contour_border (int): Border pixels for cropping (default: 150)
        coverage_threshold (float): Skip processing if document coverage ≥ this threshold (default: 0.90)
        max_processing_size (int): Max size in pixels for contour detection (default: 2000).
                                   Images larger than this will be downscaled for faster processing.

    Returns:
        tuple: (processed_img, was_processed, actual_border, is_a3_detected, page_contour, transform_M)
               - processed_img (np.ndarray): Output image (processed or original)
               - was_processed (bool): True if contour processing was applied
               - actual_border (int): Border pixels actually used
               - is_a3_detected (bool): True if A3 format was detected from contour
               - page_contour (np.ndarray): Detected page contour in original coords, or None
               - transform_M (np.ndarray): Transformation matrix (2x3) from warp_image, or None
    """
    try:
        import cv2

        if debug:
            print("\n=== PAGE PROCESSING ANALYSIS ===")

        # Step 1: Check if image needs downscaling for contour detection
        img_height, img_width = img.shape[:2]
        max_dim = max(img_height, img_width)
        scale_factor = 1.0
        img_for_contour = img

        if max_dim > max_processing_size:
            scale_factor = max_processing_size / max_dim
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            img_for_contour = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

            if debug:
                print("\n=== IMAGE DOWNSCALING FOR CONTOUR DETECTION ===")
                print(f"Original size: {img_width}x{img_height}px (max: {max_dim}px)")
                print(f"Downscaled size: {new_width}x{new_height}px")
                print(f"Scale factor: {scale_factor:.4f}")
        else:
            if debug:
                print("\n=== NO DOWNSCALING NEEDED ===")
                print(f"Image size: {img_width}x{img_height}px (max: {max_dim}px <= {max_processing_size}px)")

        # Step 2: Always apply contour processing (regardless of format)
        if debug:
            print("\nApplying contour processing...")

        # Step 3: Apply contour detection pipeline on downscaled image
        # Preprocess image for contour detection
        thresh, border_value = preprocess_image(img_for_contour, show_step_by_step=debug)

        # Find page contour on downscaled image
        page_contour, angle = find_page_contour(
            thresh, show_step_by_step=debug, original_image=img_for_contour
        )

        if page_contour is None:
            if debug:
                print("No page contour found - returning original image")
            return img, False, contour_border, False, None, None

        # Step 4: Scale contour back to original image coordinates
        if scale_factor != 1.0:
            page_contour_original = page_contour / scale_factor
            page_contour_original = page_contour_original.astype(page_contour.dtype)

            if debug:
                print(f"\n=== CONTOUR SCALING ===")
                print(f"Contour found on downscaled image - scaling back to original size")
                print(f"Scale factor: 1/{scale_factor:.4f} = {1/scale_factor:.4f}")
        else:
            page_contour_original = page_contour

            if debug:
                print(f"\n=== NO CONTOUR SCALING NEEDED ===")
                print(f"Contour detected on original-size image")

        # Step 5: Check if detected contour represents A3 document
        is_a3 = False
        if image_path:
            is_a3 = detect_document_format(
                image_path, debug=debug, document_contour=page_contour_original
            )
            if not is_a3:
                if debug:
                    print("[SKIP] Document is not A3 format - returning original image")
                # Still return page_contour for dataset generation, but skip transformation
                return img, False, contour_border, False, page_contour_original, None
        else:
            # No image path provided - skip A3 check and continue processing
            if debug:
                print("[WARNING] No image path provided - skipping A3 format check")

        # Step 6: Calculate document coverage and check threshold
        coverage = calculate_document_coverage(page_contour_original, img.shape)
        coverage_percentage = coverage * 100

        if debug:
            print(f"\n=== DOCUMENT COVERAGE ANALYSIS ===")
            print(f"Document coverage: {coverage_percentage:.1f}%")
            print(f"Coverage threshold: {coverage_threshold * 100:.1f}%")

        if coverage >= coverage_threshold:
            if debug:
                print(f"[SKIP] Document coverage ({coverage_percentage:.1f}%) ≥ threshold ({coverage_threshold * 100:.1f}%)")
                print("Document already fills most of the image - skipping contour processing")
            # Still return page_contour for dataset generation, but skip transformation
            return img, False, contour_border, is_a3, page_contour_original, None

        if debug:
            print(f"[OK] Document coverage ({coverage_percentage:.1f}%) below threshold - proceeding with contour processing")

        # Calculate actual document boundaries and adjust border if needed
        x, y, w, h = cv2.boundingRect(page_contour_original)
        img_height, img_width = img.shape[:2]

        # Calculate available space around the detected document
        available_border_left = x
        available_border_right = img_width - (x + w)
        available_border_top = y
        available_border_bottom = img_height - (y + h)

        # Calculate the minimum available border on all sides
        min_available_border = min(
            available_border_left,
            available_border_right,
            available_border_top,
            available_border_bottom,
        )

        # Define minimum threshold for cropping (configurable)
        min_border_threshold = 50

        if debug:
            print(f"Document boundaries: x={x}, y={y}, w={w}, h={h}")
            print(
                f"Available borders: left={available_border_left}, right={available_border_right}, top={available_border_top}, bottom={available_border_bottom}"
            )
            print(f"Requested border: {contour_border}px")
            print(f"Minimum available border: {min_available_border}px")
            print(f"Minimum threshold for cropping: {min_border_threshold}px")

        # Check if we should apply crop or rotation-only
        if min_available_border < min_border_threshold:
            # Border too small - apply rotation only, no crop
            if debug:
                print(
                    f"[WARNING] Available border ({min_available_border}px) below threshold ({min_border_threshold}px)"
                )
                print("Applying rotation-only mode (no crop)")

            warped, _, transform_M = warp_image(
                img,
                page_contour_original,
                border_pixels=0,  # NO CROP - rotation only
                show_step_by_step=debug,
                border_value=border_value,
                angle=angle,
                opencv_version=True,
                scale_factor=scale_factor,
                image_for_irregolar_border=img_for_contour,
                contour_for_irregolar_border=page_contour,
            )

            actual_border_used = 0
        else:
            # Sufficient space - apply normal crop with adjusted border
            adjusted_border = min(contour_border, min_available_border)

            if debug:
                print("[OK] Sufficient space available - applying normal crop")
                print(f"Adjusted border: {adjusted_border}px")
                if adjusted_border < contour_border:
                    print(
                        f"[WARNING] Border reduced from {contour_border}px to {adjusted_border}px due to document boundaries"
                    )

            warped, _, transform_M = warp_image(
                img,
                page_contour_original,
                border_pixels=adjusted_border,  # Adjusted border for crop
                show_step_by_step=debug,
                border_value=border_value,
                angle=angle,
                opencv_version=True,
                scale_factor=scale_factor,
                image_for_irregolar_border=img_for_contour,
                contour_for_irregolar_border=page_contour,
            )

            actual_border_used = adjusted_border

        if debug:
            print("[OK] Successfully processed document")
            print(f"Original size: {img.shape[1]}x{img.shape[0]}")
            print(f"Processed size: {warped.shape[1]}x{warped.shape[0]}")
            print(f"Final border used: {actual_border_used}px")

        return warped, True, actual_border_used, is_a3, page_contour_original, transform_M

    except Exception as e:
        if debug:
            print(f"Error in page processing: {e}")
            print("Falling back to original image")
        return img, False, contour_border, False, None, None
