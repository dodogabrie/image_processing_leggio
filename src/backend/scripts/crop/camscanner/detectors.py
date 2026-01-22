"""
Document type detection and classification.

Automatically detects whether input is:
- Single flat document (receipt, paper, ID card)
- Full book spread (both pages visible with center fold)
- Partial book (one page + lateral fold to crop)
"""

import numpy as np
from typing import Tuple, Dict, Optional

from .utils import (
    detect_page_boundary,
    get_contour_bounds,
    get_page_center_x,
    get_page_width,
    calculate_fold_position_ratio,
    page_covers_full_image,
    is_valid_contour
)
from .fold_detection_hough import detect_fold_combined


class DocumentTypeDetector:
    """
    Detects document type from image analysis.

    Combines edge detection (page boundary) and fold detection (spine/edge)
    to classify input as single document, book spread, or partial book.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize detector with configuration.

        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.quality_threshold = self.config.get('quality_threshold', 0.6)
        self.debug = self.config.get('debug', False)

    def detect(self, img: np.ndarray) -> Tuple[str, float, Dict]:
        """
        Detect document type from image.

        Args:
            img: Input image (BGR)

        Returns:
            tuple: (document_type, confidence, metadata)
                - document_type: "single", "book_spread", "partial_left", "partial_right", "unknown"
                - confidence: Quality score 0.0-1.0
                - metadata: Dict with detection details
        """
        h, w = img.shape[:2]

        if self.debug:
            print(f"\n[Detector] Analyzing image: {w}x{h}")

        # Step 1: Detect page boundary
        page_contour, angle = detect_page_boundary(img, debug=self.debug)

        if page_contour is None or not is_valid_contour(page_contour, img.shape):
            if self.debug:
                print("[Detector] No valid page boundary detected")
            return "unknown", 0.0, {"reason": "no_page_boundary"}

        if self.debug:
            print(f"[Detector] Page boundary detected (angle={angle:.2f}°)")

        # Step 2: Detect fold lines by searching center, left, and right
        detections = []
        for side in ["center", "left", "right"]:
            if self.debug:
                print(f"\n[Detector] Searching for fold on '{side}' side...")
            fold_x_candidate, fold_quality_candidate, fold_method_candidate = detect_fold_combined(
                img, side=side, debug=self.debug
            )
            if fold_x_candidate is not None:
                detections.append((fold_x_candidate, fold_quality_candidate, fold_method_candidate))

        if not detections:
            fold_x, fold_quality, fold_method = None, 0.0, None
        else:
            # Select best fold based on quality score
            fold_x, fold_quality, fold_method = max(detections, key=lambda item: item[1])

        if self.debug:
            if fold_x is not None:
                print(f"\n[Detector] Best fold detected at x={fold_x} (quality={fold_quality:.3f}, method={fold_method})")
            else:
                print("\n[Detector] No fold detected in any region")

        # Step 3: Classify based on fold detection
        doc_type, confidence, classification_info = self._classify_document(
            img, page_contour, fold_x, fold_quality
        )

        # Prepare metadata
        metadata = {
            'page_contour': page_contour,
            'page_angle': angle,
            'fold_x': fold_x,
            'fold_quality': fold_quality,
            'fold_method': fold_method if fold_x is not None else None,
            **classification_info
        }

        if self.debug:
            print(f"[Detector] Classification: {doc_type} (confidence={confidence:.3f})")

        return doc_type, confidence, metadata

    def _classify_document(
        self,
        img: np.ndarray,
        page_contour: np.ndarray,
        fold_x: Optional[int],
        fold_quality: float
    ) -> Tuple[str, float, Dict]:
        """
        Classify document based on page boundary and fold detection.

        Args:
            img: Input image
            page_contour: Detected page contour (4 corners)
            fold_x: Detected fold x position (None if not found)
            fold_quality: Fold detection quality score

        Returns:
            tuple: (document_type, confidence, info_dict)
        """
        h, w = img.shape[:2]
        info = {}

        # No fold detected → single document
        if fold_x is None or fold_quality < self.quality_threshold:
            if self.debug:
                if fold_x is None:
                    print("[Classifier] No fold → single document")
                else:
                    print(f"[Classifier] Fold quality too low ({fold_quality:.3f} < {self.quality_threshold}) → single document")

            return "single", 0.8, info

        # Fold detected → determine position relative to page
        fold_ratio = calculate_fold_position_ratio(fold_x, page_contour)
        page_width = get_page_width(page_contour)
        page_center_x = get_page_center_x(page_contour)

        info['fold_ratio'] = fold_ratio
        info['page_width'] = page_width
        info['page_center_x'] = page_center_x

        if self.debug:
            print(f"[Classifier] Fold position ratio: {fold_ratio:.2f} (0=left edge, 0.5=center, 1=right edge)")
            print(f"[Classifier] Page center: x={page_center_x}, width={page_width}px")

        # Case 1: Fold at page center (0.4-0.6) → book spread
        if 0.4 <= fold_ratio <= 0.6:
            return self._classify_book_spread(img, page_contour, fold_x, fold_quality, info)

        # Case 2: Fold at left edge (< 0.2) → partial book (left page visible)
        elif fold_ratio < 0.2:
            if self.debug:
                print("[Classifier] Fold at left edge → partial_left")
            info['fold_side'] = 'left'
            return "partial_left", fold_quality, info

        # Case 3: Fold at right edge (> 0.8) → partial book (right page visible)
        elif fold_ratio > 0.8:
            if self.debug:
                print("[Classifier] Fold at right edge → partial_right")
            info['fold_side'] = 'right'
            return "partial_right", fold_quality, info

        # Case 4: Ambiguous position (0.2-0.4 or 0.6-0.8)
        else:
            if self.debug:
                print(f"[Classifier] Ambiguous fold position ({fold_ratio:.2f}) → unknown")
            info['reason'] = 'ambiguous_fold_position'
            return "unknown", fold_quality * 0.5, info

    def _classify_book_spread(
        self,
        img: np.ndarray,
        page_contour: np.ndarray,
        fold_x: int,
        fold_quality: float,
        info: Dict
    ) -> Tuple[str, float, Dict]:
        """
        Classify book spread and check for warnings.

        Args:
            img: Input image
            page_contour: Page contour
            fold_x: Fold x position
            fold_quality: Fold quality score
            info: Info dict to populate

        Returns:
            tuple: (document_type, confidence, updated_info)
        """
        # Check if page covers full image (indicates both pages visible)
        page_coverage = page_covers_full_image(page_contour, img.shape, threshold=0.85)
        info['page_coverage'] = page_coverage

        if page_coverage:
            # Full book spread detected (both pages visible)
            info['warnings'] = [
                "Full book spread detected with both pages visible. "
                "Consider photographing pages individually for better quality."
            ]

            if self.debug:
                print("[Classifier] WARNING: Full book spread (both pages visible)")

            # Lower confidence due to suboptimal capture
            confidence = fold_quality * 0.7

        else:
            # Partial book spread (only one page visible, center fold detected)
            if self.debug:
                print("[Classifier] Partial book spread (single page with center fold)")

            confidence = fold_quality

        return "book_spread", confidence, info


def detect_document_type(
    img: np.ndarray,
    quality_threshold: float = 0.6,
    debug: bool = False
) -> Tuple[str, float, Dict]:
    """
    Convenience function for document type detection.

    Args:
        img: Input image
        quality_threshold: Minimum quality for fold detection
        debug: Enable debug output

    Returns:
        tuple: (document_type, confidence, metadata)
    """
    detector = DocumentTypeDetector({
        'quality_threshold': quality_threshold,
        'debug': debug
    })

    return detector.detect(img)


if __name__ == "__main__":
    """Test document type detection on sample image."""
    import sys
    import cv2

    if len(sys.argv) < 2:
        print("Usage: python detectors.py <image_path> [--debug]")
        sys.exit(1)

    img_path = sys.argv[1]
    debug = "--debug" in sys.argv

    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load image {img_path}")
        sys.exit(1)

    print(f"Testing document type detection on: {img_path}")
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")

    # Detect document type
    doc_type, confidence, metadata = detect_document_type(img, debug=True)

    print(f"\n{'='*60}")
    print(f"RESULT: {doc_type}")
    print(f"Confidence: {confidence:.3f}")
    print(f"{'='*60}")

    if 'warnings' in metadata:
        print("\nWarnings:")
        for warning in metadata['warnings']:
            print(f"  - {warning}")

    print("\nMetadata:")
    for key, value in metadata.items():
        if key not in ['page_contour', 'warnings']:
            print(f"  {key}: {value}")
