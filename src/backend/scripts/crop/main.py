#!/usr/bin/env python3

import argparse
import shutil
import json
import os
import sys
import time
from datetime import datetime
import cv2
import numpy as np

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from src.contour_detector.utils import save_outputs
from src.debug_tools import save_debug_line_visualization
from src.file_listener import create_default_rename_map, start_file_listener_thread
from src.image_io import generate_output_paths, load_image, save_image_preserve_format

# auto_detect_side removed - fold is always center
from src.image_processing import process_image
from src.page_processor import process_page_if_needed

from src.utils import resize_width_hd


def find_images_recursive(
    input_dir, format_extensions=[".tif", ".tiff", ".jpg", ".jpeg"]
):
    """
    Trova tutti i file immagine ricorsivamente nella directory di input.

    Args:
        input_dir (str): Directory di input
        format_extensions (list): Lista di estensioni da cercare

    Returns:
        list: Lista dei percorsi completi dei file immagine trovati
    """
    image_files = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in format_extensions:
                image_files.append(os.path.join(root, f))
    return image_files


def load_crop_mapping(input_dir):
    """
    Carica il file crop_mapping.json se presente nella directory di input.

    Args:
        input_dir (str): Directory di input

    Returns:
        dict or None: Mapping caricato o None se il file non esiste
    """
    crop_mapping_path = os.path.join(input_dir, "crop_mapping.json")
    if not os.path.exists(crop_mapping_path):
        return None

    try:
        with open(crop_mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        print(f"[INFO] Caricato crop_mapping.json con {len(mapping)} voci")
        return mapping
    except Exception as e:
        print(f"[WARNING] Errore nel caricamento di crop_mapping.json: {e}")
        return None


def write_info_json(output_dir, info_data):
    """Scrive il file info.json nella directory di output."""
    info_path = os.path.join(output_dir, "info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info_data, f, indent=2, ensure_ascii=False)


def save_error_json(output_dir, error_data):
    """
    Salva il file error.json nella directory di output con i file da ricontrollare.

    Args:
        output_dir (str): Directory di output
        error_data (dict): Dizionario con struttura {"Ricontrollare": [...]}
    """
    if not error_data.get("Ricontrollare"):
        # Non creare il file se non ci sono errori
        return

    error_path = os.path.join(output_dir, "error.json")
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(error_data, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Salvato error.json con {len(error_data['Ricontrollare'])} file da ricontrollare")


def update_cropped_files_mapping(info_data, original_path, cropped_files, output_base_dir,
                                 debug_info=None, page_contour=None, transform_M=None, was_processed=False):
    """
    Aggiorna la mappa dei file croppati nell'info_data.

    Args:
        info_data (dict): Struttura dati info.json
        original_path (str): Percorso del file originale
        cropped_files (list): Lista dei file generati dal cropping
        output_base_dir (str): Directory base di output per i percorsi relativi
        debug_info (dict): Debug info from processing (contains fold detection status, rotation, etc.)
        page_contour (np.ndarray): Page contour if detected, None otherwise
        transform_M (np.ndarray): Transformation matrix if perspective correction applied, None otherwise
        was_processed (bool): True if perspective correction was applied
    """
    # Get just the filename (not full path) for original file
    original_filename = os.path.basename(original_path)

    # Get relative paths and full paths for cropped files
    cropped_relative_paths = []
    cropped_full_paths = []
    cropped_filenames = []

    for f in cropped_files:
        if f:
            # Store full absolute path
            cropped_full_paths.append(f)

            # Store just the filename
            cropped_filenames.append(os.path.basename(f))

            # Convert absolute path to relative path from output_base_dir
            try:
                relative_path = os.path.relpath(f, output_base_dir)
                cropped_relative_paths.append(relative_path)
            except ValueError:
                # If relpath fails, fall back to just the filename
                cropped_relative_paths.append(os.path.basename(f))

    if cropped_relative_paths:
        # Create comprehensive metadata entry
        metadata = {
            "output_files": cropped_filenames,  # Just filenames for compatibility
            "output_paths": cropped_full_paths,  # Full absolute paths
            "output_relative_paths": cropped_relative_paths,  # Relative paths
            "fold_detected": debug_info.get("x_fold") is not None if debug_info else False,
            "page_detected": page_contour is not None,
            "was_rotated": debug_info.get("rotation_applied", False) if debug_info else False,
            "was_perspective_corrected": was_processed,
        }

        info_data["cropped"][original_filename] = metadata


def get_file_size_gb(file_path):
    """Ottiene la dimensione del file in GB."""
    return os.path.getsize(file_path) / (1024**3)


def copy_directory_structure(input_dir, output_dir, image_extensions=[".tif", ".tiff", ".jpg", ".jpeg"]):
    """
    Copia la struttura completa delle directory e i file non-immagine dall'input all'output.

    Args:
        input_dir (str): Directory di input
        output_dir (str): Directory di output
        image_extensions (list): Estensioni dei file immagine da non copiare (saranno processati separatamente)

    Returns:
        int: Numero di file copiati
    """
    files_copied = 0

    for root, dirs, files in os.walk(input_dir):
        # Calcola il percorso relativo dalla directory di input
        rel_path = os.path.relpath(root, input_dir)

        # Crea la directory corrispondente nell'output
        if rel_path == ".":
            target_dir = output_dir
        else:
            target_dir = os.path.join(output_dir, rel_path)

        os.makedirs(target_dir, exist_ok=True)

        # Copia i file non-immagine
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()

            # Salta i file immagine (saranno processati separatamente)
            if file_ext in image_extensions:
                continue

            # Copia il file preservando i metadati
            source_path = os.path.join(root, file)
            target_path = os.path.join(target_dir, file)

            try:
                shutil.copy2(source_path, target_path)
                files_copied += 1
            except Exception as e:
                print(f"[WARNING] Could not copy {source_path}: {e}")

    return files_copied


def copy_unprocessed_image(source_path, output_dir, input_base_dir):
    """
    Copia un'immagine non processata preservando la struttura delle directory.

    Args:
        source_path (str): Percorso dell'immagine sorgente
        output_dir (str): Directory di output
        input_base_dir (str): Directory base di input per preservare la struttura

    Returns:
        str: Percorso del file copiato
    """
    # Calcola il percorso relativo
    rel_path = os.path.relpath(source_path, input_base_dir)
    target_path = os.path.join(output_dir, rel_path)

    # Assicurati che la directory target esista
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # Copia il file preservando i metadati
    shutil.copy2(source_path, target_path)

    return target_path


def process_single_image(
    input_path,
    output_dir,
    input_base_dir,
    side=None,
    output_format=None,
    apply_rotation=False,
    smart_crop=False,
    debug=False,
    verbose=True,
    contour_border=150,
    fold_border=None,
    save_thumbs=False,
    quality_threshold=0.6,
    crop_mapping_entry=None,
    dataset_writer=None,
):
    """
    Processa una singola immagine usando la funzionalità di crop.py

    Args:
        input_path (str): Percorso dell'immagine di input
        output_dir (str): Directory di output
        input_base_dir (str): Directory base di input per preservare la struttura
        side (str): Lato della piega ('left', 'right', 'center', None per auto-detect)
        output_format (str): Formato di output ('jpg', 'png', 'tiff', None per mantenere originale)
        apply_rotation (bool): Se applicare la rotazione
        smart_crop (bool): Se usare il crop intelligente
        debug (bool): Se generare file di debug
        crop_mapping_entry (list): Lista di percorsi di output dal crop_mapping.json (opzionale)

    Returns:
        tuple: (success, message, debug_info, error_reason)
    """
    try:
        # If fold_border not specified, use same value as contour_border
        if fold_border is None:
            fold_border = contour_border

        # Carica l'immagine
        img = load_image(input_path)

        # Genera i percorsi di output preservando la struttura delle cartelle
        if output_format:
            # Cambia l'estensione se specificato un formato
            input_base, _ = os.path.splitext(input_path)
            modified_output = output_dir
        else:
            modified_output = output_dir

        # Usa generate_output_paths con input_base_dir per preservare la struttura
        path_left, path_right, base_path = generate_output_paths(
            input_path, modified_output, input_base_dir
        )

        # Se è specificato un formato, aggiorna le estensioni
        if output_format:
            base_left, _ = os.path.splitext(path_left)
            base_right, _ = os.path.splitext(path_right)
            path_left = base_left + f".{output_format}"
            path_right = base_right + f".{output_format}"

        # Debug directory
        debug_dir = None
        if debug:
            debug_dir = base_path + "_debug"

        # Rileva il lato automaticamente se non specificato
        detected_side = "center" if side is None else side

        if detected_side not in ("left", "right", "center"):
            # Salva originale se non rilevato
            if output_format:
                width = min(1920, img.shape[1])
                hd_img = resize_width_hd(img, target_width=width)
                save_image_preserve_format(hd_img, path_left)
            else:
                save_image_preserve_format(img, path_left)

            return (
                True,
                f"Piega non rilevata, salvato originale: {path_left}",
                {"x_fold": None, "angle": None, "side": detected_side},
                "Side not detected" if crop_mapping_entry else None,
            )

        # Apply page processing (contour detection for A3 landscape)
        processed_img, was_processed, actual_border, is_a3, page_contour, transform_M = process_page_if_needed(
            img, image_path=input_path, debug=debug, contour_border=contour_border, coverage_threshold=0.90
        )
        if verbose and was_processed:
            print(
                f"  [OK] Applicato processing pagina (correzione prospettiva A3 landscape) - border: {actual_border}px"
            )
        elif verbose and is_a3:
            print("  [INFO] Processing pagina saltato (A3 landscape già ben inquadrato, coverage >= 90%)")
        elif verbose:
            print("  [INFO] Processing pagina saltato (formato non A3 landscape)")

        # Processa l'immagine
        left_side, right_side, debug_info = process_image(
            processed_img,
            detected_side,
            debug=debug,
            debug_dir=debug_dir,
            apply_rotation=apply_rotation,
            smart_crop=smart_crop,
            fold_border=fold_border,
            image_path=input_path,
            quality_threshold=0.6,  # Default quality threshold for fold detection
            is_a3_format=is_a3,  # Use A3 detection result from contour analysis
        )

        # Salva le immagini debug
        if debug_dir and debug_info.get("x_fold") is not None:
            save_debug_line_visualization(
                processed_img,
                debug_info["x_fold"],
                debug_info["angle"],
                debug_info["slope"],
                debug_info["intercept"],
                os.path.join(debug_dir, "fold_line_visualization.jpg"),
                original_img=img,  # Original image before rectification
                transformation_matrix=transform_M  # Transformation matrix from warp_image
            )

        # Salva i risultati
        saved_files = []
        error_reason = None

        # Check if fold detection was applied
        fold_detected = debug_info["x_fold"] is not None

        # Handle crop mapping if provided
        if crop_mapping_entry and fold_detected:
            # Use crop mapping paths for saving
            # crop_mapping_entry contains the list of output paths from crop_mapping.json
            # We need to save left_side and right_side to these paths

            # Prepare processed images
            processed_images = []
            if left_side is not None:
                if output_format:
                    width = min(1920, left_side.shape[1])
                    processed_images.append(resize_width_hd(left_side, target_width=width))
                else:
                    processed_images.append(left_side)

            if right_side is not None:
                if output_format:
                    width = min(1920, right_side.shape[1])
                    processed_images.append(resize_width_hd(right_side, target_width=width))
                else:
                    processed_images.append(right_side)

            # Save to crop_mapping paths
            if len(processed_images) >= len(crop_mapping_entry):
                for i, output_path in enumerate(crop_mapping_entry):
                    if i < len(processed_images):
                        full_output_path = os.path.join(output_dir, output_path)
                        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
                        save_image_preserve_format(processed_images[i], full_output_path)
                        saved_files.append(full_output_path)
            else:
                error_reason = f"Not enough cropped images ({len(processed_images)}) for mapping ({len(crop_mapping_entry)})"

        elif crop_mapping_entry and not fold_detected:
            # Crop mapping provided but fold detection failed
            # Save original image and return error
            original_output_path = base_path + os.path.splitext(input_path)[1]
            if output_format:
                original_output_path = os.path.splitext(original_output_path)[0] + f".{output_format}"
                width = min(1920, processed_img.shape[1])
                processed = resize_width_hd(processed_img, target_width=width)
            else:
                processed = processed_img

            save_image_preserve_format(processed, original_output_path)
            saved_files.append(original_output_path)
            error_reason = "Fold detection failed - crop mapping requires fold"

        elif fold_detected:
            # Fold detection applied - save left and right sides
            if left_side is not None:
                if output_format:
                    width = min(1920, left_side.shape[1])
                    left_processed = resize_width_hd(left_side, target_width=width)
                else:
                    left_processed = left_side

                save_image_preserve_format(left_processed, path_left)
                saved_files.append(path_left)

            if right_side is not None:
                if output_format:
                    width = min(1920, right_side.shape[1])
                    right_processed = resize_width_hd(right_side, target_width=width)
                else:
                    right_processed = right_side

                save_image_preserve_format(right_processed, path_right)
                saved_files.append(path_right)
        else:
            # No fold detection - save with original name (no _left/_right suffix)
            original_output_path = base_path + os.path.splitext(input_path)[1]

            if output_format:
                # Change extension if output format specified
                original_output_path = (
                    os.path.splitext(original_output_path)[0] + f".{output_format}"
                )
                width = min(1920, left_side.shape[1])
                processed = resize_width_hd(left_side, target_width=width)
            else:
                processed = left_side

            save_image_preserve_format(processed, original_output_path)
            saved_files.append(original_output_path)

        # Generate comparison thumbnails if requested
        if save_thumbs:
            thumb_dir = base_path + "_thumbs"
            os.makedirs(thumb_dir, exist_ok=True)

            if left_side is not None:
                # For thumbnails: use original full image vs processed result
                save_outputs(
                    img,  # True original image (uncropped, unprocessed)
                    left_processed,  # Final processed result
                    path_left,  # This will be ignored since we only want thumbs
                    output_path_thumb=thumb_dir,
                    original_path=input_path,
                )

            if right_side is not None:
                # For thumbnails: use original full image vs processed result
                save_outputs(
                    img,  # True original image (uncropped, unprocessed)
                    right_processed,  # Final processed result
                    path_right,  # This will be ignored since we only want thumbs
                    output_path_thumb=thumb_dir,
                    original_path=input_path,
                )

        debug_info["side"] = detected_side
        debug_info["saved_files"] = saved_files
        debug_info["page_contour"] = page_contour
        debug_info["transform_M"] = transform_M
        debug_info["was_processed"] = was_processed

        # Generate dataset sample if dataset_writer provided
        if dataset_writer is not None:
            try:
                # Extract fold information from debug_info
                fold_x = debug_info.get("x_fold")
                fold_detected = fold_x is not None

                # Calculate fold line endpoints in original image space
                fold_p1_original = None
                fold_p2_original = None

                if fold_detected:
                    # Get fold line parameters (equation: x = slope * y + intercept)
                    slope = debug_info.get("slope", 0.0)
                    intercept = debug_info.get("intercept", 0.0)
                    x_fold = debug_info.get("x_fold")

                    # Get height of image where fold was detected (processed_img)
                    img_height = processed_img.shape[0]
                    img_width = processed_img.shape[1]

                    print(f"\n=== FOLD COORDINATE TRANSFORMATION DEBUG ===")
                    print(f"Fold detection: x_fold={x_fold}, slope={slope}, intercept={intercept}")
                    print(f"Rectified image size: {img_width}×{img_height}")
                    print(f"Original image size: {img.shape[1]}×{img.shape[0]}")
                    print(f"Border added to rectified image: {actual_border}px")

                    # Calculate fold line endpoints in rectified space
                    fold_p1_rect = (int(intercept), 0)
                    fold_p2_rect = (int(slope * img_height + intercept), img_height)
                    print(f"Fold in rectified space (with border): p1={fold_p1_rect}, p2={fold_p2_rect}")

                    # Subtract border to get coordinates in borderless rectified space
                    # (the space that M transforms from/to)
                    fold_p1_no_border = (fold_p1_rect[0] - actual_border, fold_p1_rect[1] - actual_border)
                    fold_p2_no_border = (fold_p2_rect[0] - actual_border, fold_p2_rect[1] - actual_border)
                    print(f"Fold in rectified space (no border): p1={fold_p1_no_border}, p2={fold_p2_no_border}")

                    # If image was rectified, inverse transform to original space
                    if transform_M is not None:
                        print(f"Transform M exists - applying inverse transformation")
                        print(f"Transform M:\n{transform_M}")

                        M_inv = cv2.invertAffineTransform(transform_M)
                        print(f"Inverse M:\n{M_inv}")

                        # Use borderless coordinates for transformation
                        p1_h = np.array([fold_p1_no_border[0], fold_p1_no_border[1], 1.0], dtype=np.float32)
                        p2_h = np.array([fold_p2_no_border[0], fold_p2_no_border[1], 1.0], dtype=np.float32)

                        p1_orig_h = M_inv @ p1_h
                        p2_orig_h = M_inv @ p2_h

                        print(f"Fold in original space (float): p1=({p1_orig_h[0]:.2f}, {p1_orig_h[1]:.2f}), p2=({p2_orig_h[0]:.2f}, {p2_orig_h[1]:.2f})")

                        fold_p1_original = (int(p1_orig_h[0]), int(p1_orig_h[1]))
                        fold_p2_original = (int(p2_orig_h[0]), int(p2_orig_h[1]))

                        print(f"Fold in original space (int): p1={fold_p1_original}, p2={fold_p2_original}")
                    else:
                        print(f"No transform M - fold already in original space")
                        # No rectification - fold already in original space
                        fold_p1_original = fold_p1_rect
                        fold_p2_original = fold_p2_rect

                    # Also show page contour for comparison
                    if page_contour is not None:
                        print(f"\nPage contour in original space:")
                        contour_flat = page_contour.reshape(-1, 2)
                        page_min_x = contour_flat[:, 0].min()
                        page_max_x = contour_flat[:, 0].max()
                        page_min_y = contour_flat[:, 1].min()
                        page_max_y = contour_flat[:, 1].max()
                        print(f"  Min X: {page_min_x:.2f}, Max X: {page_max_x:.2f}")
                        print(f"  Min Y: {page_min_y:.2f}, Max Y: {page_max_y:.2f}")
                        print(f"  Corners: {contour_flat[:4]}")

                        # CRITICAL INSIGHT: The transform M is almost identity!
                        # This means it's NOT mapping from full original image to warped.
                        # Instead, it's mapping within a coordinate space that's already document-relative.
                        # We need to add the document offset in original image!
                        print(f"\n[CRITICAL] Transform M is near-identity!")
                        print(f"  This means coordinates are document-relative, not full-image-relative")
                        print(f"  Adding document offset in original image...")

                        fold_p1_original = (
                            fold_p1_original[0] + int(page_min_x),
                            fold_p1_original[1] + int(page_min_y)
                        )
                        fold_p2_original = (
                            fold_p2_original[0] + int(page_min_x),
                            fold_p2_original[1] + int(page_min_y)
                        )

                        print(f"  Final fold in original space: p1={fold_p1_original}, p2={fold_p2_original}")

                        # Verify fold is within page bounds
                        print(f"\nVerification:")
                        print(f"  Fold X range: {fold_p1_original[0]} to {fold_p2_original[0]}")
                        print(f"  Page X range: {page_min_x:.0f} to {page_max_x:.0f}")
                        print(f"  Fold Y range: {fold_p1_original[1]} to {fold_p2_original[1]}")
                        print(f"  Page Y range: {page_min_y:.0f} to {page_max_y:.0f}")

                        # Check if fold is within page bounds
                        x_ok = page_min_x <= fold_p1_original[0] <= page_max_x
                        y_ok = page_min_y <= fold_p1_original[1] <= page_max_y and page_min_y <= fold_p2_original[1] <= page_max_y

                        if x_ok and y_ok:
                            print(f"  [OK] Fold is WITHIN page bounds!")
                        else:
                            if not x_ok:
                                print(f"  [WARNING] Fold X is outside page bounds!")
                            if not y_ok:
                                if fold_p2_original[1] > page_max_y:
                                    print(f"  [WARNING] Fold extends {fold_p2_original[1] - page_max_y:.0f}px below page bottom!")
                                if fold_p1_original[1] < page_min_y:
                                    print(f"  [WARNING] Fold extends {page_min_y - fold_p1_original[1]:.0f}px above page top!")

                    print(f"=== END DEBUG ===\n")

                # Call dataset writer with original (unprocessed) image
                dataset_writer.add_sample(
                    original_img=img,  # Original image loaded at line 245
                    filename=os.path.basename(input_path),
                    page_corners_original=page_contour,  # From process_page_if_needed
                    rectified_img=processed_img,  # Rectified image from process_page_if_needed
                    transformation_matrix=transform_M,  # From process_page_if_needed
                    fold_p1_original=fold_p1_original,  # Fold line endpoint 1 in original space
                    fold_p2_original=fold_p2_original,  # Fold line endpoint 2 in original space
                    fold_detected=fold_detected
                )
            except Exception as e:
                print(f"[DATASET] Warning: Failed to generate dataset sample for {os.path.basename(input_path)}: {e}")

        return True, f"Processato: {', '.join(saved_files)}", debug_info, error_reason

    except Exception as e:
        return False, f"Errore processing {input_path}: {str(e)}", {}, str(e)


def rename_couple_outputs(first_result, second_result, verbose=True):
    """
    Rinomina i file di output di una coppia front-back secondo il pattern 4-page.

    Args:
        first_result (dict): Risultato del processing della prima immagine (front)
        second_result (dict): Risultato del processing della seconda immagine (back)
        verbose (bool): Se mostrare output verbose

    Returns:
        tuple: (success, renamed_files_list)
    """
    renamed_files = []

    try:
        first_saved = first_result.get("saved_files", [])
        second_saved = second_result.get("saved_files", [])

        if len(first_saved) != 2 or len(second_saved) != 2:
            return False, []

        # Find left/right files for both images
        first_left = next((f for f in first_saved if "_left" in f), None)
        first_right = next((f for f in first_saved if "_right" in f), None)
        second_left = next((f for f in second_saved if "_left" in f), None)
        second_right = next((f for f in second_saved if "_right" in f), None)

        if not all([first_left, first_right, second_left, second_right]):
            return False, []

        # Get base name from first image (without _left/_right suffix)
        first_base = first_left.replace("_left", "").rsplit(".", 1)[0]
        first_ext = "." + first_left.rsplit(".", 1)[1]

        # Define new names based on 4-page pattern
        # First image: _left -> _4, _right -> _1
        # Second image: _left -> _2, _right -> _3, and use first image base name
        new_names = {
            first_left: first_base + "_crop_4" + first_ext,  # first left -> 4
            first_right: first_base + "_crop_1" + first_ext,  # first right -> 1
            second_left: first_base + "_crop_2" + first_ext,  # second left -> 2
            second_right: first_base + "_crop_3" + first_ext,  # second right -> 3
        }

        # Perform renaming
        for old_path, new_path in new_names.items():
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                renamed_files.append(new_path)
                if verbose:
                    print(
                        f"  Renamed: {os.path.basename(old_path)} -> {os.path.basename(new_path)}"
                    )
            else:
                print(f"  Warning: File not found for renaming: {old_path}")

        return True, renamed_files

    except Exception as e:
        print(f"  Error during couple renaming: {e}")
        return False, []


def rename_single_image_outputs(result, verbose=True):
    """
    Rinomina i file di output di una singola immagine da _left/_right a _4/_1.

    Args:
        result (dict): Risultato del processing dell'immagine
        verbose (bool): Se mostrare output verbose

    Returns:
        tuple: (success, renamed_files_list)
    """
    renamed_files = []

    try:
        saved_files = result.get("saved_files", [])

        if len(saved_files) != 2:
            return False, []

        # Find left/right files
        left_file = next((f for f in saved_files if "_left" in f), None)
        right_file = next((f for f in saved_files if "_right" in f), None)

        if not all([left_file, right_file]):
            return False, []

        # Get base name from first image (without _left/_right suffix)
        base_name = left_file.replace("_left", "").rsplit(".", 1)[0]
        ext = "." + left_file.rsplit(".", 1)[1]

        # Define new names: _left -> _4, _right -> _1
        new_names = {
            left_file: base_name + "_crop_4" + ext,  # left -> 4
            right_file: base_name + "_crop_1" + ext,  # right -> 1
        }

        # Perform renaming
        for old_path, new_path in new_names.items():
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                renamed_files.append(new_path)
                if verbose:
                    print(
                        f"  Renamed: {os.path.basename(old_path)} -> {os.path.basename(new_path)}"
                    )
            else:
                print(f"  Warning: File not found for renaming: {old_path}")

        return True, renamed_files

    except Exception as e:
        print(f"  Error during single image renaming: {e}")
        return False, []


def process_front_back_couples(
    image_files,
    output_dir,
    input_dir,
    info_data,
    error_data,
    crop_mapping=None,
    side=None,
    output_format=None,
    apply_rotation=False,
    smart_crop=False,
    debug=False,
    verbose=True,
    contour_border=150,
    fold_border=None,
    save_thumbs=False,
    dataset_writer=None,
):
    """
    Processa le immagini sequenzialmente e identifica coppie consecutive con crop riuscito.

    Args:
        image_files (list): Lista ordinata dei file immagine
        info_data (dict): Struttura dati info.json per tracciare i file croppati
        Altri args: come process_single_image

    Returns:
        tuple: (processed_count, error_count, renamed_count)
    """
    processed_count = 0
    error_count = 0
    renamed_count = 0

    # Store results from all processed images
    processing_results = []

    print(f"[INFO] Processing {len(image_files)} images sequentially to detect couples...")

    # Phase 1: Process all images sequentially
    for i, image_path in enumerate(image_files):
        rel_path = os.path.relpath(image_path, input_dir)
        print(f"[{i + 1}/{len(image_files)}] Processing: {rel_path}")

        # Get crop mapping entry for this image if available
        crop_mapping_entry = None
        if crop_mapping:
            # Find matching key in crop_mapping
            rel_path = os.path.relpath(image_path, input_dir)
            filename = os.path.basename(image_path)
            for mapping_key, mapping_value in crop_mapping.items():
                if filename in mapping_key or rel_path in mapping_key:
                    crop_mapping_entry = mapping_value
                    break

        success, message, debug_info, error_reason = process_single_image(
            image_path,
            output_dir,
            input_dir,
            side,
            output_format,
            apply_rotation,
            smart_crop,
            debug,
            False,  # verbose=False for cleaner output
            contour_border,
            fold_border,
            save_thumbs,
            crop_mapping_entry=crop_mapping_entry,
            dataset_writer=dataset_writer,
        )

        # Store result for couple detection
        result = {
            'index': i,
            'path': image_path,
            'success': success,
            'message': message,
            'debug_info': debug_info,
            'fold_detected': debug_info.get("x_fold") is not None,
            'crop_mapping_entry': crop_mapping_entry,  # Track if this image has crop mapping
        }
        processing_results.append(result)

        if success:
            processed_count += 1

            # Track error if present
            if error_reason:
                error_data["Ricontrollare"].append({
                    "fname": os.path.basename(image_path),
                    "fpath": image_path,
                    "reason": error_reason
                })

            # Track initial cropped files (before potential renaming)
            saved_files = debug_info.get("saved_files", [])
            if saved_files:
                # Note: These will be updated again in phases 3-4 with renamed files
                update_cropped_files_mapping(
                    info_data, image_path, saved_files, output_dir,
                    debug_info=debug_info,
                    page_contour=debug_info.get("page_contour"),
                    transform_M=debug_info.get("transform_M"),
                    was_processed=debug_info.get("was_processed", False)
                )

            if debug_info.get("x_fold"):
                print(f"  [OK] fold detected, {len(saved_files)} files renamed")
            else:
                print(f"  [OK] no fold, {len(saved_files)} files renamed")
        else:
            error_count += 1
            print(f"  [ERROR] {message}")

            # Copy original file to output when processing fails
            try:
                copied_path = copy_unprocessed_image(image_path, output_dir, input_dir)
                print(f"  [INFO] Copied original to: {copied_path}")
            except Exception as e:
                print(f"  [WARNING] Could not copy original: {e}")

            # Track error
            error_data["Ricontrollare"].append({
                "fname": os.path.basename(image_path),
                "fpath": image_path,
                "reason": error_reason if error_reason else message
            })

        # Update info.json after each image for progress tracking
        info_data["processed"] = i + 1
        write_info_json(output_dir, info_data)

    # Phase 2: Detect consecutive couples with successful fold detection
    print(f"\n[INFO] Phase 2: Detecting consecutive couples with fold detection...")

    couples_detected = []
    i = 0
    while i < len(processing_results) - 1:
        current = processing_results[i]
        next_img = processing_results[i + 1]

        # Skip images that have crop_mapping - they already have correct naming
        if current.get('crop_mapping_entry') or next_img.get('crop_mapping_entry'):
            i += 1
            continue

        # Check if both consecutive images have successful fold detection
        if (current['success'] and current['fold_detected'] and
            next_img['success'] and next_img['fold_detected']):

            couples_detected.append((current, next_img))
            if verbose:
                print(f"  [COUPLE] Found couple: {os.path.basename(current['path'])} + {os.path.basename(next_img['path'])}")
            i += 2  # Skip next image as it's part of this couple
        else:
            i += 1  # Move to next image

    print(f"[INFO] Detected {len(couples_detected)} couples for 4-page renaming")

    # Phase 3: Apply 4-page renaming to detected couples
    if couples_detected:
        print(f"\n[INFO] Phase 3: Applying 4-page renaming to {len(couples_detected)} couples...")

        for couple_idx, (first_result, second_result) in enumerate(couples_detected):
            print(f"[{couple_idx + 1}/{len(couples_detected)}] Processing couple: {os.path.basename(first_result['path'])} + {os.path.basename(second_result['path'])}")

            # Apply couple renaming
            success_rename, renamed_files = rename_couple_outputs(
                first_result['debug_info'], second_result['debug_info'], verbose
            )

            if success_rename:
                renamed_count += len(renamed_files)

                # Update cropped files mapping with correct file assignment
                first_original_filename = os.path.basename(first_result['path'])
                second_original_filename = os.path.basename(second_result['path'])

                # Get final relative paths (not just filenames) for renamed files
                renamed_filenames = [os.path.relpath(f, output_dir) for f in renamed_files]

                # Split files correctly: first image gets pages 1&4, second gets pages 2&3
                # Renamed files order: _crop_1, _crop_2, _crop_3, _crop_4
                first_files = []  # Pages 1 and 4
                second_files = [] # Pages 2 and 3

                for filename in renamed_filenames:
                    if "_crop_1" in filename or "_crop_4" in filename:
                        first_files.append(filename)
                    elif "_crop_2" in filename or "_crop_3" in filename:
                        second_files.append(filename)

                # Update mapping for each original image with its specific pages
                if first_files:
                    # Get full paths for renamed files
                    first_full_paths = [f for f in renamed_files if os.path.basename(f) in first_files]
                    update_cropped_files_mapping(
                        info_data, first_result['path'], first_full_paths, output_dir,
                        debug_info=first_result['debug_info'],
                        page_contour=first_result['debug_info'].get("page_contour"),
                        transform_M=first_result['debug_info'].get("transform_M"),
                        was_processed=first_result['debug_info'].get("was_processed", False)
                    )
                if second_files:
                    # Get full paths for renamed files
                    second_full_paths = [f for f in renamed_files if os.path.basename(f) in second_files]
                    update_cropped_files_mapping(
                        info_data, second_result['path'], second_full_paths, output_dir,
                        debug_info=second_result['debug_info'],
                        page_contour=second_result['debug_info'].get("page_contour"),
                        transform_M=second_result['debug_info'].get("transform_M"),
                        was_processed=second_result['debug_info'].get("was_processed", False)
                    )

                print(f"  [OK] Couple processed successfully - {len(renamed_files)} files renamed")
            else:
                print(f"  [ERROR] Couple validation failed - crops undone")

    # Phase 4: Handle single images with fold detection (not part of couples)
    print(f"\n[INFO] Phase 4: Processing single images with fold detection...")

    # Track which images were already processed as couples
    couple_indices = set()
    for first_result, second_result in couples_detected:
        couple_indices.add(first_result['index'])
        couple_indices.add(second_result['index'])

    # Find single images with fold detection that weren't part of couples
    # Skip images with crop_mapping_entry - they already have correct naming
    single_fold_images = []
    for result in processing_results:
        if (result['success'] and result['fold_detected'] and
            result['index'] not in couple_indices and
            not result.get('crop_mapping_entry')):
            single_fold_images.append(result)

    if single_fold_images:
        print(f"[INFO] Found {len(single_fold_images)} single images with fold detection for _crop_1/_crop_4 renaming")

        for single_idx, single_result in enumerate(single_fold_images):
            print(f"[{single_idx + 1}/{len(single_fold_images)}] Processing: {os.path.basename(single_result['path'])}")

            # Apply single image renaming (_left -> _crop_4, _right -> _crop_1)
            success_rename, renamed_files = rename_single_image_outputs(
                single_result['debug_info'], verbose
            )

            if success_rename:
                renamed_count += len(renamed_files)

                # Update cropped files mapping with final renamed files
                update_cropped_files_mapping(
                    info_data, single_result['path'], renamed_files, output_dir,
                    debug_info=single_result['debug_info'],
                    page_contour=single_result['debug_info'].get("page_contour"),
                    transform_M=single_result['debug_info'].get("transform_M"),
                    was_processed=single_result['debug_info'].get("was_processed", False)
                )

                print(f"  [OK] Only first image cropped - {len(renamed_files)} files renamed to _4/_1 pattern")
            else:
                print(f"  [ERROR] Failed to rename single image outputs")
    else:
        print("[INFO] No single images with fold detection found")

    return processed_count, error_count, renamed_count


def main(
    input_dir,
    output_dir,
    side=None,
    output_format=None,
    image_input_format=None,
    apply_rotation=False,
    smart_crop=False,
    debug=False,
    verbose=True,
    enable_file_listener=False,
    rename_map=None,
    contour_border=150,
    fold_border=None,
    save_thumbs=False,
    process_jpg=True,
    process_tiff=True,
    export_json_mapping=None,
    json_only=False,
    no_rename=False,
    front_back_couple=False,
    generate_dataset=False,
):
    """
    Funzione principale per processare le immagini in batch con supporto ICCD Busta.

    Args:
        input_dir (str): Directory di input
        output_dir (str): Directory di output
        side (str): Lato della piega (None per auto-detect)
        output_format (str): Formato di output
        image_input_format (str): Formato delle immagini di input da cercare
        apply_rotation (bool): Se applicare la rotazione
        smart_crop (bool): Se usare il crop intelligente
        debug (bool): Se generare file di debug
        verbose (bool): Se mostrare output verbose
        enable_file_listener (bool): Se abilitare il file listener per rinominazioni
        rename_map (dict): Mappa di rinominazione per il file listener
    """
    print("[INFO] Avvio elaborazione doppia pagina...")
    print(f"[INFO] Input directory: {input_dir}")
    print(f"[INFO] Output directory: {output_dir}")

    # Check if input contains ICCD Folder+XML structure
    try:
        # Add current directory to path for imports
        import sys

        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        from xml_processor import has_object_structure

        rename_active = not no_rename

        if has_object_structure(input_dir) and rename_active:
            print(
                "[INFO] Detected ICCD Folder+XML structure - using XML-based processing"
            )
            return process_iccd_objects(
                input_dir,
                output_dir,
                side,
                output_format,
                apply_rotation,
                smart_crop,
                debug,
                verbose,
                contour_border,
                fold_border,
                save_thumbs,
                process_jpg,
                process_tiff,
                export_json_mapping,
                json_only,
            )
        elif no_rename:
            print("[INFO] Standard batch processing mode (--no-rename flag enabled)")
        else:
            print("[INFO] Standard batch processing mode (no Folder+XML pairs found)")
    except ImportError as e:
        print(f"[WARNING] XML processor not available: {e}, using standard processing")
    except Exception as e:
        print(
            f"[WARNING] Error checking Folder+XML structure: {e}, using standard processing"
        )

    # Avvia il file listener se richiesto
    file_listener = None
    if enable_file_listener:
        if rename_map is None:
            rename_map = create_default_rename_map()

        print(f"Avvio file listener con mappa: {rename_map}")
        file_listener = start_file_listener_thread(output_dir, rename_map, verbose)

    start_time = time.time()
    start_datetime = datetime.now().isoformat()

    # Assicurati che la directory di output esista
    os.makedirs(output_dir, exist_ok=True)

    # Initialize dataset writer if requested
    dataset_writer = None
    if generate_dataset:
        from src.dataset.dataset_writer import DatasetWriter
        dataset_writer = DatasetWriter(output_dir)
        print("[DATASET] AI training dataset generation ENABLED")

    # Determina le estensioni da cercare
    if image_input_format:
        image_input_format = image_input_format.lower()
        if image_input_format in ["tif", "tiff"]:
            format_extensions = [".tif", ".tiff"]
        elif image_input_format in ["jpg", "jpeg"]:
            format_extensions = [".jpg", ".jpeg"]
        else:
            raise ValueError(
                "Formato immagine non supportato. Usa 'tif', 'tiff', 'jpg', o 'jpeg'."
            )
    else:
        format_extensions = [".tif", ".tiff", ".jpg", ".jpeg"]

    # Copia la struttura completa delle directory e i file non-immagine
    print(f"[INFO] Copying directory structure and non-image files...")
    files_copied = copy_directory_structure(input_dir, output_dir, format_extensions)
    print(f"[INFO] Copied {files_copied} non-image files")

    # Trova tutte le immagini
    image_files = find_images_recursive(input_dir, format_extensions)
    # Sort files to ensure consecutive processing for front-back couples
    image_files.sort()

    # Load crop mapping if available
    crop_mapping = load_crop_mapping(input_dir)
    error_data = {"Ricontrollare": []}

    total_files = len(image_files)

    if total_files == 0:
        print("Nessuna immagine trovata nella directory di input.")
        return

    # Calcola dimensione totale
    total_size_gb = sum(get_file_size_gb(f) for f in image_files)

    # Determina il formato primario
    formats = {}
    for f in image_files:
        ext = os.path.splitext(f)[1].lower()
        formats[ext] = formats.get(ext, 0) + 1
    primary_format = max(formats.keys(), key=formats.get) if formats else "unknown"

    # Crea il file info.json iniziale
    info_data = {
        "total_images": total_files,
        "processed": 0,
        "primary_format": primary_format.upper().replace(".", ""),
        "all_formats": formats,
        "total_size_gb": round(total_size_gb, 3),
        "start_time": start_datetime,
        "duration_seconds": None,
        "status": "processing",
        "cropped": {},  # Track original -> cropped file mappings
        "parameters": {
            "side": side,
            "output_format": output_format,
            "apply_rotation": apply_rotation,
            "smart_crop": smart_crop,
            "debug": debug,
            "file_listener_enabled": enable_file_listener,
            "rename_map": rename_map if enable_file_listener else None,
        },
    }

    write_info_json(output_dir, info_data)

    # Processa le immagini
    processed_count = 0
    error_count = 0
    renamed_count = 0

    if front_back_couple:
        # Process images in front-back couples
        print(
            f"[INFO] Front-back couple mode enabled - processing {total_files} images in pairs"
        )
        processed_count, error_count, renamed_count = process_front_back_couples(
            image_files,
            output_dir,
            input_dir,
            info_data,
            error_data,
            crop_mapping,
            side,
            output_format,
            apply_rotation,
            smart_crop,
            debug,
            verbose,
            contour_border,
            fold_border,
            save_thumbs,
            dataset_writer=dataset_writer,
        )

        # Update info.json with final counts
        info_data["processed"] = processed_count + error_count
        write_info_json(output_dir, info_data)

    else:
        # Standard individual processing
        for i, input_path in enumerate(image_files):
            if verbose:
                rel_path = os.path.relpath(input_path, input_dir)
                print(f"[{i + 1}/{total_files}] Processing: {rel_path}")

            # Get crop mapping entry for this image if available
            crop_mapping_entry = None
            if crop_mapping:
                # Find matching key in crop_mapping
                rel_path = os.path.relpath(input_path, input_dir)
                filename = os.path.basename(input_path)
                for mapping_key, mapping_value in crop_mapping.items():
                    if filename in mapping_key or rel_path in mapping_key:
                        crop_mapping_entry = mapping_value
                        break

            success, message, debug_info, error_reason = process_single_image(
                input_path,
                output_dir,
                input_dir,
                side,
                output_format,
                apply_rotation,
                smart_crop,
                debug,
                verbose,
                contour_border,
                fold_border,
                save_thumbs,
                crop_mapping_entry=crop_mapping_entry,
                dataset_writer=dataset_writer,
            )

            if success:
                processed_count += 1

                # Track error if present
                if error_reason:
                    error_data["Ricontrollare"].append({
                        "fname": os.path.basename(input_path),
                        "fpath": input_path,
                        "reason": error_reason
                    })

                # Track cropped files in info.json
                saved_files = debug_info.get("saved_files", [])
                if saved_files:
                    update_cropped_files_mapping(
                        info_data, input_path, saved_files, output_dir,
                        debug_info=debug_info,
                        page_contour=debug_info.get("page_contour"),
                        transform_M=debug_info.get("transform_M"),
                        was_processed=debug_info.get("was_processed", False)
                    )

                if verbose:
                    rotation_status = (
                        "con rotazione"
                        if debug_info.get("rotation_applied")
                        else "senza rotazione"
                    )
                    crop_status = (
                        "smart crop"
                        if debug_info.get("smart_crop_applied")
                        else "crop standard"
                    )
                    if debug_info.get("x_fold"):
                        print(
                            f"  x: {debug_info['x_fold']}, angolo: {debug_info['angle']:.2f} gradi, {rotation_status}, {crop_status}"
                        )
                    print(f"  {message}")
            else:
                error_count += 1
                print(f"  ERRORE: {message}")

                # Copy original file to output when processing fails
                try:
                    copied_path = copy_unprocessed_image(input_path, output_dir, input_dir)
                    print(f"  [INFO] Copied original to: {copied_path}")
                except Exception as e:
                    print(f"  [WARNING] Could not copy original: {e}")

                # Track error
                error_data["Ricontrollare"].append({
                    "fname": os.path.basename(input_path),
                    "fpath": input_path,
                    "reason": error_reason if error_reason else message
                })

            # Aggiorna info.json
            info_data["processed"] = i + 1
            write_info_json(output_dir, info_data)

    # Completa info.json
    end_time = time.time()
    duration_seconds = round(end_time - start_time, 2)

    info_data["duration_seconds"] = duration_seconds
    info_data["status"] = "completed"
    info_data["end_time"] = datetime.now().isoformat()
    summary = {
        "processed_successfully": processed_count,
        "errors": error_count,
        "success_rate": round(processed_count / total_files * 100, 1)
        if total_files > 0
        else 0,
    }

    if front_back_couple:
        summary["renamed_files"] = renamed_count
        summary["processing_mode"] = "front_back_couple"

    info_data["summary"] = summary
    write_info_json(output_dir, info_data)

    # Save error.json if there are files to review
    save_error_json(output_dir, error_data)

    print("\nElaborazione completata!")
    if front_back_couple:
        print(
            f"Coppie processate con successo: {processed_count // 2 if processed_count > 0 else 0}/{total_files // 2}"
        )
        print(f"Immagini processate: {processed_count}/{total_files}")
        print(f"File rinominati: {renamed_count}")
    else:
        print(f"Processate con successo: {processed_count}/{total_files}")
    print(f"Errori: {error_count}")
    print(f"Tempo totale: {duration_seconds} secondi")

    # Finalize dataset generation if enabled
    if dataset_writer:
        dataset_writer.finalize()

    # Ferma il file listener se era attivo
    if file_listener:
        print("Fermando il file listener...")
        file_listener.stop_monitoring()


def process_iccd_objects(
    input_dir,
    output_dir,
    side=None,
    output_format=None,
    apply_rotation=False,
    smart_crop=False,
    debug=False,
    verbose=True,
    contour_border=150,
    fold_border=None,
    save_thumbs=False,
    process_jpg=True,
    process_tiff=True,
    export_json_mapping=None,
    json_only=False,
):
    """
    Processa tutte le Buste ICCD nell'input directory con XML mapping e renaming

    Args:
        input_dir (str): Directory contenente Busta_XX folders e XML files
        output_dir (str): Directory di output per file ICCD rinominati
        Altri args: come nel main standard
    """
    import tempfile

    from iccd_renamer import CropResult, ICCDRenamer
    from xml_processor import XMLProcessor

    start_time = time.time()
    start_datetime = datetime.now().isoformat()

    print("\n[PHASE 1] XML Processing and Discovery")

    # Inizializza processors
    xml_processor = XMLProcessor()
    renamer = ICCDRenamer()

    # Processa tutti gli XML e estrai mappings
    print(f"[INFO] File processing settings: JPG={process_jpg}, TIFF={process_tiff}")
    mappings = xml_processor.process_all_objects(input_dir, process_jpg, process_tiff)

    if not mappings:
        print(
            "[ERROR] No valid ICCD mappings found. Check XML files and image folders."
        )
        return

    total_images = len(mappings)
    print(f"[INFO] Found {total_images} images to process across Bustas")

    # Export JSON mapping if requested
    if export_json_mapping:
        # Make JSON path relative to output directory if it's not absolute
        if not os.path.isabs(export_json_mapping):
            json_path = os.path.join(output_dir, export_json_mapping)
        else:
            json_path = export_json_mapping

        print(f"\n[JSON EXPORT] Saving complete mapping to: {json_path}")
        success = xml_processor.save_mappings_to_json(
            mappings, json_path, include_iccd_names=True
        )
        if success:
            print("[JSON EXPORT] Complete mapping saved successfully")
        else:
            print("[JSON EXPORT] Failed to save mapping")

        # If json_only mode, exit after JSON export
        if json_only:
            print("[JSON ONLY] JSON export complete, skipping image processing")
            return success

    # Phase 2: Crea struttura directory output ICCD
    print("\n[PHASE 2] Creating ICCD Output Directory Structure")
    fascicolo_dirs = renamer.create_iccd_directory_structure(output_dir, mappings)

    # Phase 3: Process images con XML mapping
    print("\n[PHASE 3] Processing Images with ICCD Renaming")

    processed_count = 0
    renamed_count = 0
    error_count = 0

    # Create temp directory for intermediate processing
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, mapping in enumerate(mappings):
            if verbose:
                print(
                    f"[{i + 1}/{total_images}] Processing: {mapping.original_filename}"
                )

            try:
                # Path originale immagine - usa full_path se disponibile
                if hasattr(mapping, "full_path") and mapping.full_path:
                    original_image = mapping.full_path
                else:
                    # Fallback per compatibilità
                    if hasattr(mapping, "subdir") and mapping.subdir:
                        original_image = os.path.join(
                            mapping.object_folder,
                            mapping.subdir,
                            mapping.original_filename,
                        )
                    else:
                        original_image = os.path.join(
                            mapping.object_folder, mapping.original_filename
                        )

                if not os.path.exists(original_image):
                    error_count += 1
                    print(f"[ERROR] Image not found: {original_image}")
                    continue

                # Process image usando la logica esistente
                temp_output = os.path.join(temp_dir, f"temp_{i}")
                os.makedirs(temp_output, exist_ok=True)

                success, message, debug_info = process_single_image(
                    original_image,
                    temp_output,
                    mapping.object_folder,
                    side=side,
                    output_format=None,  # Preserve original format
                    apply_rotation=apply_rotation,
                    smart_crop=smart_crop,
                    debug=debug,
                    verbose=False,  # Suppress verbose for cleaner output
                    contour_border=contour_border,
                    fold_border=fold_border,
                    save_thumbs=False,  # No thumbs in temp
                    dataset_writer=dataset_writer,
                )

                if not success:
                    error_count += 1
                    print(f"[ERROR] Processing failed: {message}")
                    continue

                processed_count += 1

                # Analizza risultato crop per determinare files generati
                saved_files = debug_info.get("saved_files", [])
                fold_detected = debug_info.get("x_fold") is not None

                if fold_detected and len(saved_files) == 2:
                    # Fold rilevato - files left/right
                    left_file = next((f for f in saved_files if "_left" in f), None)
                    right_file = next((f for f in saved_files if "_right" in f), None)

                    crop_result = CropResult(
                        fold_detected=True,
                        left_file=left_file,
                        right_file=right_file,
                        original_filename=mapping.original_filename,
                        original_file_path=original_image,
                    )
                else:
                    # No fold - file singolo
                    single_file = saved_files[0] if saved_files else None

                    crop_result = CropResult(
                        fold_detected=False,
                        single_file=single_file,
                        original_filename=mapping.original_filename,
                        original_file_path=original_image,
                    )

                # Applica renaming ICCD
                base_target_dir = renamer.get_target_directory(mapping, fascicolo_dirs)

                if base_target_dir:
                    # Create subdirectory in output if source has subdirectory
                    final_target_dir = base_target_dir
                    if hasattr(mapping, "subdir") and mapping.subdir:
                        final_target_dir = os.path.join(base_target_dir, mapping.subdir)
                        os.makedirs(final_target_dir, exist_ok=True)
                        if verbose:
                            print(f"  [INFO] Created subdirectory: {mapping.subdir}")

                    renamings = renamer.handle_page_splitting(mapping, crop_result)

                    for source_file, target_filename, original_file_path in renamings:
                        success = renamer.apply_naming_convention(
                            source_file,
                            target_filename,
                            final_target_dir,
                            original_file_path,
                        )

                        if success:
                            renamed_count += 1

                # Status update
                if verbose:
                    fold_status = "fold detected" if fold_detected else "no fold"
                    print(
                        f"  [OK] {fold_status}, {len(renamings) if 'renamings' in locals() else 0} files renamed"
                    )

            except Exception as e:
                error_count += 1
                print(f"[ERROR] Error processing {mapping.original_filename}: {e}")

    # Phase 4: Final reporting
    print("\n[PHASE 4] Final Report")

    end_time = time.time()
    duration_seconds = round(end_time - start_time, 2)

    print("=" * 60)
    print("[SUMMARY] ICCD PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total images found: {total_images}")
    print(f"Successfully processed: {processed_count}")
    print(f"Successfully renamed: {renamed_count}")
    print(f"Errors: {error_count}")

    if total_images > 0:
        success_rate = (processed_count / total_images) * 100
        rename_rate = (renamed_count / total_images) * 100
        print(f"Processing success rate: {success_rate:.1f}%")
        print(f"Renaming success rate: {rename_rate:.1f}%")

    print(f"Total processing time: {duration_seconds} seconds")

    # Generate reports
    try:
        import json

        report_file = os.path.join(output_dir, "iccd_processing_report.json")
        renamer.generate_processing_report(
            report_file.replace(".json", "_renaming.json")
        )

        # General report
        general_report = {
            "timestamp": datetime.now().isoformat(),
            "total_images": total_images,
            "processed": processed_count,
            "renamed": renamed_count,
            "errors": error_count,
            "duration_seconds": duration_seconds,
            "success_rates": {
                "processing": round(success_rate, 1) if total_images > 0 else 0,
                "renaming": round(rename_rate, 1) if total_images > 0 else 0,
            },
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(general_report, f, indent=2, ensure_ascii=False)

        print(f"Reports saved to: {output_dir}")

    except Exception as e:
        print(f"[WARNING] Could not generate reports: {e}")

    print("=" * 60)

    if error_count == 0:
        print("[SUCCESS] ICCD processing completed successfully!")
    else:
        print(f"[WARNING] ICCD processing completed with {error_count} errors")

    return error_count == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ritaglia un doppio foglio A4 sulla piega e aggiorna l'ordine delle pagine generate dal ritaglio"
    )
    parser.add_argument("input_dir", type=str, help="Input directory")
    parser.add_argument("output_dir", type=str, help="Output directory")
    parser.add_argument(
        "--side",
        choices=["left", "right", "center"],
        default=None,
        help="Lato della piega (default: auto-detect)",
    )
    parser.add_argument(
        "--output_format",
        choices=["jpg", "png", "tiff"],
        default=None,
        help="Formato di output (default: mantieni originale)",
    )
    parser.add_argument(
        "--image_input_format",
        choices=["tif", "tiff", "jpg", "jpeg"],
        default=None,
        help="Formato delle immagini di input da cercare (default: tutti)",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help="Applica rotazione per raddrizzare la piega",
    )
    parser.add_argument(
        "--smart_crop",
        action="store_true",
        default=False,
        help="Usa rilevamento intelligente del bordo documento",
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Genera file di debug"
    )
    parser.add_argument(
        "--verbose", action="store_true", default=True, help="Output verbose"
    )
    parser.add_argument(
        "--enable_file_listener",
        action="store_true",
        default=False,
        help="Abilita il file listener per rinominazioni automatiche",
    )
    parser.add_argument(
        "--rename_map_file",
        type=str,
        default=None,
        help="File JSON contenente la mappa di rinominazione",
    )
    parser.add_argument(
        "--contour_border",
        type=int,
        default=150,
        help="Border pixels per correzione prospettiva contour detection (default: 150)",
    )
    parser.add_argument(
        "--fold_border",
        type=int,
        default=None,
        help="Border pixels attorno alla piega per contenuto sovrapposto (default: same as contour_border)",
    )
    parser.add_argument(
        "--save_thumbs",
        action="store_true",
        default=False,
        help="Genera thumbnails di confronto prima/dopo per ogni lato",
    )
    parser.add_argument(
        "--process_jpg",
        action="store_true",
        default=True,
        help="Processa file .jpg/.jpeg (default: True)",
    )
    parser.add_argument(
        "--no_process_jpg",
        dest="process_jpg",
        action="store_false",
        help="Non processare file .jpg/.jpeg",
    )
    parser.add_argument(
        "--process_tiff",
        action="store_true",
        default=True,
        help="Processa file .tiff/.tif (default: True)",
    )
    parser.add_argument(
        "--no_process_tiff",
        dest="process_tiff",
        action="store_false",
        help="Non processare file .tiff/.tif",
    )
    parser.add_argument(
        "--export_json_mapping",
        type=str,
        default=None,
        help="Esporta mappings XML->ICCD come file JSON per debug (fornisci path)",
    )
    parser.add_argument(
        "--json_only",
        action="store_true",
        default=False,
        help="Esporta solo JSON mapping senza processare immagini",
    )
    parser.add_argument(
        "--no-rename",
        action="store_true",
        default=True,
        help="Force standard processing without ICCD renaming, even if XML structure detected",
    )
    parser.add_argument(
        "--front-back-couple",
        action="store_true",
        default=False,
        help="Process images in consecutive pairs as front-back couples with 4-page renaming pattern",
    )
    parser.add_argument(
        "--generate-dataset",
        action="store_true",
        default=False,
        help="Generate AI training dataset with 512x512 images, labels, and debug visualizations in _AI_training/ folder",
    )

    args = parser.parse_args()

    # If fold_border not specified, use same value as contour_border
    if args.fold_border is None:
        args.fold_border = args.contour_border

    # Carica la mappa di rinominazione se specificata
    rename_map = None
    if args.enable_file_listener:
        if args.rename_map_file and os.path.exists(args.rename_map_file):
            import json

            with open(args.rename_map_file, "r", encoding="utf-8") as f:
                rename_map = json.load(f)
            print(f"Caricata mappa di rinominazione da: {args.rename_map_file}")
        else:
            rename_map = create_default_rename_map()
            print("Uso mappa di rinominazione di default")

    main(
        args.input_dir,
        args.output_dir,
        side=args.side,
        output_format=args.output_format,
        image_input_format=args.image_input_format,
        apply_rotation=args.rotate,
        smart_crop=args.smart_crop,
        debug=args.debug,
        verbose=args.verbose,
        enable_file_listener=args.enable_file_listener,
        rename_map=rename_map,
        contour_border=args.contour_border,
        fold_border=args.fold_border,
        save_thumbs=args.save_thumbs,
        process_jpg=args.process_jpg,
        process_tiff=args.process_tiff,
        export_json_mapping=args.export_json_mapping,
        json_only=args.json_only,
        no_rename=args.no_rename,
        front_back_couple=args.front_back_couple,
        generate_dataset=args.generate_dataset,
    )
