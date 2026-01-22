#!/usr/bin/env python3
"""
Export JSON Mapping Tool

Exports complete XML-to-ICCD filename mappings as JSON for debugging and verification.

Usage:
    python export_json_mapping.py <xml_file> <folder_path> <output_json>
    python export_json_mapping.py /path/to/Busta_42.xml /path/to/Busta_42 mapping.json

Output JSON structure:
{
  "metadata": {
    "generated_at": "2025-01-XX...",
    "total_mappings": 123
  },
  "mappings": [
    {
      "fascicolo_number": "1335",
      "total_images": 45,
      "images": [
        {
          "original_filename": "0398.tif",
          "full_path": "/path/to/0398.tif",
          "subdir": "tiff",
          "fascicolo_number": "1335",
          "oggetto_number": "0001",
          "document_type": "S",
          "document_type_name": "Scheda",
          "sequence_number": "0001",
          "page_number": 1,
          "iccd_filename": "ICCD_FSC01335-0001_01_S0001_01.tif"
        }
      ]
    }
  ],
  "summary": {
    "total_images": 123,
    "by_fascicolo": {"1335": 45, "1336": 78},
    "by_document_type": {"S": 89, "A": 12, "F": 15, "P": 7},
    "by_file_type": {".tif": 100, ".jpg": 23}
  }
}
"""

import argparse
import os
import sys

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from xml_processor import XMLProcessor


def main():
    parser = argparse.ArgumentParser(
        description="Export XML to ICCD filename mappings as JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("xml_file", help="Path to XML file (e.g., Busta_42.xml)")
    parser.add_argument("folder_path", help="Path to image folder (e.g., Busta_42/)")
    parser.add_argument("output_json", help="Output JSON file path (e.g., mapping.json)")

    parser.add_argument("--no-jpg", dest="process_jpg", action="store_false", default=True,
                       help="Don't process .jpg/.jpeg files")
    parser.add_argument("--no-tiff", dest="process_tiff", action="store_false", default=True,
                       help="Don't process .tiff/.tif files")
    parser.add_argument("--no-iccd-names", dest="include_iccd_names", action="store_false", default=True,
                       help="Don't generate ICCD filename previews")

    args = parser.parse_args()

    # Validate input paths
    if not os.path.exists(args.xml_file):
        print(f"[ERROR] XML file not found: {args.xml_file}")
        return 1

    if not os.path.exists(args.folder_path):
        print(f"[ERROR] Folder path not found: {args.folder_path}")
        return 1

    # Initialize processor
    processor = XMLProcessor()

    print(f"[INFO] Exporting mappings from XML: {args.xml_file}")
    print(f"[INFO] Image folder: {args.folder_path}")
    print(f"[INFO] Output JSON: {args.output_json}")
    print(f"[INFO] Process JPG: {args.process_jpg}")
    print(f"[INFO] Process TIFF: {args.process_tiff}")
    print(f"[INFO] Include ICCD names: {args.include_iccd_names}")
    print()

    try:
        # Export to JSON
        success = processor.export_xml_mappings_to_json(
            args.xml_file,
            args.folder_path,
            args.output_json,
            process_jpg=args.process_jpg,
            process_tiff=args.process_tiff
        )

        if success:
            print(f"\n[SUCCESS] JSON mapping exported successfully!")
            print(f"[INFO] You can now inspect the complete mapping in: {args.output_json}")

            # Show sample of the JSON structure
            try:
                import json
                with open(args.output_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                print(f"\n[PREVIEW] JSON structure preview:")
                print(f"  Total mappings: {data['metadata']['total_mappings']}")
                print(f"  Fascicoli count: {len(data['mappings'])}")

                if data['mappings']:
                    first_fasc = data['mappings'][0]
                    print(f"  First fascicolo: {first_fasc['fascicolo_number']} ({first_fasc['total_images']} images)")

                    if first_fasc['images']:
                        first_img = first_fasc['images'][0]
                        print(f"  Sample mapping: {first_img['original_filename']} -> {first_img.get('iccd_filename', 'N/A')}")

            except Exception as e:
                print(f"[WARNING] Could not show preview: {e}")

            return 0
        else:
            print(f"\n[ERROR] Failed to export JSON mapping")
            return 1

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return 1


def export_all_bustas(input_dir: str, output_dir: str, process_jpg: bool = True, process_tiff: bool = True):
    """
    Export JSON mappings for all Bustas in a directory

    Args:
        input_dir: Directory containing Busta folders and XML files
        output_dir: Directory to save JSON mapping files
        process_jpg: Whether to process .jpg/.jpeg files
        process_tiff: Whether to process .tiff/.tif files
    """
    processor = XMLProcessor()

    # Discover all Busta pairs
    folder_pairs = processor.discover_busta_files(input_dir)

    if not folder_pairs:
        print(f"[ERROR] No Busta folders found in {input_dir}")
        return

    print(f"[INFO] Found {len(folder_pairs)} Busta pairs")
    os.makedirs(output_dir, exist_ok=True)

    successful = 0
    failed = 0

    for folder_path, xml_file in folder_pairs:
        busta_name = os.path.basename(xml_file).replace('.xml', '')
        output_json = os.path.join(output_dir, f"{busta_name}_mapping.json")

        print(f"\n[INFO] Processing {busta_name}...")

        try:
            success = processor.export_xml_mappings_to_json(
                xml_file, folder_path, output_json, process_jpg, process_tiff
            )

            if success:
                successful += 1
                print(f"[OK] {busta_name} -> {output_json}")
            else:
                failed += 1
                print(f"[FAILED] {busta_name}")

        except Exception as e:
            failed += 1
            print(f"[ERROR] {busta_name}: {e}")

    print(f"\n[SUMMARY] Processed {len(folder_pairs)} Bustas")
    print(f"[SUMMARY] Successful: {successful}")
    print(f"[SUMMARY] Failed: {failed}")


if __name__ == "__main__":
    sys.exit(main())