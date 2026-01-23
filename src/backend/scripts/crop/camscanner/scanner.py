"""
Main CamScanner class and result object.

Simple API for automatic document scanning:
    scanner = CamScanner()
    result = scanner.scan("image.jpg")
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Dict, List

from .utils import load_image
from .detectors import DocumentTypeDetector
from .processors import create_processor


class ScanResult:
    """
    Container for scan results with processed images and metadata.
    """

    def __init__(
        self,
        processed_image: Optional[np.ndarray] = None,
        left_image: Optional[np.ndarray] = None,
        right_image: Optional[np.ndarray] = None,
        document_type: str = "unknown",
        confidence: float = 0.0,
        warnings: Optional[List[str]] = None,
        debug_info: Optional[Dict] = None,
        success: bool = False
    ):
        """
        Initialize scan result.

        Args:
            processed_image: Main processed image
            left_image: Left page (for books)
            right_image: Right page (for books)
            document_type: Document classification
            confidence: Quality score 0.0-1.0
            warnings: Warning messages
            debug_info: Debug metadata
            success: True if processing succeeded
        """
        self.processed_image = processed_image
        self.left_image = left_image
        self.right_image = right_image
        self.document_type = document_type
        self.confidence = confidence
        self.warnings = warnings or []
        self.debug_info = debug_info or {}
        self.success = success

    def save(self, output_path: Union[str, Path], quality: int = 95):
        """
        Save processed image(s) to disk.

        Args:
            output_path: Output file path or directory
            quality: JPEG quality (0-100)
        """
        output_path = Path(output_path)

        # For book spreads with split pages
        if self.left_image is not None or self.right_image is not None:
            # Save to directory
            if output_path.suffix:
                # Path has extension, use as base name
                output_dir = output_path.parent
                base_name = output_path.stem
                ext = output_path.suffix
            else:
                # Path is directory
                output_dir = output_path
                base_name = "page"
                ext = ".jpg"

            output_dir.mkdir(parents=True, exist_ok=True)

            if self.left_image is not None:
                left_path = output_dir / f"{base_name}_left{ext}"
                cv2.imwrite(str(left_path), self.left_image,
                           [cv2.IMWRITE_JPEG_QUALITY, quality])

            if self.right_image is not None:
                right_path = output_dir / f"{base_name}_right{ext}"
                cv2.imwrite(str(right_path), self.right_image,
                           [cv2.IMWRITE_JPEG_QUALITY, quality])

        # For single processed image
        elif self.processed_image is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), self.processed_image,
                       [cv2.IMWRITE_JPEG_QUALITY, quality])

    def show(self, title: str = "Scan Result"):
        """
        Display result using matplotlib.

        Args:
            title: Window title
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("Matplotlib not available for display")
            return

        # Determine layout
        if self.left_image is not None and self.right_image is not None:
            # Show both pages
            fig, axes = plt.subplots(1, 2, figsize=(12, 6))
            axes[0].imshow(cv2.cvtColor(self.left_image, cv2.COLOR_BGR2RGB))
            axes[0].set_title("Left Page")
            axes[0].axis('off')
            axes[1].imshow(cv2.cvtColor(self.right_image, cv2.COLOR_BGR2RGB))
            axes[1].set_title("Right Page")
            axes[1].axis('off')
        elif self.processed_image is not None:
            # Show single image
            plt.figure(figsize=(8, 10))
            plt.imshow(cv2.cvtColor(self.processed_image, cv2.COLOR_BGR2RGB))
            plt.title(title)
            plt.axis('off')

        plt.tight_layout()
        plt.show()

    def __repr__(self) -> str:
        """String representation."""
        status = "success" if self.success else "failed"
        return (
            f"ScanResult(type={self.document_type}, "
            f"confidence={self.confidence:.2f}, "
            f"status={status})"
        )


class CamScanner:
    """
    Main document scanner with automatic type detection.

    Detects and processes:
    - Single flat documents
    - Book spreads with center fold
    - Partial books with lateral fold
    """

    def __init__(
        self,
        debug: bool = False,
        quality_threshold: float = 0.6,
        contour_border: int = 150,
        fold_border: int = 150,
        **config
    ):
        """
        Initialize scanner with configuration.

        Args:
            debug: Enable debug output and visualizations
            quality_threshold: Minimum quality for fold detection (0.0-1.0)
            contour_border: Border pixels for perspective correction
            fold_border: Border pixels around fold line
            **config: Additional configuration options
        """
        self.debug = debug
        self.config = {
            'debug': debug,
            'quality_threshold': quality_threshold,
            'contour_border': contour_border,
            'fold_border': fold_border,
            **config
        }

        # Initialize detector
        self.detector = DocumentTypeDetector(self.config)

        if self.debug:
            print(f"[CamScanner] Initialized with config: {self.config}")

    def scan(self, image: Union[str, Path, np.ndarray]) -> ScanResult:
        """
        Process image with automatic document type detection.

        Args:
            image: File path, numpy array, or PIL Image

        Returns:
            ScanResult object with processed image(s) and metadata
        """
        try:
            # Load and normalize input
            img = load_image(image)

            if self.debug:
                h, w = img.shape[:2]
                print(f"\n[CamScanner] Processing image: {w}x{h}")

            # Detect document type
            doc_type, confidence, metadata = self.detector.detect(img)

            if self.debug:
                print(f"[CamScanner] Detected: {doc_type} (confidence={confidence:.3f})")

            # Handle unknown/failed detection
            if doc_type == "unknown":
                return self._create_fallback_result(img, metadata)

            # Create appropriate processor
            processor = create_processor(doc_type, self.config)
            if processor is None:
                return self._create_fallback_result(
                    img, metadata, reason=f"No processor for type '{doc_type}'"
                )

            # Process image
            result = processor.process(img, **metadata)

            # Package result
            return self._create_result(img, result, doc_type, confidence, metadata)

        except Exception as e:
            if self.debug:
                import traceback
                traceback.print_exc()
            return self._create_error_result(image, str(e))

    def _create_result(
        self,
        original: np.ndarray,
        processing_result: Dict,
        doc_type: str,
        confidence: float,
        metadata: Dict
    ) -> ScanResult:
        """
        Package processing results into ScanResult.

        Args:
            original: Original input image
            processing_result: Result from processor
            doc_type: Document type
            confidence: Detection confidence
            metadata: Detection metadata

        Returns:
            ScanResult object
        """
        # Extract warnings from both metadata and processing result
        warnings = []
        warnings.extend(metadata.get('warnings', []))
        warnings.extend(processing_result.get('warnings', []))

        # Build debug info
        debug_info = {
            'document_type': doc_type,
            'detection_confidence': confidence,
            'processing_method': processing_result.get('method'),
            'detection_metadata': metadata,
            'processing_metadata': {
                k: v for k, v in processing_result.items()
                if k not in ['processed_image', 'left_image', 'right_image']
            }
        }

        return ScanResult(
            processed_image=processing_result.get('processed_image'),
            left_image=processing_result.get('left_image'),
            right_image=processing_result.get('right_image'),
            document_type=doc_type,
            confidence=confidence,
            warnings=warnings,
            debug_info=debug_info,
            success=processing_result.get('success', False)
        )

    def _create_fallback_result(
        self,
        img: np.ndarray,
        metadata: Dict,
        reason: Optional[str] = None
    ) -> ScanResult:
        """
        Create result with original image (fallback).

        Args:
            img: Original image
            metadata: Detection metadata
            reason: Failure reason

        Returns:
            ScanResult with original image
        """
        warnings = metadata.get('warnings', [])
        if reason:
            warnings.append(f"Processing failed: {reason}. Returning original image.")

        if self.debug:
            print(f"[CamScanner] Fallback: {reason or 'detection failed'}")

        return ScanResult(
            processed_image=img,
            document_type="unknown",
            confidence=0.0,
            warnings=warnings,
            debug_info={'reason': reason or 'detection_failed', 'metadata': metadata},
            success=False
        )

    def _create_error_result(self, image_input, error_msg: str) -> ScanResult:
        """
        Create error result.

        Args:
            image_input: Original image input
            error_msg: Error message

        Returns:
            ScanResult with error information
        """
        # Try to load image for fallback
        try:
            img = load_image(image_input)
        except:
            img = None

        return ScanResult(
            processed_image=img,
            document_type="unknown",
            confidence=0.0,
            warnings=[f"Error during processing: {error_msg}"],
            debug_info={'error': error_msg},
            success=False
        )


if __name__ == "__main__":
    """Test CamScanner on sample image."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scanner.py <image_path> [--debug]")
        print("\nExample:")
        print("  python scanner.py receipt.jpg")
        print("  python scanner.py book.jpg --debug")
        sys.exit(1)

    img_path = sys.argv[1]
    debug = "--debug" in sys.argv

    print(f"{'='*60}")
    print(f"CamScanner Test")
    print(f"{'='*60}")
    print(f"Image: {img_path}")
    print(f"Debug: {debug}")
    print()

    # Create scanner
    scanner = CamScanner(debug=debug)

    # Process image
    result = scanner.scan(img_path)

    # Display results
    print(f"\n{'='*60}")
    print(f"RESULT")
    print(f"{'='*60}")
    print(f"Document Type: {result.document_type}")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Success: {result.success}")

    if result.warnings:
        print(f"\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    # Save results
    if result.success:
        print(f"\nSaving results...")
        if result.left_image is not None or result.right_image is not None:
            result.save("output/")
            print("  Saved to: output/page_left.jpg, output/page_right.jpg")
        else:
            result.save("output.jpg")
            print("  Saved to: output.jpg")
    else:
        print("\nProcessing failed, no output saved")

    print(f"\n{'='*60}")
