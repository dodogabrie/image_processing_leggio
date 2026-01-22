import json
import os
import time

import cv2
import numpy as np
from PIL import Image

from .quality_evaluation import evaluate_quality

DEFAULT_ERROR = {
    "sharpness": 0.1,
    "entropy": 0.1,
    "edge_density": 0.1,
    "residual_skew_angle": 0.1,
}


def show_image(image, title="Image", max_width=1280, max_height=720, file_path=None):
    """
    Resize and display an image with a title. Waits for a key press to close.

    Args:
        image (numpy.ndarray): Image to display.
        title (str): Window title for the displayed image.
        max_width (int): Maximum width for resizing.
        max_height (int): Maximum height for resizing.
        file_path (str): Path to save the image.

    Returns:
        None
    """
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1)
    resized_image = cv2.resize(image, (int(width * scale), int(height * scale)))

    if not file_path:
        cv2.imshow(title, resized_image)
        cv2.waitKey(0)

    # this is for educational purposes
    if file_path:
        cv2.imwrite(file_path, resized_image)


def load_image(image_path):
    """Load the input image from the given path."""
    return cv2.imread(image_path, cv2.IMREAD_UNCHANGED)


def save_image_with_metadata(
    image_array, output_path, original_path, use_compression=True
):
    """
    Salva un'immagine preservando i metadati EXIF senza perdita di qualità.

    Args:
        image_array (np.ndarray): Array dell'immagine da salvare (BGR format)
        output_path (str): Path dove salvare l'immagine
        original_path (str): Path dell'immagine originale (per i metadati)
        use_compression (bool): Se True, usa compressione LZW per TIFF (default: True)

    Returns:
        dict: Metadata information including original and saved metadata
    """
    metadata_info = {
        "original_metadata": {},
        "saved_successfully": False,
        "metadata_preserved": False,
        "format": None,
        "compression": None,
        "compression_requested": use_compression,
        "error": None,
    }

    try:
        # Convert BGR to RGB for PIL
        if len(image_array.shape) == 3:
            image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image_array

        pil_image = Image.fromarray(image_rgb)
        output_ext = os.path.splitext(output_path)[1].lower()
        metadata_info["format"] = output_ext.upper().replace(".", "")

        # Load metadata from original
        with Image.open(original_path) as original:
            # Extract readable metadata
            readable_metadata = {}
            for key, value in original.info.items():
                try:
                    readable_metadata[str(key)] = str(value)
                except:
                    readable_metadata[str(key)] = "non-serializable"

            # Add EXIF if available
            if hasattr(original, "_getexif") and original._getexif():
                exif_dict = original._getexif()
                for tag_id, value in exif_dict.items():
                    try:
                        readable_metadata[f"EXIF_{tag_id}"] = str(value)
                    except:
                        readable_metadata[f"EXIF_{tag_id}"] = "non-serializable"

            metadata_info["original_metadata"] = readable_metadata

            if output_ext in [".tiff", ".tif"]:
                # TIFF handling
                compression_type = "tiff_lzw" if use_compression else "raw"
                save_kwargs = {"format": "TIFF", "compression": compression_type}

                # Add metadata (excluding ICC profile if using compression to avoid conflicts)
                if "dpi" in original.info:
                    save_kwargs["dpi"] = original.info["dpi"]
                if "exif" in original.info:
                    save_kwargs["exif"] = original.info["exif"]
                if not use_compression and "icc_profile" in original.info:
                    save_kwargs["icc_profile"] = original.info["icc_profile"]

                pil_image.save(output_path, **save_kwargs)
                metadata_info["compression"] = "lzw" if use_compression else "raw"
                metadata_info["metadata_preserved"] = True
                if use_compression:
                    metadata_info["notes"] = (
                        "LZW compression applied, ICC profile excluded to avoid conflicts"
                    )

            elif output_ext in [".png"]:
                # PNG handling
                from PIL import PngImagePlugin

                pnginfo = PngImagePlugin.PngInfo()
                for key, value in original.info.items():
                    if isinstance(key, str) and isinstance(value, str):
                        pnginfo.add_text(key, value)

                pil_image.save(output_path, format="PNG", pnginfo=pnginfo)
                metadata_info["compression"] = "lossless"
                metadata_info["metadata_preserved"] = bool(pnginfo)

            elif output_ext in [".jpg", ".jpeg"]:
                # JPEG handling
                save_kwargs = {
                    "format": "JPEG",
                    "quality": 100,
                    "optimize": False,
                    "subsampling": 0,
                }
                if "exif" in original.info:
                    save_kwargs["exif"] = original.info["exif"]
                if "dpi" in original.info:
                    save_kwargs["dpi"] = original.info["dpi"]

                pil_image.save(output_path, **save_kwargs)
                metadata_info["compression"] = "quality_100"
                metadata_info["metadata_preserved"] = "exif" in original.info

            else:
                # Default handling
                save_kwargs = {}
                if "exif" in original.info:
                    save_kwargs["exif"] = original.info["exif"]
                pil_image.save(output_path, **save_kwargs)
                metadata_info["metadata_preserved"] = "exif" in original.info

            metadata_info["saved_successfully"] = True

    except Exception as e:
        metadata_info["error"] = str(e)
        print(f"Error in save_image_with_metadata: {e}")
        # Fallback to OpenCV
        try:
            if output_path.lower().endswith((".jpg", ".jpeg")):
                cv2.imwrite(output_path, image_array, [cv2.IMWRITE_JPEG_QUALITY, 100])
                metadata_info["compression"] = "opencv_quality_100"
            elif output_path.lower().endswith(".png"):
                cv2.imwrite(output_path, image_array, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                metadata_info["compression"] = "opencv_lossless"
            else:
                cv2.imwrite(output_path, image_array)
                metadata_info["compression"] = "opencv_raw"
            metadata_info["saved_successfully"] = True
        except Exception as e2:
            metadata_info["error"] = f"PIL and OpenCV both failed: {e}, {e2}"

    return metadata_info


def compare_metadata(original_path, output_path):
    """Compare metadata between original and output images."""
    comparison = {
        "metadata_preserved": False,
        "original_metadata": {},
        "output_metadata": {},
        "missing_fields": [],
        "added_fields": [],
        "changed_fields": [],
    }

    try:
        # Read metadata from both files
        with Image.open(original_path) as original_img:
            original_metadata = original_img.info.copy()
            original_metadata["mode"] = original_img.mode
            original_metadata["size"] = str(original_img.size)

        with Image.open(output_path) as output_img:
            output_metadata = output_img.info.copy()
            output_metadata["mode"] = output_img.mode
            output_metadata["size"] = str(output_img.size)

        # Convert to strings for JSON serialization
        original_str = {str(k): str(v) for k, v in original_metadata.items()}
        output_str = {str(k): str(v) for k, v in output_metadata.items()}

        comparison["original_metadata"] = original_str
        comparison["output_metadata"] = output_str

        # Find differences
        original_keys = set(original_str.keys())
        output_keys = set(output_str.keys())

        comparison["missing_fields"] = list(original_keys - output_keys)
        comparison["added_fields"] = list(output_keys - original_keys)

        # Check for changed values
        for key in original_keys.intersection(output_keys):
            if original_str[key] != output_str[key]:
                comparison["changed_fields"].append(
                    {
                        "field": key,
                        "original": original_str[key],
                        "output": output_str[key],
                    }
                )

        # Determine if critical metadata is preserved
        critical_fields = ["icc_profile", "dpi"]
        preserved = True

        for field in critical_fields:
            if field in comparison["missing_fields"]:
                preserved = False
                break

        # Allow minor DPI differences
        for change in comparison["changed_fields"]:
            if change["field"] == "dpi":
                try:
                    orig_dpi = eval(change["original"])
                    out_dpi = eval(change["output"])
                    if isinstance(orig_dpi, tuple) and isinstance(out_dpi, tuple):
                        if (
                            abs(orig_dpi[0] - out_dpi[0]) > 50
                            or abs(orig_dpi[1] - out_dpi[1]) > 50
                        ):
                            preserved = False
                            break
                except:
                    preserved = False
                    break

        comparison["metadata_preserved"] = preserved

    except Exception as e:
        comparison["error"] = str(e)

    return comparison


def save_outputs(
    original,
    processed,
    output_path_tiff,
    output_path_thumb=None,
    copied=False,
    output_no_cropped=None,
    original_path=None,
    use_compression=True,
):
    """
    Save the processed TIFF image, a reduced JPG thumbnail, and the quality evaluation JSON.
    Always saves both original and processed images in the thumbnail, and always saves the quality file.
    Now also preserves metadata from original images.
    """
    if copied:
        processed = np.zeros_like(original)  # If copied, processed is an empty image

    # Save the processed TIFF with metadata preservation
    metadata_info = None
    if original_path:
        metadata_info = save_image_with_metadata(
            processed, output_path_tiff, original_path, use_compression
        )
    else:
        # Fallback: salvataggio con compressione opzionale
        if output_path_tiff.lower().endswith((".tiff", ".tif")):
            if use_compression:
                # Convert to PIL and save with LZW compression
                if len(processed.shape) == 3:
                    processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                else:
                    processed_rgb = processed
                pil_image = Image.fromarray(processed_rgb)
                print("Fallback: Saving TIFF with LZW compression")
                pil_image.save(output_path_tiff, format="TIFF", compression="lzw")
            else:
                print("Fallback: Saving TIFF without compression")
                cv2.imwrite(output_path_tiff, processed)
        elif output_path_tiff.lower().endswith(".png"):
            cv2.imwrite(output_path_tiff, processed, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        elif output_path_tiff.lower().endswith((".jpg", ".jpeg")):
            cv2.imwrite(output_path_tiff, processed, [cv2.IMWRITE_JPEG_QUALITY, 100])
        else:
            cv2.imwrite(output_path_tiff, processed)

    # Ensure both images have the same height
    if original.shape[0] != processed.shape[0]:
        height = min(original.shape[0], processed.shape[0])
        original = cv2.resize(
            original, (int(original.shape[1] * height / original.shape[0]), height)
        )
        processed = cv2.resize(
            processed, (int(processed.shape[1] * height / processed.shape[0]), height)
        )

    # Ensure both images have the same type
    if original.shape[2] != processed.shape[2]:
        if len(original.shape) == 2:
            original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
        if len(processed.shape) == 2:
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

    # --- SEPARAZIONE VISIVA ---
    sep_width = 100  # larghezza separatore
    height = original.shape[0]
    separator = 0 * np.ones((height, sep_width, 3), dtype=np.uint8)  # grigio chiaro

    # Concatenate original, separator, processed
    concatenated_image = cv2.hconcat([original, separator, processed])

    resize_val = 800
    height, width = concatenated_image.shape[:2]
    thumbnail = cv2.resize(
        concatenated_image, (resize_val, int(resize_val * height / width))
    )

    # Se non viene passato output_path_thumb, salva in una cartella tmp accanto all'output tiff
    if not output_path_thumb:
        output_dir = os.path.dirname(output_path_tiff)
        output_path_thumb = os.path.join(output_dir, "tmp")
        os.makedirs(output_path_thumb, exist_ok=True)

    # Extract the base filename and add timestamp for proper sorting
    base_filename = os.path.basename(output_path_tiff)
    name_without_ext = os.path.splitext(base_filename)[0]
    timestamp = str(int(time.time() * 1000))  # milliseconds timestamp
    thumbnail_filename = f"{timestamp}_{name_without_ext}.jpg"

    # Salva thumbnail con gestione errori migliorata
    thumbnail_full_path = os.path.join(output_path_thumb, thumbnail_filename)
    try:
        success = cv2.imwrite(
            thumbnail_full_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if not success:
            # Fallback con PIL
            thumbnail_rgb = cv2.cvtColor(thumbnail, cv2.COLOR_BGR2RGB)
            pil_thumbnail = Image.fromarray(thumbnail_rgb)
            pil_thumbnail.save(thumbnail_full_path, format="JPEG", quality=85)
    except Exception as e:
        print(f"Warning: Failed to save thumbnail: {e}")

    # --- Calcola e salva la valutazione della qualità ---
    if output_no_cropped is not None:
        image_to_compare = output_no_cropped
    else:
        # If no uncropped original is provided, use the processed image
        image_to_compare = original

    quality = evaluate_quality(image_to_compare, processed)

    # Add metadata information if available
    if metadata_info:
        quality["save_metadata_info"] = metadata_info
        # Also add compression info to the main quality object for easier access
        quality["compression_used"] = metadata_info.get("compression", "unknown")
        quality["compression_requested"] = use_compression

    # Add metadata comparison if original_path is provided
    if original_path and os.path.exists(output_path_tiff):
        metadata_comparison = compare_metadata(original_path, output_path_tiff)
        quality["metadata_comparison"] = metadata_comparison

    quality_dir = os.path.join(os.path.dirname(output_path_thumb), "quality")
    quality_dir = os.path.abspath(quality_dir)
    os.makedirs(quality_dir, exist_ok=True)
    quality_filename = os.path.splitext(thumbnail_filename)[0] + ".json"
    quality_path = os.path.join(quality_dir, quality_filename)

    def to_python_type(obj):
        if isinstance(obj, dict):
            return {k: to_python_type(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [to_python_type(x) for x in obj]
        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        else:
            return obj

    quality_py = to_python_type(quality)
    with open(quality_path, "w", encoding="utf-8") as f:
        json.dump(quality_py, f, indent=2, ensure_ascii=False)

    return thumbnail


def is_image_valid(image_path):
    """
    Controlla se un file immagine esiste e non è corrotto.
    Supporta TIFF, PNG, JPEG, ecc.

    Args:
        image_path (str): Percorso dell'immagine da controllare.

    Returns:
        bool: True se l'immagine esiste e non è corrotta, False altrimenti.
    """
    if not os.path.exists(image_path):
        return False
    try:
        with Image.open(image_path) as img:
            img.verify()  # Verifica integrità senza caricare tutto in memoria
        return True
    except Exception:
        return False
