#!/usr/bin/env python3
"""
Example: Process book spread with center fold.

Automatically detects fold line and splits into left/right pages.

Usage:
    python example_book.py <image_path>
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from camscanner import CamScanner


def main():
    if len(sys.argv) < 2:
        print("Usage: python example_book.py <image_path>")
        print("\nExample:")
        print("  python example_book.py book_spread.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    print("=" * 60)
    print("CamScanner - Book Spread Example")
    print("=" * 60)
    print(f"Input: {image_path}\n")

    # Create scanner with higher fold border for books
    scanner = CamScanner(
        debug=False,
        fold_border=100  # Larger overlap for book spine
    )

    # Process image
    result = scanner.scan(image_path)

    # Check results
    print(f"Document type: {result.document_type}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Success: {result.success}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    # Save output
    if result.success:
        if result.document_type == "book_spread":
            # Book was split into pages
            if result.left_image is not None or result.right_image is not None:
                base_name = Path(image_path).stem
                result.save(f"output/{base_name}")
                print(f"\nPages saved to:")
                print(f"  output/{base_name}_left.jpg")
                print(f"  output/{base_name}_right.jpg")
            else:
                # Book detected but not split (low quality fold)
                output_path = "book_" + Path(image_path).name
                result.save(output_path)
                print(f"\nBook detected but not split (low fold quality)")
                print(f"Saved to: {output_path}")
        else:
            # Not a book spread
            output_path = "processed_" + Path(image_path).name
            result.save(output_path)
            print(f"\nNot detected as book spread")
            print(f"Saved to: {output_path}")
    else:
        print("\nProcessing failed")

    print("=" * 60)


if __name__ == "__main__":
    main()
