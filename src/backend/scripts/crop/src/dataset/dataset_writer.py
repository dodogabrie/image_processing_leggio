"""
dataset_writer.py

Dataset Writer Orchestrator
============================

Main coordinator for AI training dataset generation. This class integrates
all dataset generation components (resize, transform, labels, visualization)
and provides a simple interface for the processing pipeline.

Usage:
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

import os
import cv2

from .resize_utils import resize_with_letterbox
from .coordinate_transform import (
    transform_page_corners,
    compute_fold_line_full_pipeline
)
from .label_generator import (
    create_label_dict,
    save_label_json,
    create_metadata_summary,
    save_metadata_summary
)
from .debug_visualizer import (
    draw_debug_visualization,
    save_debug_image
)


class DatasetWriter:
    """
    Main class for generating AI training dataset during image processing.

    Coordinates all dataset generation steps:
    1. Resize original images to 512x512 with letterbox
    2. Transform coordinates to dataset space
    3. Generate JSON labels
    4. Create debug visualizations
    5. Save everything to organized output structure

    Attributes:
        ai_training_dir (str): Root directory for AI training data
        dataset_dir (str): Directory for dataset images and labels
        debug_dir (str): Directory for debug visualizations
        samples_generated (list): List of generated sample metadata
    """

    def __init__(self, output_base_dir, dataset_subdir="dataset", debug_subdir="debug"):
        """
        Initialize dataset writer.

        Args:
            output_base_dir (str): Base output directory (e.g., "/path/to/output")
            dataset_subdir (str): Subfolder for dataset (default: "dataset")
            debug_subdir (str): Subfolder for debug images (default: "debug")

        Creates directory structure:
            {output_base_dir}/_AI_training/
            - dataset/
            - debug/
        """
        self.ai_training_dir = os.path.join(output_base_dir, "_AI_training")
        self.dataset_dir = os.path.join(self.ai_training_dir, dataset_subdir)
        self.debug_dir = os.path.join(self.ai_training_dir, debug_subdir)
        self.samples_generated = []

        # Create directories
        os.makedirs(self.dataset_dir, exist_ok=True)
        os.makedirs(self.debug_dir, exist_ok=True)

        print(f"[DATASET] Initialized dataset writer")
        print(f"[DATASET]   Dataset dir: {self.dataset_dir}")
        print(f"[DATASET]   Debug dir: {self.debug_dir}")

    def add_sample(
        self,
        original_img,
        filename,
        page_corners_original=None,
        rectified_img=None,
        transformation_matrix=None,
        fold_p1_original=None,
        fold_p2_original=None,
        fold_detected=False
    ):
        """
        Process one image and generate dataset sample.

        This is the main entry point called from the processing pipeline.
        It handles all transformations and saves both dataset and debug outputs.

        Args:
            original_img (np.ndarray): Raw input image (variable size, BGR)
            filename (str): Base filename (e.g., "IMG_00123.jpg")
            page_corners_original (np.ndarray): (4,2) or (4,1,2) array of corners
                                                 in original pixel coords, or None
            rectified_img (np.ndarray): Warped/rectified image or None
            transformation_matrix (np.ndarray): M (2x3) from warp_image or None
            fold_p1_original (tuple): (x, y) for fold line point 1 in original image space, or None
            fold_p2_original (tuple): (x, y) for fold line point 2 in original image space, or None
            fold_detected (bool): True if fold was detected

        Returns:
            bool: True if sample generated successfully

        Processing Steps:
            1. Resize original image to 512x512 with letterbox
            2. Transform page corners to 512x512 space
            3. If fold detected, transform fold line points to 512x512 space
            4. Generate JSON label
            5. Save 512x512 image to dataset/
            6. Generate and save debug visualization to debug/
            7. Track sample in metadata
        """
        try:
            # Step 1: Resize original image to 512x512 with letterbox
            img_512, scale, offset_x, offset_y = resize_with_letterbox(original_img, target_size=512)

            original_height, original_width = original_img.shape[:2]

            # Step 2: Determine page detection status and transform corners
            page_present = page_corners_original is not None
            page_corners_512 = None

            if page_present:
                page_corners_512 = transform_page_corners(
                    page_corners_original,
                    scale,
                    offset_x,
                    offset_y
                )

            # Step 3: Transform fold line if detected
            fold_p1_512 = None
            fold_p2_512 = None

            if fold_detected and fold_p1_original is not None and fold_p2_original is not None:
                # Transform fold line endpoints from original image space to 512x512 space
                from .coordinate_transform import transform_fold_to_512

                fold_p1_512, fold_p2_512 = transform_fold_to_512(
                    fold_p1_original,
                    fold_p2_original,
                    scale,
                    offset_x,
                    offset_y
                )

            # Step 4: Generate JSON label
            # Prepare filename without extension for paths
            base_name = os.path.splitext(filename)[0]
            file_ext = os.path.splitext(filename)[1]

            # Relative path for label
            relative_img_path = os.path.join("dataset", filename)

            label_dict = create_label_dict(
                filename=filename,
                filepath=relative_img_path,
                page_present=page_present,
                page_corners_512=page_corners_512,
                fold_present=fold_detected,
                fold_p1_512=fold_p1_512,
                fold_p2_512=fold_p2_512,
                original_width=original_width,
                original_height=original_height,
                scale=scale,
                offset_x=offset_x,
                offset_y=offset_y,
                target_size=512
            )

            # Step 5: Save 512x512 image to dataset/
            img_output_path = os.path.join(self.dataset_dir, filename)
            cv2.imwrite(img_output_path, img_512, [cv2.IMWRITE_JPEG_QUALITY, 95])

            # Step 6: Save JSON label
            json_output_path = os.path.join(self.dataset_dir, base_name + ".json")
            save_label_json(label_dict, json_output_path)

            # Step 7: Generate and save debug visualization
            debug_img = draw_debug_visualization(
                img_512,
                page_corners_512,
                fold_p1_512,
                fold_p2_512,
                page_present,
                fold_detected,
                filename=filename
            )

            debug_output_path = os.path.join(self.debug_dir, base_name + "_debug.jpg")
            save_debug_image(debug_img, debug_output_path)

            # Step 8: Track in metadata
            sample_metadata = {
                "filename": filename,
                "page_present": page_present,
                "fold_present": fold_detected,
                "image_path": img_output_path,
                "label_path": json_output_path,
                "debug_path": debug_output_path
            }
            self.samples_generated.append(sample_metadata)

            # Log success
            status_str = []
            if page_present:
                status_str.append("page")
            else:
                status_str.append("page")

            if fold_detected:
                status_str.append("fold")
            else:
                status_str.append("fold")

            print(f"[DATASET] Added sample: {filename} ({', '.join(status_str)})")

            return True

        except Exception as e:
            print(f"[DATASET] ERROR: Failed to generate sample for {filename}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def finalize(self):
        """
        Finalize dataset generation and create metadata summary.

        Creates:
            _AI_training/metadata.json

        This should be called after all samples have been added.

        Returns:
            dict: Metadata summary dictionary
        """
        print(f"\n[DATASET] Finalizing dataset generation...")

        # Generate labels list for metadata
        labels_list = []
        for sample in self.samples_generated:
            # Create minimal label entry for metadata
            label_entry = {
                "filename": sample["filename"],
                "page_present": sample["page_present"],
                "fold_present": sample["fold_present"]
            }
            labels_list.append(label_entry)

        # Create metadata summary
        metadata = create_metadata_summary(labels_list, self.dataset_dir)

        # Save metadata
        metadata_path = os.path.join(self.ai_training_dir, "metadata.json")
        save_metadata_summary(metadata, metadata_path)

        # Print summary
        print(f"[DATASET] ========================================")
        print(f"[DATASET] Dataset Generation Complete")
        print(f"[DATASET] ========================================")
        print(f"[DATASET] Total samples: {metadata['total_samples']}")
        print(f"[DATASET] With page detection: {metadata['samples_with_page']}")
        print(f"[DATASET] With fold detection: {metadata['samples_with_fold']}")
        print(f"[DATASET] Dataset directory: {self.dataset_dir}")
        print(f"[DATASET] Debug directory: {self.debug_dir}")
        print(f"[DATASET] Metadata file: {metadata_path}")
        print(f"[DATASET] ========================================")

        return metadata

    def get_sample_count(self):
        """Get number of samples generated so far."""
        return len(self.samples_generated)

    def get_samples_summary(self):
        """Get summary of all generated samples."""
        return {
            "total": len(self.samples_generated),
            "with_page": sum(1 for s in self.samples_generated if s["page_present"]),
            "with_fold": sum(1 for s in self.samples_generated if s["fold_present"])
        }


# Test function for development
if __name__ == "__main__":
    import numpy as np

    print("Testing DatasetWriter...")

    # Create temporary output directory
    test_output_dir = "/tmp/test_dataset_output"

    # Initialize writer
    writer = DatasetWriter(test_output_dir)

    # Create test images
    print("\n[Test 1] Adding sample with full detection")
    test_img_1 = np.random.randint(0, 255, (3000, 4000, 3), dtype=np.uint8)
    test_corners_1 = np.array([[100, 150], [3900, 140], [3920, 2860], [80, 2880]])
    test_rect_img_1 = np.random.randint(0, 255, (3000, 4000, 3), dtype=np.uint8)
    test_M_1 = cv2.getRotationMatrix2D((2000, 1500), 5, 1.0)

    success_1 = writer.add_sample(
        original_img=test_img_1,
        filename="test_001.jpg",
        page_corners_original=test_corners_1,
        rectified_img=test_rect_img_1,
        transformation_matrix=test_M_1,
        fold_x=2000,
        fold_detected=True
    )
    print(f"Sample 1 result: {success_1}")

    # Test sample with page only
    print("\n[Test 2] Adding sample with page only (no fold)")
    test_img_2 = np.random.randint(0, 255, (3000, 3000, 3), dtype=np.uint8)
    test_corners_2 = np.array([[150, 200], [2850, 180], [2880, 2820], [130, 2840]])

    success_2 = writer.add_sample(
        original_img=test_img_2,
        filename="test_002.jpg",
        page_corners_original=test_corners_2,
        rectified_img=None,
        transformation_matrix=None,
        fold_x=None,
        fold_detected=False
    )
    print(f"Sample 2 result: {success_2}")

    # Test sample with no detection
    print("\n[Test 3] Adding sample with no detection")
    test_img_3 = np.random.randint(0, 255, (2448, 1836, 3), dtype=np.uint8)

    success_3 = writer.add_sample(
        original_img=test_img_3,
        filename="test_003.jpg",
        page_corners_original=None,
        rectified_img=None,
        transformation_matrix=None,
        fold_x=None,
        fold_detected=False
    )
    print(f"Sample 3 result: {success_3}")

    # Finalize
    print("\n[Test 4] Finalizing dataset")
    metadata = writer.finalize()

    print("\nAll DatasetWriter tests completed!")
    print(f"Check output at: {test_output_dir}/_AI_training/")
