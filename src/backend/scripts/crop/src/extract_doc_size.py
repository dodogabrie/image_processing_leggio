import cv2
from PIL import Image
from PIL.ExifTags import TAGS

from src.contour_detector.detect import find_page_contour
from src.contour_detector.preprocess import preprocess_image

DEBUG = False


def calculate_contour_dimensions(contour, dpi_x, dpi_y):
    """
    Calculate physical dimensions of a detected contour/rectangle.

    Parameters:
        contour (numpy.ndarray): Detected contour points
        dpi_x (float): DPI in X direction
        dpi_y (float): DPI in Y direction

    Returns:
        tuple: (width_cm, height_cm, area_cm2)
    """
    if contour is None or dpi_x is None or dpi_y is None:
        return None, None, None

    try:
        # Get bounding rectangle of the contour
        x, y, w, h = cv2.boundingRect(contour)

        # Convert DPI to float to handle Fraction objects
        dpi_x_float = float(dpi_x)
        dpi_y_float = float(dpi_y)

        # Convert pixels to inches, then to cm
        width_inches = w / dpi_x_float
        height_inches = h / dpi_y_float
        width_cm = width_inches * 2.54
        height_cm = height_inches * 2.54

        # Calculate area
        area_cm2 = width_cm * height_cm

        return width_cm, height_cm, area_cm2

    except Exception as e:
        print(f"Error calculating contour dimensions: {e}")
        return None, None, None


def test_lab(image_path):
    """
    Test function to examine TIF image metadata and properties.
    """
    print(f"\n=== TIF METADATA TEST for {image_path} ===")

    try:
        # Open image with PIL to check metadata
        with Image.open(image_path) as pil_img:
            print(f"Format: {pil_img.format}")
            print(f"Mode: {pil_img.mode}")
            print(f"Size: {pil_img.size}")

            # Check for EXIF data
            if hasattr(pil_img, "_getexif") and pil_img._getexif() is not None:
                exif = pil_img._getexif()
                print(f"EXIF data found: {len(exif)} entries")
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    print(f"  {tag}: {value}")
            else:
                print("No EXIF data found")

            # Check for other metadata
            info = pil_img.info
            if info:
                print(f"PIL Info metadata: {len(info)} entries")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            else:
                print("No PIL Info metadata found")

            # Check compression and quality
            if "compression" in info:
                print(f"Compression: {info['compression']}")
            if "quality" in info:
                print(f"Quality: {info['quality']}")

            # Check DPI information and calculate physical size
            dpi_x = dpi_y = None

            # Try to get DPI from various sources
            if hasattr(pil_img, "info") and "dpi" in pil_img.info:
                dpi_info = pil_img.info["dpi"]
                if isinstance(dpi_info, tuple) and len(dpi_info) >= 2:
                    dpi_x, dpi_y = dpi_info[0], dpi_info[1]
                else:
                    dpi_x = dpi_y = dpi_info
                print(f"DPI: {dpi_info}")
            elif hasattr(pil_img, "tag") and "dpi" in pil_img.tag:
                dpi_info = pil_img.tag["dpi"]
                dpi_x = dpi_y = dpi_info
                print(f"DPI (from tag): {dpi_info}")
            else:
                print("No DPI information found")

            # Try to detect document contour using contour detector
            detected_contour = None
            contour_angle = None
            try:
                print("\nCONTOUR DETECTION:")
                # Load image with OpenCV for contour detection
                cv_image = cv2.imread(image_path)
                if cv_image is not None:
                    print("  Loading image for contour detection...")

                    # Preprocess image to get binary mask
                    thresh, border_rgb = preprocess_image(
                        cv_image, show_step_by_step=DEBUG
                    )

                    # Find page contour
                    detected_contour, contour_angle = find_page_contour(
                        thresh, show_step_by_step=DEBUG, original_image=cv_image
                    )

                    if detected_contour is not None:
                        contour_area_px = cv2.contourArea(detected_contour)
                        contour_rect = cv2.boundingRect(detected_contour)
                        print("  [OK] Document contour detected!")
                        print(f"     Contour area: {contour_area_px:.0f} pixels^2")
                        print(
                            f"     Bounding box: {contour_rect[2]} x {contour_rect[3]} pixels"
                        )
                        if contour_angle is not None:
                            print(f"     Document rotation: {contour_angle:.1f} gradi")
                    else:
                        print("  [NO] No document contour detected")
                else:
                    print("  [ERROR] Could not load image with OpenCV")
            except Exception as contour_error:
                print(f"  [ERROR] Error during contour detection: {contour_error}")

            # Calculate physical dimensions in cm if DPI is available
            if dpi_x and dpi_y:
                try:
                    width_px, height_px = pil_img.size

                    # Convert DPI to float to handle Fraction objects
                    dpi_x_float = float(dpi_x)
                    dpi_y_float = float(dpi_y)

                    # Convert pixels to inches, then to cm
                    width_inches = width_px / dpi_x_float
                    height_inches = height_px / dpi_y_float
                    width_cm = width_inches * 2.54
                    height_cm = height_inches * 2.54

                    print("\nPHYSICAL DIMENSIONS:")
                    print("\n[INFO] FULL IMAGE:")
                    print(f"  Size in pixels: {width_px} x {height_px}")
                    print(f"  DPI: {dpi_x_float:.1f} x {dpi_y_float:.1f}")
                    print(
                        f'  Size in inches: {width_inches:.2f}" x {height_inches:.2f}"'
                    )
                    print(f"  Size in cm: {width_cm:.2f} cm x {height_cm:.2f} cm")

                    # Calculate area
                    area_cm2 = width_cm * height_cm
                    print(f"  Area: {area_cm2:.2f} cm^2")

                    # Calculate detected document dimensions if contour was found
                    if detected_contour is not None:
                        doc_width_cm, doc_height_cm, doc_area_cm2 = (
                            calculate_contour_dimensions(
                                detected_contour, dpi_x_float, dpi_y_float
                            )
                        )
                        if doc_width_cm is not None:
                            print("\n[INFO] DETECTED DOCUMENT:")
                            contour_rect = cv2.boundingRect(detected_contour)
                            doc_width_px, doc_height_px = (
                                contour_rect[2],
                                contour_rect[3],
                            )
                            doc_width_inches = doc_width_cm / 2.54
                            doc_height_inches = doc_height_cm / 2.54
                            print(f"  Size in pixels: {doc_width_px} x {doc_height_px}")
                            print(
                                f'  Size in inches: {doc_width_inches:.2f}" x {doc_height_inches:.2f}"'
                            )
                            print(
                                f"  Size in cm: {doc_width_cm:.2f} cm x {doc_height_cm:.2f} cm"
                            )
                            print(f"  Area: {doc_area_cm2:.2f} cm^2")

                            # Use document dimensions for format detection instead of full image
                            width_cm, height_cm, area_cm2 = (
                                doc_width_cm,
                                doc_height_cm,
                                doc_area_cm2,
                            )
                        else:
                            print(
                                "\n[INFO] DETECTED DOCUMENT: Unable to calculate dimensions"
                            )
                    else:
                        print(
                            "\n[INFO] DETECTED DOCUMENT: No contour detected, using full image"
                        )

                    # Standard paper sizes for reference
                    print("\n[INFO] REFERENCE SIZES:")
                    print("  A4: 21.0 x 29.7 cm")
                    print("  A3: 29.7 x 42.0 cm")
                    print("  A2: 42.0 x 59.4 cm")
                    print("  A1: 59.4 x 84.1 cm")
                    print("  A0: 84.1 x 118.9 cm")

                    # Check if image matches specific paper formats
                    print("\nFORMAT DETECTION:")

                    # Define tolerances (+/-15% for "more or less" matching)
                    tolerance = 0.15

                    # A4 dimensions
                    a4_w, a4_h = 21.0, 29.7
                    # A3 dimensions
                    a3_w, a3_h = 29.7, 42.0

                    def matches_size(actual_w, actual_h, target_w, target_h, tolerance):
                        """Check if actual dimensions match target within tolerance"""
                        w_diff = abs(actual_w - target_w) / target_w
                        h_diff = abs(actual_h - target_h) / target_h
                        return w_diff <= tolerance and h_diff <= tolerance

                    # Check orientation
                    is_portrait = height_cm > width_cm
                    is_landscape = width_cm > height_cm

                    print(
                        f"  Orientation: {'Portrait (H>W)' if is_portrait else 'Landscape (W>H)' if is_landscape else 'Square'}"
                    )

                    # Check A4 vertical (portrait)
                    if is_portrait and matches_size(
                        width_cm, height_cm, a4_w, a4_h, tolerance
                    ):
                        print("  [OK] MATCHES: A4 Vertical (Portrait)")
                        print(f"     Expected: {a4_w} x {a4_h} cm")
                        print(f"     Actual:   {width_cm:.1f} x {height_cm:.1f} cm")

                    # Check A3 horizontal (landscape)
                    elif is_landscape and matches_size(
                        width_cm, height_cm, a3_h, a3_w, tolerance
                    ):
                        print("  [OK] MATCHES: A3 Horizontal (Landscape)")
                        print(f"     Expected: {a3_h} x {a3_w} cm")
                        print(f"     Actual:   {width_cm:.1f} x {height_cm:.1f} cm")

                    # Check other possibilities
                    else:
                        print("  [NO] No exact match found")

                        # Check if close to A4 vertical
                        if is_portrait:
                            w_diff_a4 = abs(width_cm - a4_w) / a4_w * 100
                            h_diff_a4 = abs(height_cm - a4_h) / a4_h * 100
                            print(
                                f"     A4 Vertical difference: W {w_diff_a4:.1f}%, H {h_diff_a4:.1f}%"
                            )

                        # Check if close to A3 horizontal
                        if is_landscape:
                            w_diff_a3 = abs(width_cm - a3_h) / a3_h * 100
                            h_diff_a3 = abs(height_cm - a3_w) / a3_w * 100
                            print(
                                f"     A3 Horizontal difference: W {w_diff_a3:.1f}%, H {h_diff_a3:.1f}%"
                            )

                except Exception as calc_error:
                    print(f"Error calculating physical dimensions: {calc_error}")
            else:
                print("Cannot calculate physical dimensions without DPI information")

    except Exception as e:
        print(f"Error reading metadata: {e}")

    print("=== END TIF METADATA TEST ===\n")
