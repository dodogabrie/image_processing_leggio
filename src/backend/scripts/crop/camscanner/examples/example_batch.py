#!/usr/bin/env python3
"""
Example: Batch process multiple images in a directory.

Usage:
    python example_batch.py <input_dir> <output_dir>
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from camscanner import CamScanner


def main():
    if len(sys.argv) < 3:
        print("Usage: python example_batch.py <input_dir> <output_dir>")
        print("\nExample:")
        print("  python example_batch.py ./images/ ./scanned/")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all images
    image_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.tif']
    image_files = []
    for ext in image_extensions:
        image_files.extend(input_dir.glob(f"*{ext}"))
        image_files.extend(input_dir.glob(f"*{ext.upper()}"))

    if not image_files:
        print(f"No images found in {input_dir}")
        sys.exit(1)

    print("=" * 60)
    print("CamScanner - Batch Processing Example")
    print("=" * 60)
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Found {len(image_files)} images\n")

    # Create scanner
    scanner = CamScanner(debug=False)

    # Process each image
    results = {
        'success': 0,
        'failed': 0,
        'single': 0,
        'book_spread': 0,
        'partial': 0
    }

    for i, image_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] Processing: {image_path.name}")

        # Process image
        result = scanner.scan(str(image_path))

        # Update statistics
        if result.success:
            results['success'] += 1
            if result.document_type == 'single':
                results['single'] += 1
            elif result.document_type == 'book_spread':
                results['book_spread'] += 1
            elif result.document_type in ['partial_left', 'partial_right']:
                results['partial'] += 1
        else:
            results['failed'] += 1

        # Save result
        if result.success:
            output_path = output_dir / image_path.name
            result.save(output_path)
            print(f"  Type: {result.document_type}, Confidence: {result.confidence:.2f}")

            if result.warnings:
                for warning in result.warnings:
                    print(f"  Warning: {warning}")
        else:
            print(f"  Failed: {result.warnings[0] if result.warnings else 'Unknown error'}")

        print()

    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total images: {len(image_files)}")
    print(f"Successfully processed: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"\nDocument types:")
    print(f"  Single documents: {results['single']}")
    print(f"  Book spreads: {results['book_spread']}")
    print(f"  Partial books: {results['partial']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
