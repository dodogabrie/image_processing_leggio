# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based image processing pipeline for automatically detecting and cropping book fold lines in scanned double-page images. Supports batch processing, A3 landscape detection, perspective correction, and intelligent document edge detection.

## Tech Stack

- **Python 3.x** with OpenCV (cv2) for image processing
- **NumPy** for numerical operations
- **PIL/Pillow** for image I/O
- **Multiprocessing** for parallel batch processing

## Development Commands

### Single Image Processing
```bash
# Basic crop with auto-detection
python crop.py input.jpg output.jpg

# With specific side detection
python crop.py input.jpg --side center output.jpg

# With rotation and smart crop
python crop.py input.jpg --rotate --smart_crop output.jpg

# Debug mode with visualizations
python crop.py input.jpg output.jpg --debug

# Format conversion
python crop.py input.jpg --output_format jpg output.jpg

# AI training dataset generation
python crop.py input.jpg output.jpg --generate-dataset
```

### Batch Processing
```bash
# Process entire directory
python main.py input_dir/ output_dir/

# With front-back couple detection (4-page renaming)
python main.py input_dir/ output_dir/ --front-back-couple

# With specific settings
python main.py input_dir/ output_dir/ --rotate --smart_crop --contour_border 150

# Export JSON only (no processing)
python main.py input_dir/ output_dir/ --export_json_mapping mapping.json --json_only
```

### Alternative Batch Processing
```bash
# Using batch_crop.py with parallel workers
python batch_crop.py input_folder/ output_folder/ --workers 4
```

## Architecture

### Three-Layer Processing Pipeline

1. **Page Detection & Perspective Correction** (`page_processor.py`)
   - Detects A3 landscape format from contour dimensions
   - Applies perspective correction via `contour_detector/` modules
   - Adds configurable border around document edges
   - Falls back gracefully if not A3 or already well-framed

2. **Fold Detection** (`fold_detection.py`)
   - Brightness profile analysis to detect book fold line
   - Parabolic fit for fold position estimation
   - Linear regression for angle detection
   - Quality scoring (0.0-1.0) to validate fold detection
   - Returns fold x-position and angle

3. **Crop & Split** (`image_processing.py`)
   - Splits image at detected fold line
   - Optional rotation to straighten fold
   - Configurable fold border to preserve overlapping content
   - Smart crop using document edge detection (optional)

### Core Modules

#### Entry Points
- **crop.py**: Single image processing with full CLI options
- **main.py**: Batch processing with ICCD renaming support, front-back couple detection
- **batch_crop.py**: Parallel batch processing wrapper

#### Processing Modules
- **src/page_processor.py**: A3 detection + perspective correction integration
- **src/image_processing.py**: Main processing orchestrator (fold detection + crop/split)
- **src/fold_detection.py**: Brightness-based fold detection algorithm
- **src/image_io.py**: Image loading/saving with metadata preservation
- **src/utils.py**: Image resizing utilities (resize_width_hd)

#### Contour Detection (in `src/contour_detector/`)
- **detect.py**: Page contour detection via edge detection
- **preprocess.py**: Grayscale conversion and noise reduction
- **transform.py**: Perspective correction (warp_image)
- **quality_evaluation.py**: Contour quality scoring
- **utils.py**: Image saving with metadata preservation

#### Dataset Generation (in `src/dataset/`)
- **dataset_writer.py**: AI training dataset generator (512x512 images + JSON labels)
- **label_generator.py**: COCO-style annotation generation
- **coordinate_transform.py**: Coordinate space transformations
- **debug_visualizer.py**: Visual debugging overlays

#### ICCD Support (optional advanced features)
- **xml_processor.py**: XML-based metadata extraction
- **iccd_renamer.py**: ICCD naming convention application
- **export_json_mapping.py**: JSON mapping export for debugging

### Processing Flow

1. **Load Image** (`load_image()`): Preserves EXIF metadata and quality
2. **Page Detection** (`process_page_if_needed()`):
   - Extract contour from edges
   - Detect if A3 landscape format (from contour dimensions)
   - Apply perspective correction if needed
   - Add border for fold detection stability
3. **Fold Detection** (`process_image()` -> `detect_fold_brightness_profile()`):
   - Compute brightness profile across image width
   - Fit parabola to find fold minimum
   - Linear regression for angle
   - Quality check (default threshold: 0.6)
4. **Crop & Split** (`apply_crop_and_split()`):
   - Optional rotation to straighten
   - Split at fold x-position with configurable border
   - Save left/right sides with `_left`/`_right` suffixes
5. **Save Results** (`save_image_with_metadata()`):
   - Preserve original EXIF metadata
   - Apply format conversion if requested
   - Resize to HD if output_format specified

### Output Naming Conventions

#### Standard Mode
- No fold detected: `original_name.ext`
- Fold detected: `original_name_left.ext` and `original_name_right.ext`

#### Front-Back Couple Mode (`--front-back-couple`)
Detects consecutive image pairs with successful fold detection:
- First image: `base_crop_1.ext` (right page), `base_crop_4.ext` (left page)
- Second image: `base_crop_2.ext` (left page), `base_crop_3.ext` (right page)
- Single images with fold: `base_crop_1.ext` and `base_crop_4.ext`

This creates proper page ordering for 4-page book spreads.

#### ICCD Mode (XML-based)
Renames files according to ICCD metadata from XML (advanced feature).

## Key Parameters

### Borders
- **--contour-border**: Border pixels for perspective correction (default: 150)
  - Added around document edges after perspective correction
  - Provides stability for fold detection
- **--fold-border**: Border pixels around fold line (default: same as contour-border)
  - Preserves overlapping content at fold
  - Prevents losing text/images near spine

### Processing Options
- **--rotate**: Apply rotation to straighten detected fold angle
- **--smart_crop**: Use document edge detection for intelligent cropping
- **--side**: Force fold side (left/right/center), default: auto-detect center
- **--output_format**: Convert to jpg/png/tiff with HD resize (1920px width)
- **--debug**: Generate debug visualizations in `*_debug/` folders
- **--save-thumbs**: Generate before/after comparison thumbnails

### Batch Processing
- **--front-back-couple**: Enable consecutive pair detection with 4-page renaming
- **--no-rename**: Force standard processing, skip ICCD renaming even if XML detected
- **--generate-dataset**: Generate AI training dataset (512x512 + JSON labels)

## File Organization

### Input Requirements
- Supported formats: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.bmp`
- Batch mode preserves directory structure
- Optional `crop_mapping.json` for custom output paths

### Output Structure
```
output_dir/
├── image_left.ext           # Left page
├── image_right.ext          # Right page
├── image_debug/             # Debug visualizations (if --debug)
│   └── fold_line_visualization.jpg
├── image_thumbs/            # Comparison thumbnails (if --save-thumbs)
│   ├── before_thumb.jpg
│   └── after_thumb.jpg
├── info.json                # Batch processing metadata
└── error.json               # Files requiring manual review
```

### info.json Structure
Tracks processing progress and results:
- `cropped`: Maps original files to output files with metadata
  - `fold_detected`, `page_detected`, `was_rotated`, `was_perspective_corrected`
  - `output_files`, `output_paths`, `output_relative_paths`
- Processing statistics and parameters

### error.json Structure
Lists files requiring review:
- `Ricontrollare`: Array of `{fname, fpath, reason}` objects
- Created only if errors/warnings exist

## Critical Implementation Details

### Coordinate Spaces
When working with fold coordinates, there are multiple coordinate spaces:
1. **Original Image Space**: Coordinates in the unprocessed input image
2. **Rectified Space (with border)**: After perspective correction + border added
3. **Rectified Space (no border)**: Before border added (what transform M operates on)

When transforming fold coordinates back to original space:
- Subtract border from detected fold coordinates first
- Apply inverse transformation matrix `M_inv`
- Add document offset (page contour min x/y) if applicable

### A3 Detection
- Detects A3 landscape by analyzing contour dimensions (not DPI-based)
- Uses coverage threshold (default: 0.90) to skip processing if already well-framed
- Page processing is skipped for non-A3 formats or well-framed A3 images

### Fold Detection Quality
- Quality score based on parabola fit residuals
- Default threshold: 0.6 (range 0.0-1.0)
- Below threshold: saves original without split
- Can be adjusted via `quality_threshold` parameter in code

### EXIF Metadata Preservation
All image operations preserve original EXIF data:
- Uses `piexif` library to extract/inject metadata
- Critical for maintaining camera settings, timestamps, GPS data

## Common Development Patterns

### Adding New Processing Steps
Insert between page processing and fold detection in `crop.py`:
```python
processed_img, was_processed, actual_border, is_a3, page_contour, transform_M = process_page_if_needed(...)
# Add new processing here on processed_img
left_side, right_side, debug_info = process_image(processed_img, ...)
```

### Modifying Fold Detection Algorithm
Edit `src/fold_detection.py`:
- `detect_fold_brightness_profile()`: Main detection function
- Adjust parabola fitting parameters or quality scoring
- Return updated `debug_info` dict for tracking

### Custom Output Naming
Modify `src/image_io.py` -> `generate_output_paths()`:
- Change `_left`/`_right` suffix logic
- Add custom directory structure
- Handle special cases (ICCD, couples, etc.)

## Dependencies

Install via `requirements.txt` (not included in this folder - should be created):
```
opencv-python
numpy
pillow
piexif
```

Optional for advanced features:
- `lxml` for XML processing (ICCD mode)
- `matplotlib` for debug visualizations

## Testing

No formal test suite included. Manual testing workflow:
1. Use `--debug` to generate visualizations
2. Check `info.json` for processing metadata
3. Review `error.json` for problematic files
4. Use `--save-thumbs` for before/after comparison
5. Test with `--generate-dataset` to verify coordinate transforms
