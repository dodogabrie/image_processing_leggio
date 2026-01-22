#!/usr/bin/env python3
"""
Example: Process single flat document (receipt, ID card, paper).

Usage:
    python example_single_doc.py <image_path>
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from camscanner import CamScanner


def main():
    if len(sys.argv) < 2:
        print("Usage: python example_single_doc.py <image_path>")
        print("\nExample:")
        print("  python example_single_doc.py receipt.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    print("=" * 60)
    print("CamScanner - Single Document Example")
    print("=" * 60)
    print(f"Input: {image_path}\n")

    # Create scanner
    scanner = CamScanner(debug=False)

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
        output_path = "scanned_" + Path(image_path).name
        result.save(output_path)
        print(f"\nSaved to: {output_path}")
    else:
        print("\nProcessing failed, original image returned")

    print("=" * 60)


if __name__ == "__main__":
    main()
