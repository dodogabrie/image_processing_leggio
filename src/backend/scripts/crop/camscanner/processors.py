"""
Document processing pipelines.

Three specialized processors:
1. SingleDocumentProcessor - Flat documents (receipts, papers, ID cards)
2. BookSpreadProcessor - Books with center fold (split into left/right)
3. PartialBookProcessor - Partial books with lateral fold (crop one page)
"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple

from .utils import (
    apply_perspective_correction,
    split_at_fold,
    crop_to_fold
)


class DocumentProcessor:
    """
    Base processor with shared configuration and utilities.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize processor with configuration.

        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.contour_border = self.config.get('contour_border', 150)
        self.fold_border = self.config.get('fold_border', 150)
        self.quality_threshold = self.config.get('quality_threshold', 0.6)
        self.debug = self.config.get('debug', False)

    def _log(self, message: str):
        """Print debug message if debug enabled."""
        if self.debug:
            print(f"[Processor] {message}")


class SingleDocumentProcessor(DocumentProcessor):
    """
    Process single flat document (no folds).

    Pipeline:
    1. Perspective correction (straighten document)
    2. Smart crop (remove background)
    3. Return processed image
    """

    def process(
        self,
        img: np.ndarray,
        page_contour: np.ndarray,
        **metadata
    ) -> Dict:
        """
        Process single flat document.

        Args:
            img: Input image
            page_contour: Detected page boundary (4 corners)
            **metadata: Additional metadata from detector

        Returns:
            dict: Processing result with keys:
                - processed_image: Final processed image
                - success: True if processing succeeded
                - method: Processing method used
        """
        self._log("Processing single document")

        try:
            # Apply perspective correction
            warped, transform_M = apply_perspective_correction(
                img, page_contour, border=self.contour_border, debug=self.debug
            )

            if warped is None:
                self._log("Perspective correction failed, returning original")
                return {
                    'processed_image': img,
                    'success': False,
                    'method': 'fallback_original',
                    'reason': 'perspective_correction_failed'
                }

            self._log(f"Perspective correction applied (border={self.contour_border}px)")

            # Successful processing
            return {
                'processed_image': warped,
                'success': True,
                'method': 'perspective_correction',
                'transform_matrix': transform_M
            }

        except Exception as e:
            self._log(f"Processing failed: {e}")
            return {
                'processed_image': img,
                'success': False,
                'method': 'fallback_original',
                'error': str(e)
            }


class BookSpreadProcessor(DocumentProcessor):
    """
    Process book spread with center fold.

    Pipeline:
    1. Perspective correction
    2. Detect fold quality
    3. Split at fold (left/right pages)
    4. Check warnings (both pages visible)
    5. Return left + right images
    """

    def process(
        self,
        img: np.ndarray,
        page_contour: np.ndarray,
        fold_x: int,
        fold_quality: float,
        **metadata
    ) -> Dict:
        """
        Process book spread with center fold.

        Args:
            img: Input image
            page_contour: Detected page boundary
            fold_x: Fold x position
            fold_quality: Fold detection quality
            **metadata: Additional metadata

        Returns:
            dict: Processing result with keys:
                - left_image: Left page (or None)
                - right_image: Right page (or None)
                - processed_image: Full processed image (before split)
                - success: True if processing succeeded
                - method: Processing method used
                - warnings: List of warning messages
        """
        self._log("Processing book spread")
        warnings = metadata.get('warnings', [])

        try:
            # Apply perspective correction first
            warped, transform_M = apply_perspective_correction(
                img, page_contour, border=self.contour_border, debug=self.debug
            )

            if warped is None:
                self._log("Perspective correction failed")
                return {
                    'processed_image': img,
                    'left_image': None,
                    'right_image': None,
                    'success': False,
                    'method': 'fallback_original',
                    'warnings': warnings,
                    'reason': 'perspective_correction_failed'
                }

            self._log(f"Perspective correction applied")

            # Transform fold_x to warped image coordinates
            h = img.shape[0]
            fold_line = np.array([[[float(fold_x), 0.0], [float(fold_x), float(h-1)]]], dtype=np.float32)
            warped_fold_line = cv2.perspectiveTransform(fold_line, transform_M)
            warped_fold_x = int(np.mean(warped_fold_line[0, :, 0]))

            # Check fold quality
            if fold_quality < self.quality_threshold:
                self._log(f"Fold quality too low ({fold_quality:.3f}), not splitting")
                warnings.append(
                    f"Fold detection quality low ({fold_quality:.2f}). "
                    "Image not split into pages."
                )
                return {
                    'processed_image': warped,
                    'left_image': None,
                    'right_image': None,
                    'success': True,
                    'method': 'no_split_low_quality',
                    'warnings': warnings
                }

            # Split at fold
            left_page, right_page = split_at_fold(
                warped, warped_fold_x, fold_border=self.fold_border
            )

            self._log(f"Split at fold (x={warped_fold_x}, border={self.fold_border}px)")
            self._log(f"Left page: {left_page.shape[1]}x{left_page.shape[0]}")
            self._log(f"Right page: {right_page.shape[1]}x{right_page.shape[0]}")

            return {
                'processed_image': warped,
                'left_image': left_page,
                'right_image': right_page,
                'success': True,
                'method': 'split_at_fold',
                'fold_x': warped_fold_x,
                'transform_matrix': transform_M,
                'warnings': warnings
            }

        except Exception as e:
            self._log(f"Processing failed: {e}")
            return {
                'processed_image': img,
                'left_image': None,
                'right_image': None,
                'success': False,
                'method': 'fallback_original',
                'warnings': warnings,
                'error': str(e)
            }


class PartialBookProcessor(DocumentProcessor):
    """
    Process partial book with lateral fold.

    Pipeline:
    1. Determine crop direction (keep visible page, remove fold side)
    2. Crop to fold boundary
    3. Perspective correction on cropped region
    4. Return single processed page
    """

    def process(
        self,
        img: np.ndarray,
        page_contour: np.ndarray,
        fold_x: int,
        fold_side: str,
        **metadata
    ) -> Dict:
        """
        Process partial book (one page + lateral fold).

        Args:
            img: Input image
            page_contour: Detected page boundary
            fold_x: Fold x position
            fold_side: Which side fold is on ('left' or 'right')
            **metadata: Additional metadata

        Returns:
            dict: Processing result with keys:
                - processed_image: Cropped and corrected page
                - success: True if processing succeeded
                - method: Processing method used
                - fold_side: Which side was cropped
        """
        self._log(f"Processing partial book (fold on {fold_side} side)")

        try:
            # First apply perspective correction to entire image
            warped, transform_M = apply_perspective_correction(
                img, page_contour, border=self.contour_border, debug=self.debug
            )

            if warped is None:
                self._log("Perspective correction failed")
                return {
                    'processed_image': img,
                    'success': False,
                    'method': 'fallback_original',
                    'reason': 'perspective_correction_failed'
                }

            self._log("Perspective correction applied")

            # Since warp_image applies rotation/perspective, the fold position changes
            # For simplicity, just crop based on image dimensions rather than transforming coords
            # For partial_left (fold on left), keep right 75% of warped image
            # For partial_right (fold on right), keep left 75% of warped image
            h, w = warped.shape[:2]

            if fold_side == 'left':
                # Keep right side (main page), remove left fold
                crop_start = int(w * 0.25)
                cropped = warped[:, crop_start:]
                keep_side = 'right'
            else:
                # Keep left side (main page), remove right fold
                crop_end = int(w * 0.75)
                cropped = warped[:, :crop_end]
                keep_side = 'left'

            self._log(f"Cropped to {keep_side} side")
            self._log(f"Result: {cropped.shape[1]}x{cropped.shape[0]}")

            return {
                'processed_image': cropped,
                'success': True,
                'method': 'crop_at_fold',
                'fold_side': fold_side,
                'kept_side': keep_side,
                'transform_matrix': transform_M
            }

        except Exception as e:
            self._log(f"Processing failed: {e}")
            return {
                'processed_image': img,
                'success': False,
                'method': 'fallback_original',
                'error': str(e)
            }


def create_processor(document_type: str, config: Optional[Dict] = None) -> Optional[DocumentProcessor]:
    """
    Factory function to create appropriate processor for document type.

    Args:
        document_type: Type of document ("single", "book_spread", "partial_left", "partial_right")
        config: Optional configuration dict

    Returns:
        DocumentProcessor instance or None if type unknown
    """
    processors = {
        'single': SingleDocumentProcessor,
        'book_spread': BookSpreadProcessor,
        'partial_left': PartialBookProcessor,
        'partial_right': PartialBookProcessor
    }

    processor_class = processors.get(document_type)
    if processor_class is None:
        return None

    return processor_class(config)


if __name__ == "__main__":
    """Test processors on sample image."""
    import sys
    import cv2
    from detectors import detect_document_type

    if len(sys.argv) < 2:
        print("Usage: python processors.py <image_path> [--debug]")
        sys.exit(1)

    img_path = sys.argv[1]
    debug = "--debug" in sys.argv

    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load image {img_path}")
        sys.exit(1)

    print(f"Testing processors on: {img_path}")
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")

    # Detect document type
    print("\n=== Document Detection ===")
    doc_type, confidence, metadata = detect_document_type(img, debug=debug)
    print(f"Detected: {doc_type} (confidence={confidence:.3f})")

    # Create appropriate processor
    processor = create_processor(doc_type, {'debug': debug})
    if processor is None:
        print(f"Error: No processor for type '{doc_type}'")
        sys.exit(1)

    # Process image
    print(f"\n=== Processing with {processor.__class__.__name__} ===")
    result = processor.process(img, **metadata)

    print(f"\nSuccess: {result['success']}")
    print(f"Method: {result['method']}")

    if result['success']:
        # Save results
        if 'left_image' in result and result['left_image'] is not None:
            cv2.imwrite("output_left.jpg", result['left_image'])
            print("Saved: output_left.jpg")

        if 'right_image' in result and result['right_image'] is not None:
            cv2.imwrite("output_right.jpg", result['right_image'])
            print("Saved: output_right.jpg")

        if 'processed_image' in result:
            cv2.imwrite("output_processed.jpg", result['processed_image'])
            print("Saved: output_processed.jpg")

    if 'warnings' in result and result['warnings']:
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
