"""
label_generator.py

JSON Label File Generation
===========================

Creates structured JSON label files for AI training datasets.
Labels contain page corner coordinates, fold line parameters, and
resize metadata in the format expected by neural network training pipelines.
"""

import json
import os
from datetime import datetime
import numpy as np


def create_label_dict(
    filename,
    filepath,
    page_present,
    page_corners_512,
    fold_present,
    fold_p1_512,
    fold_p2_512,
    original_width,
    original_height,
    scale,
    offset_x,
    offset_y,
    target_size=512
):
    """
    Generate label dictionary in the required JSON format.

    Args:
        filename (str): Image filename (e.g., "IMG_00123.jpg")
        filepath (str): Relative path to image in dataset (e.g., "_AI_training/dataset/IMG_00123.jpg")
        page_present (bool): True if page contour was detected
        page_corners_512 (list): List of 4 [x, y] corners in 512x512 space, or None
        fold_present (bool): True if fold line was detected
        fold_p1_512 (list): [x, y] for fold point 1 in 512x512 space, or None
        fold_p2_512 (list): [x, y] for fold point 2 in 512x512 space, or None
        original_width (int): Original image width in pixels
        original_height (int): Original image height in pixels
        scale (float): Scaling factor applied during resize
        offset_x (int): Horizontal offset from letterbox padding
        offset_y (int): Vertical offset from letterbox padding
        target_size (int): Target size for dataset images (default: 512)

    Returns:
        dict: Label dictionary ready for JSON serialization

    Example output:
        {
            "filename": "IMG_00123.jpg",
            "filepath": "_AI_training/dataset/IMG_00123.jpg",
            "page_present": true,
            "page_corners": [[45, 32], [478, 28], [482, 488], [41, 492]],
            "fold_present": true,
            "fold_line": {
                "point1": [256, 35],
                "point2": [262, 485]
            },
            "resize_params": {
                "target_size": [512, 512],
                "scale": 0.128,
                "offset_x": 0,
                "offset_y": 64,
                "original_size": [4000, 3000]
            }
        }
    """
    label = {
        "filename": filename,
        "filepath": filepath,
        "page_present": page_present,
        "page_corners": page_corners_512 if page_present else None,
        "fold_present": fold_present,
        "fold_line": None,
        "resize_params": {
            "target_size": [target_size, target_size],
            "scale": round(scale, 6),  # Round to avoid floating point noise
            "offset_x": offset_x,
            "offset_y": offset_y,
            "original_size": [original_width, original_height]
        }
    }

    # Add fold line if present
    if fold_present and fold_p1_512 is not None and fold_p2_512 is not None:
        label["fold_line"] = {
            "point1": fold_p1_512,
            "point2": fold_p2_512
        }

    return label


class NumpyEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles NumPy data types.
    Converts numpy arrays and scalars to Python native types.
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def save_label_json(label_dict, output_path):
    """
    Save label dictionary to JSON file with proper formatting.

    Args:
        label_dict (dict): Label dictionary from create_label_dict()
        output_path (str): Full path to output JSON file

    Returns:
        bool: True if save successful, False otherwise

    Example:
        >>> label = create_label_dict(...)
        >>> save_label_json(label, "_AI_training/dataset/IMG_001.json")
        True
    """
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write JSON with nice formatting, using custom encoder for NumPy types
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(label_dict, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        return True

    except Exception as e:
        print(f"[ERROR] Failed to save label JSON to {output_path}: {e}")
        return False


def load_label_json(json_path):
    """
    Load and parse a label JSON file.

    Args:
        json_path (str): Path to JSON file

    Returns:
        dict: Parsed label dictionary, or None if failed
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            label = json.load(f)
        return label

    except Exception as e:
        print(f"[ERROR] Failed to load label JSON from {json_path}: {e}")
        return None


def validate_label_schema(label_dict):
    """
    Validate that label dictionary conforms to expected schema.

    Args:
        label_dict (dict): Label dictionary to validate

    Returns:
        bool: True if valid

    Raises:
        ValueError: If schema validation fails
    """
    required_keys = ["filename", "filepath", "page_present", "page_corners",
                     "fold_present", "fold_line", "resize_params"]

    # Check all required keys present
    for key in required_keys:
        if key not in label_dict:
            raise ValueError(f"Missing required key: {key}")

    # Validate page_corners if page present
    if label_dict["page_present"]:
        corners = label_dict["page_corners"]
        if corners is None or len(corners) != 4:
            raise ValueError("page_present=true but page_corners invalid")
        for i, corner in enumerate(corners):
            if not isinstance(corner, list) or len(corner) != 2:
                raise ValueError(f"Corner {i} is not a valid [x, y] pair")

    # Validate fold_line if fold present
    if label_dict["fold_present"]:
        fold = label_dict["fold_line"]
        if fold is None:
            raise ValueError("fold_present=true but fold_line is None")
        if "point1" not in fold or "point2" not in fold:
            raise ValueError("fold_line missing point1 or point2")
        if len(fold["point1"]) != 2 or len(fold["point2"]) != 2:
            raise ValueError("fold_line points must be [x, y] pairs")

    # Validate resize_params
    resize = label_dict["resize_params"]
    required_resize_keys = ["target_size", "scale", "offset_x", "offset_y", "original_size"]
    for key in required_resize_keys:
        if key not in resize:
            raise ValueError(f"resize_params missing key: {key}")

    return True


def create_metadata_summary(labels_list, dataset_dir):
    """
    Create a metadata summary file for the entire dataset.

    Args:
        labels_list (list): List of label dictionaries
        dataset_dir (str): Path to dataset directory

    Returns:
        dict: Metadata summary dictionary

    Example output:
        {
            "total_samples": 150,
            "samples_with_page": 148,
            "samples_with_fold": 142,
            "target_size": [512, 512],
            "generated_at": "2025-10-06T14:30:00",
            "samples": [
                {"filename": "IMG_00001.jpg", "page_present": true, "fold_present": true},
                ...
            ]
        }
    """
    total = len(labels_list)
    with_page = sum(1 for label in labels_list if label["page_present"])
    with_fold = sum(1 for label in labels_list if label["fold_present"])

    metadata = {
        "total_samples": total,
        "samples_with_page": with_page,
        "samples_with_fold": with_fold,
        "target_size": [512, 512],
        "generated_at": datetime.now().isoformat(),
        "dataset_directory": dataset_dir,
        "samples": [
            {
                "filename": label["filename"],
                "page_present": label["page_present"],
                "fold_present": label["fold_present"]
            }
            for label in labels_list
        ]
    }

    return metadata


def save_metadata_summary(metadata_dict, output_path):
    """
    Save metadata summary to JSON file.

    Args:
        metadata_dict (dict): Metadata dictionary from create_metadata_summary()
        output_path (str): Path to output JSON file (e.g., "_AI_training/metadata.json")

    Returns:
        bool: True if successful
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
        return True

    except Exception as e:
        print(f"[ERROR] Failed to save metadata summary to {output_path}: {e}")
        return False


# Test function for development
if __name__ == "__main__":
    print("Testing label generation...")

    # Test case 1: Full detection (page + fold)
    print("\n[Test 1] Full detection (page + fold)")
    label1 = create_label_dict(
        filename="IMG_00001.jpg",
        filepath="_AI_training/dataset/IMG_00001.jpg",
        page_present=True,
        page_corners_512=[[45, 32], [478, 28], [482, 488], [41, 492]],
        fold_present=True,
        fold_p1_512=[256, 35],
        fold_p2_512=[262, 485],
        original_width=4000,
        original_height=3000,
        scale=0.128,
        offset_x=0,
        offset_y=64
    )
    print(json.dumps(label1, indent=2))
    validate_label_schema(label1)
    print("Full detection label valid")

    # Test case 2: Page only (no fold)
    print("\n[Test 2] Page only (no fold)")
    label2 = create_label_dict(
        filename="IMG_00002.jpg",
        filepath="_AI_training/dataset/IMG_00002.jpg",
        page_present=True,
        page_corners_512=[[52, 38], [461, 35], [465, 479], [48, 482]],
        fold_present=False,
        fold_p1_512=None,
        fold_p2_512=None,
        original_width=3000,
        original_height=3000,
        scale=0.17,
        offset_x=32,
        offset_y=0
    )
    print(json.dumps(label2, indent=2))
    validate_label_schema(label2)
    print("Page-only label valid")

    # Test case 3: No detection
    print("\n[Test 3] No detection")
    label3 = create_label_dict(
        filename="IMG_00003.jpg",
        filepath="_AI_training/dataset/IMG_00003.jpg",
        page_present=False,
        page_corners_512=None,
        fold_present=False,
        fold_p1_512=None,
        fold_p2_512=None,
        original_width=2448,
        original_height=1836,
        scale=0.21,
        offset_x=0,
        offset_y=48
    )
    print(json.dumps(label3, indent=2))
    validate_label_schema(label3)
    print("No-detection label valid")

    # Test case 4: Metadata summary
    print("\n[Test 4] Metadata summary")
    metadata = create_metadata_summary(
        [label1, label2, label3],
        "_AI_training/dataset"
    )
    print(json.dumps(metadata, indent=2))
    print("Metadata summary valid")

    print("\nAll label generation tests passed!")
