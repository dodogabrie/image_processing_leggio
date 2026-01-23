"""
crop.py

Script per il rilevamento automatico della piega di un libro in una scansione,
crop e rotazione dell'immagine, e salvataggio in formato JPG.

Funzionalità principali:
- Rilevamento automatico del lato della piega (sinistra/destra/centro)
- Stima dell'angolo della piega tramite fit parabolico e regressione lineare
- Crop e rotazione per portare la piega al bordo dell'immagine
- Salvataggio dell'immagine croppata e ridimensionata
- Opzionale: generazione di immagini di debug per analisi visiva

Utilizzo:
    python crop.py input.jpg [--side left|right|center] output.jpg [--debug]
"""

import argparse
import os

from src.contour_detector.utils import save_image_with_metadata, save_outputs
from src.debug_tools import save_debug_line_visualization
from src.extract_doc_size import test_lab

# auto_detect_side removed - fold is always center
from src.image_io import generate_output_paths, load_image
from src.image_processing import process_image
from src.page_processor import process_page_if_needed

from src.utils import resize_width_hd


def main():
    """
    Parsing degli argomenti, caricamento immagine, rilevamento piega, crop, rotazione e salvataggio.
    """
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--side", choices=("left", "right", "center"), default=None)
    p.add_argument("out", nargs="?")
    p.add_argument("--debug", action="store_true")
    p.add_argument(
        "--output_format",
        choices=("jpg", "png", "tiff"),
        default=None,
        help="Output format. If specified, images will be resized to HD and converted to this format.",
    )
    p.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help="Apply rotation to straighten the fold. Default is False.",
    )
    p.add_argument(
        "--smart_crop",
        action="store_true",
        default=False,
        help="Use document edge detection for intelligent cropping. Default is False.",
    )
    p.add_argument(
        "--input_base_dir",
        default=None,
        help="Base directory for preserving folder structure in batch processing.",
    )
    p.add_argument(
        "--test-lab",
        action="store_true",
        default=False,
        help="Run metadata test only, skip normal processing.",
    )
    p.add_argument(
        "--contour-border",
        type=int,
        default=150,
        help="Border pixels for contour detection perspective correction (default: 150).",
    )
    p.add_argument(
        "--fold-border",
        type=int,
        default=None,
        help="Border pixels around fold line for overlapping content (default: same as contour-border).",
    )
    p.add_argument(
        "--save-thumbs",
        action="store_true",
        default=False,
        help="Generate before/after comparison thumbnails (default: False).",
    )
    p.add_argument(
        "--no-rename",
        action="store_true",
        default=False,
        help="Force standard processing without ICCD renaming (for consistency with batch mode).",
    )
    p.add_argument(
        "--coverage-threshold",
        type=float,
        default=0.90,
        help="Skip contour processing if document covers this percentage of image (0.0-1.0, default: 0.90).",
    )
    p.add_argument(
        "--generate-dataset",
        action="store_true",
        default=False,
        help="Generate AI training dataset (512x512 images + JSON labels + debug visualizations).",
    )
    args = p.parse_args()

    # If fold_border not specified, use same value as contour_border
    if args.fold_border is None:
        args.fold_border = args.contour_border

    # If test lab mode, run only metadata test
    if args.test_lab:
        test_lab(args.input)
        return

    # Load image without quality loss
    print("Loading image...")
    img = load_image(args.input)

    # Generate output paths - modify extension if output format is specified
    if args.output_format:
        # Override extension based on output format
        input_base, _ = os.path.splitext(args.input)
        if args.out and not os.path.isdir(args.out):
            # If specific output file provided, change its extension
            output_base, _ = os.path.splitext(args.out)
            modified_out = output_base + f".{args.output_format}"
        else:
            modified_out = args.out
        path_left, path_right, base_path = generate_output_paths(
            args.input, modified_out, args.input_base_dir
        )
        # Ensure the extensions match the output format
        base_left, _ = os.path.splitext(path_left)
        base_right, _ = os.path.splitext(path_right)
        path_left = base_left + f".{args.output_format}"
        path_right = base_right + f".{args.output_format}"
    else:
        path_left, path_right, base_path = generate_output_paths(
            args.input, args.out, args.input_base_dir
        )

    debug_dir = None
    if args.debug:
        debug_dir = base_path + "_debug"

    # Initialize dataset writer if dataset generation is enabled
    dataset_writer = None
    if args.generate_dataset:
        from src.dataset.dataset_writer import DatasetWriter
        # Determine output directory (use parent directory of base_path)
        output_dir = os.path.dirname(base_path) if base_path else os.path.dirname(args.input)
        if not output_dir:
            output_dir = "."
        dataset_writer = DatasetWriter(output_dir)
        print("[DATASET] AI training dataset generation ENABLED")

    side = "center" if args.side is None else args.side

    if side not in ("left", "right", "center"):
        print("Attenzione: Lato della piega non rilevato, salvo originale")
        if args.output_format:
            # Resize and convert format
            width = min(1920, img.shape[1])
            hd_img = resize_width_hd(img, target_width=width)
            save_image_with_metadata(hd_img, path_left, args.input)
        else:
            # Save at maximum quality without resizing
            save_image_with_metadata(img, path_left, args.input)
        return

    # Apply page processing (contour detection for A3 landscape)
    print("Applying page detection...")
    processed_img, was_processed, actual_border, is_a3, page_contour, transform_M = process_page_if_needed(
        img,
        image_path=args.input,
        debug=args.debug,
        contour_border=args.contour_border,
        coverage_threshold=args.coverage_threshold,
    )
    if was_processed:
        print(
            f"[OK] Applicato processing pagina (correzione prospettiva A3 landscape) - border: {actual_border}px"
        )
    elif is_a3:
        print("[INFO] Processing pagina saltato (A3 landscape già ben inquadrato, coverage >= 90%)")
    else:
        print("[INFO] Processing pagina saltato (formato non A3 landscape)")

    # Show A3 detection result
    if is_a3:
        print(
            "[A3 DETECTION] Document is A3 landscape (detected from contour dimensions)"
        )
    else:
        print("[A3 DETECTION] Document is NOT A3 landscape")

    # Show page detection result
    print(f"[PAGE DETECTION] Page is {actual_border}px")
    print("Detecting left and right sides...")
    left_side, right_side, debug_info = process_image(
        processed_img,
        side,
        debug=args.debug,
        debug_dir=debug_dir,
        apply_rotation=args.rotate,
        smart_crop=args.smart_crop,
        fold_border=args.fold_border,
        image_path=args.input,
        quality_threshold=0.6,  # Default quality threshold for fold detection
        is_a3_format=is_a3,  # Use A3 detection result from contour analysis
    )

    rotation_status = (
        "con rotazione" if debug_info["rotation_applied"] else "senza rotazione"
    )
    crop_status = "smart crop" if debug_info["smart_crop_applied"] else "crop standard"
    print(
        f"x: {debug_info['x_fold']}, inclinazione stimata: {debug_info['angle']:.2f} gradi, processato {rotation_status}, {crop_status}"
    )

    if debug_dir:
        save_debug_line_visualization(
            processed_img,
            debug_info["x_fold"],
            debug_info["angle"],
            debug_info["slope"],
            debug_info["intercept"],
            os.path.join(debug_dir, "fold_line_visualization.jpg"),
        )

    # Process and save results based on fold detection
    fold_detected = debug_info["x_fold"] is not None

    # Generate dataset sample if dataset_writer enabled
    if dataset_writer is not None:
        try:
            fold_x = debug_info.get("x_fold")
            dataset_writer.add_sample(
                original_img=img,
                filename=os.path.basename(args.input),
                page_corners_original=page_contour,
                rectified_img=processed_img,
                transformation_matrix=transform_M,
                fold_x=fold_x,
                fold_detected=fold_detected
            )
        except Exception as e:
            print(f"[DATASET] Warning: Failed to generate dataset sample: {e}")

    if fold_detected:
        # Fold detection applied - save left and right sides with _left/_right suffix
        if left_side is not None:
            if args.output_format:
                # Resize and convert format
                width = min(1920, left_side.shape[1])
                left_processed = resize_width_hd(left_side, target_width=width)
            else:
                # Save at maximum quality without resizing
                left_processed = left_side

            save_image_with_metadata(left_processed, path_left, args.input)
            print(f"Salvato lato sinistro: {path_left}")

        if right_side is not None:
            if args.output_format:
                # Resize and convert format
                width = min(1920, right_side.shape[1])
                right_processed = resize_width_hd(right_side, target_width=width)
            else:
                # Save at maximum quality without resizing
                right_processed = right_side

            save_image_with_metadata(right_processed, path_right, args.input)
            print(f"Salvato lato destro: {path_right}")
    else:
        # No fold detection - save with original name (no _left/_right suffix)
        input_base, input_ext = os.path.splitext(args.input)
        input_filename = os.path.basename(input_base)

        if args.out and not os.path.isdir(args.out):
            # Specific output file provided
            original_output_path = args.out
        else:
            # Directory output or default
            if args.out and os.path.isdir(args.out):
                original_output_path = os.path.join(
                    args.out, os.path.basename(args.input)
                )
            else:
                original_output_path = args.input  # Same location as input

        # Change extension if output format specified
        if args.output_format:
            original_output_path = (
                os.path.splitext(original_output_path)[0] + f".{args.output_format}"
            )

        if args.output_format:
            # Resize and convert format
            width = min(1920, left_side.shape[1])
            processed = resize_width_hd(left_side, target_width=width)
        else:
            # Save at maximum quality without resizing
            processed = left_side

        save_image_with_metadata(processed, original_output_path, args.input)
        print(f"Salvato immagine originale processata: {original_output_path}")

    # Generate comparison thumbnails if requested
    if args.save_thumbs:
        print("Generando thumbnails di confronto...")
        thumb_dir = base_path + "_thumbs"
        os.makedirs(thumb_dir, exist_ok=True)  # Ensure thumbnail directory exists

        if left_side is not None:
            # Use true original (uncropped) vs final processed result
            save_outputs(
                img,  # True original image (uncropped, unprocessed)
                left_processed,  # Final processed left side
                path_left,  # This will be ignored since we only want thumbs
                output_path_thumb=thumb_dir,
                original_path=args.input,
            )
            print(f"Thumbnail lato sinistro: {thumb_dir}")

        if right_side is not None:
            # Use true original (uncropped) vs final processed result
            save_outputs(
                img,  # True original image (uncropped, unprocessed)
                right_processed,  # Final processed right side
                path_right,  # This will be ignored since we only want thumbs
                output_path_thumb=thumb_dir,
                original_path=args.input,
            )
            print(f"Thumbnail lato destro: {thumb_dir}")

    # Finalize dataset generation
    if dataset_writer is not None:
        dataset_writer.finalize()


if __name__ == "__main__":
    main()
