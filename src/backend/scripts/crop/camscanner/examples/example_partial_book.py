#!/usr/bin/env python3
"""
Example: Process partial book (one page + lateral fold).

Detects fold at page edge and crops to visible page.

Usage:
    python example_partial_book.py <image_path>
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from camscanner import CamScanner


def main():
    if len(sys.argv) < 2:
        print("Usage: python example_partial_book.py <image_path>")
        print("\nExample:")
        print("  python example_partial_book.py partial_page.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    print("=" * 60)
    print("CamScanner - Partial Book Example")
    print("=" * 60)
    print(f"Input: {image_path}\n")

    # Create scanner with moderate quality threshold
    scanner = CamScanner(
        debug=False,
        quality_threshold=0.5,  # Lower threshold for edge folds
        fold_border=80  # Moderate overlap for page edge
    )

    # Process image
    result = scanner.scan(image_path)

    # Check results
    print(f"Document type: {result.document_type}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Success: {result.success}")

    if result.document_type in ["partial_left", "partial_right"]:
        fold_side = result.document_type.split("_")[1]
        print(f"Fold detected on {fold_side} edge")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    # Save output
    if result.success:
        if result.document_type in ["partial_left", "partial_right"]:
            output_path = "page_cropped_" + Path(image_path).name
            result.save(output_path)
            print(f"\nPage cropped at fold edge")
            print(f"Saved to: {output_path}")
        else:
            output_path = "processed_" + Path(image_path).name
            result.save(output_path)
            print(f"\nNot detected as partial book")
            print(f"Saved to: {output_path}")
    else:
        print("\nProcessing failed")

    print("=" * 60)


if __name__ == "__main__":
    main()
