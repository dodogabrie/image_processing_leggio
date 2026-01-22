#!/usr/bin/env python3
"""
batch_crop.py

Script for batch processing multiple images using crop.py functionality.
Processes all images in a specified input folder and saves results to an output folder.

Usage:
    python batch_crop.py input_folder output_folder [--side left|right|center] [--debug] [--output_format jpg|png|tiff] [--rotate] [--smart_crop]
"""

import argparse
import os
import sys
from pathlib import Path
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Import the main function from crop.py
sys.path.append(os.path.dirname(__file__))
from crop import main as crop_main

# Supported image extensions
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}

def is_image_file(filename):
    """Check if file has a supported image extension."""
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS

def get_image_files(input_folder):
    """Get all supported image files from input folder."""
    input_path = Path(input_folder)
    if not input_path.exists():
        raise FileNotFoundError(f"Input folder not found: {input_folder}")

    image_files = []
    for file_path in input_path.iterdir():
        if file_path.is_file() and is_image_file(file_path.name):
            image_files.append(str(file_path))

    return sorted(image_files)

def process_single_image(args_tuple):
    """Process a single image using crop.py functionality."""
    input_file, output_folder, crop_args = args_tuple

    try:
        # Construct arguments for crop.py
        input_filename = Path(input_file).name
        output_path = os.path.join(output_folder, input_filename)

        # Build command line arguments
        sys_argv_backup = sys.argv[:]
        sys.argv = ['crop.py', input_file, output_path]

        # Add optional arguments
        if crop_args.get('side'):
            sys.argv.extend(['--side', crop_args['side']])
        if crop_args.get('debug'):
            sys.argv.append('--debug')
        if crop_args.get('output_format'):
            sys.argv.extend(['--output_format', crop_args['output_format']])
        if crop_args.get('rotate'):
            sys.argv.append('--rotate')
        if crop_args.get('smart_crop'):
            sys.argv.append('--smart_crop')
        if crop_args.get('contour_border'):
            sys.argv.extend(['--contour-border', str(crop_args['contour_border'])])
        if crop_args.get('fold_border'):
            sys.argv.extend(['--fold-border', str(crop_args['fold_border'])])
        if crop_args.get('save_thumbs'):
            sys.argv.append('--save-thumbs')

        # Add input_base_dir for preserving folder structure
        sys.argv.extend(['--input_base_dir', str(Path(input_file).parent)])

        # Call crop.py main function
        crop_main()

        # Restore sys.argv
        sys.argv = sys_argv_backup

        return f"Processed: {input_filename}"

    except Exception as e:
        # Restore sys.argv in case of error
        sys.argv = sys_argv_backup
        return f"[ERROR] Error processing {Path(input_file).name}: {str(e)}"

def main():
    """Main function for batch processing."""
    parser = argparse.ArgumentParser(description="Batch process images using crop.py")
    parser.add_argument("input_folder", help="Input folder containing images")
    parser.add_argument("output_folder", help="Output folder for processed images")
    parser.add_argument("--side", choices=("left", "right", "center"), default=None,
                       help="Side of the fold (default: center)")
    parser.add_argument("--debug", action="store_true",
                       help="Generate debug visualizations")
    parser.add_argument("--output_format", choices=("jpg", "png", "tiff"), default=None,
                       help="Output format. If specified, images will be resized to HD and converted to this format.")
    parser.add_argument("--rotate", action="store_true", default=False,
                       help="Apply rotation to straighten the fold. Default is False.")
    parser.add_argument("--smart_crop", action="store_true", default=False,
                       help="Use document edge detection for intelligent cropping. Default is False.")
    parser.add_argument("--contour-border", type=int, default=150,
                       help="Border pixels for contour detection perspective correction (default: 150).")
    parser.add_argument("--fold-border", type=int, default=None,
                       help="Border pixels around fold line for overlapping content (default: same as contour-border).")
    parser.add_argument("--save-thumbs", action="store_true", default=False,
                       help="Generate before/after comparison thumbnails (default: False).")
    parser.add_argument("--workers", type=int, default=None,
                       help="Number of parallel workers (default: number of CPU cores)")

    args = parser.parse_args()

    # Create output folder if it doesn't exist
    output_path = Path(args.output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get all image files
    try:
        image_files = get_image_files(args.input_folder)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if not image_files:
        print(f"No supported image files found in {args.input_folder}")
        return 1

    print(f"Found {len(image_files)} image(s) to process")
    print(f"Output folder: {args.output_folder}")

    # Prepare arguments for crop processing
    crop_args = {
        'side': args.side,
        'debug': args.debug,
        'output_format': args.output_format,
        'rotate': args.rotate,
        'smart_crop': args.smart_crop,
        'contour_border': args.contour_border,
        'fold_border': args.fold_border,
        'save_thumbs': args.save_thumbs,
    }

    # Determine number of workers
    max_workers = args.workers if args.workers else multiprocessing.cpu_count()
    print(f"Using {max_workers} parallel workers")

    # Process images in parallel
    tasks = [(img_file, args.output_folder, crop_args) for img_file in image_files]

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_image, task) for task in tasks]

        processed_count = 0
        error_count = 0

        for future in as_completed(futures):
            result = future.result()
            print(result)

            if result.startswith("Processed:"):
                processed_count += 1
            else:
                error_count += 1

    print(f"\nBatch processing completed:")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(image_files)}")

    return 0 if error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())