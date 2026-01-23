"""
dataset package

AI Training Dataset Generation Module
======================================

This package provides utilities to generate training datasets for neural networks
from the existing computer vision detection pipeline.

The CV pipeline detects:
- Page contours (4 corners)
- Fold lines in double-page scans

This module captures these detections and creates:
- 512x512 letterbox-resized images from original scans
- JSON labels with transformed coordinates
- Debug visualizations showing detections

Modules:
--------
- resize_utils: Letterbox resize to 512x512 with black padding
- coordinate_transform: Transform coordinates between image spaces
- label_generator: Create JSON label files
- debug_visualizer: Generate debug images with overlays
- dataset_writer: Main orchestrator for dataset generation

Usage:
------
    from src.dataset.dataset_writer import DatasetWriter

    writer = DatasetWriter(output_dir="/path/to/output")
    writer.add_sample(
        original_img=img,
        filename="IMG_001.jpg",
        page_corners_original=corners,
        rectified_img=rect_img,
        transformation_matrix=M,
        fold_x=256,
        fold_detected=True
    )
    writer.finalize()
"""

__version__ = "1.0.0"
__author__ = "Scripta Image Processing"
