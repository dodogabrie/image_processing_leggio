# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Electron-based desktop application for preprocessing images and videos for the Leggio project. The app processes media files (images, videos) with operations like cropping, thumbnail generation, format conversion (WebP), video optimization, and CSV-based organization.

### Complete Workflow Summary

1. **User selects input folder** containing:
   - Original images/videos (any format, any nested structure)
   - Optional CSV file with metadata

2. **Configure processing options**:
   - Enable/disable image cropping (book fold detection)
   - Enable/disable video optimization (requires FFmpeg)
   - Set max CSV rows to process (for testing)
   - Configure CSV column mapping (via custom JSON or use default)

3. **Processing phase** (`processDir()`):
   - Scans all images/videos recursively
   - Crops images (if enabled) using Python OpenCV script
   - Converts all images to WebP format
   - Generates thumbnails (low_quality, gallery profiles)
   - Optimizes videos (if enabled) with H.264/H.265 encoding
   - Outputs to `finalOutput/` with preserved structure + `thumbnails/` subfolder

4. **Organization phase** (if CSV exists - `organizeFromCsv()`):
   - Reads CSV from input folder
   - Matches CSV rows to processed WebP images by `identifier`
   - Groups images by `groupBy` field into document folders
   - Copies to organized structure with slug-based naming
   - Generates JSON metadata per document group

5. **Final output**:
   - `organized/` - Document folders with renamed images
   - `organized_thumbnails/` - Thumbnails grouped by document
   - JSON metadata files
   - `output.zip` - Complete archive ready for deployment

## Tech Stack

- **Frontend**: Vue 3 + Vite (running on port 3000 in development)
- **Backend**: Node.js (ES modules) + Electron
- **Python Scripts**: OpenCV-based image processing (crop.py)
- **Key Libraries**: Sharp (image processing), FFmpeg (video processing), csv-parse

## Development Commands

### Running the app
```bash
npm run dev              # Start dev server (Vue + Electron)
npm run start            # Alias for dev
```

### Building
```bash
npm run build            # Build for production (Vite build + Python prep + electron-builder)
npm run prepare-python   # Prepare Python virtual environment for build
```

### Python Setup
Python environment setup is handled automatically by `src/backend/scripts/setup-python.js`. The script creates a venv and installs dependencies from `requirements.txt`.

## Architecture

### Three-Layer Structure

1. **Electron Main Process** (`src/electron/main.js`)
   - Creates BrowserWindow, handles IPC communication
   - Entry point for all backend operations
   - Manages dialog interactions (folder selection)
   - Paths change based on `app.isPackaged` (dev vs production)

2. **Backend Processing Layer** (`src/backend/`)
   - **media_processor.js**: Main orchestrator for processing entire directories
   - **worker_forks.js**: Spawns child processes for CPU-intensive tasks
   - **image_processor.js**: Legacy/minimal (most logic moved to media_processor)
   - **postprocessing.js**: CSV-based organization and ZIP creation
   - **json_generator.js**: Generates JSON metadata for documents

3. **Vue Frontend** (`src/client/`)
   - Single-page app with progress tracking UI
   - Components: folder progress display, CSV mapping, CSV preview
   - Communicates via IPC through preload script (`src/electron/preload.cjs`)

### Worker Architecture

The app uses multiple worker types for parallel processing:

- **crop_worker.js**: Calls Python script (crop.py) via spawn for book fold detection and cropping
- **webp_worker.js**: Converts images to WebP format
- **thumbnail_worker.js**: Generates thumbnails (low_quality, gallery profiles)
- **video_worker.js**: Video optimization using FFmpeg
- **video_thumbnail_worker.js**: Extracts frames from videos
- **video_optimization_worker.js**: Applies encoding profiles (web, mobile, archive)
- **xml_worker.js**: Processes XML metadata
- **zip_worker.js**: Creates ZIP archives
- **organize_by_csv.js**: Maps CSV data to files, handles origin_folder logic

Workers are forked processes managed by `worker_forks.js`, limited by CPU count (`MAX_PARALLEL = cpus - 1 or cpus/2`).

### Batch Processing

All intensive operations use `processInBatches()` pattern (in media_processor.js):
- Limits concurrent operations to MAX_PARALLEL
- Uses Promise.allSettled for error tolerance
- Queue-based execution with Promise.race

## Key Processing Flows

### 1. Main Image/Video Processing
`processDir()` in media_processor.js:
1. Scan directory recursively (excluding EXCLUDED_FOLDERS)
2. For each image/video file:
   - Optional: Crop via Python script (crop.py)
   - Convert to WebP
   - Generate thumbnails (low_quality, gallery)
   - For videos: optimize + generate thumbnail frames
3. Output structure: `finalOutput/` with processed images + `finalOutput/thumbnails/` for thumbnails
4. Progress tracking via IPC to renderer

### 2. CSV-Based Organization
`postProcessResults()` in postprocessing.js → `organizeFromCsv()`:

**Expected Input Structure** (selected by user):
```
input_folder/
├── data.csv                    # CSV with metadata
└── (any nested structure)      # Original images (not used directly)
```

**Processing Flow**:
1. First pass: `processDir()` processes the input folder → creates `finalOutput/` with:
   - All processed WebP images (flat or nested structure preserved)
   - `thumbnails/` subfolder with thumbnails

2. Second pass (if CSV exists): `organizeFromCsv()` reads CSV and reorganizes:
   - **webpDir parameter**: Points to `finalOutput/` (already processed WebP images)
   - Reads CSV from input folder
   - For each CSV row:
     - Extract `identifier` (filename without extension, e.g., "IMG_001")
     - Extract `groupBy` field (determines which folder/document the image belongs to)
     - Extract optional `origin_folder` field:
       - If present: Look for `identifier.webp` ONLY in `webpDir/origin_folder/`
       - If empty: Search globally in `webpDir/` using file index
       - Resolution: try direct path first (`webpDir/origin_folder/`), else recursive search by folder name
     - Copy matched image to `outputDir/organized/{groupBy_slug}/{slug}_{identifier}.webp`
     - Copy thumbnails to `outputDir/organized_thumbnails/{groupBy_slug}/`
     - Accumulate metadata per group

3. Generate JSON metadata files per document group

4. Create ZIP archive with:
   - `organized/` folder (final organized images)
   - `organized_thumbnails/` folder
   - JSON metadata files

### 3. Python Crop Script (crop.py)
Automatic book fold detection algorithm:
- Auto-detects fold side (left/right) via brightness analysis
- Parabolic fit for fold position estimation
- Linear regression for angle detection
- Crop + rotation to straighten page
- Outputs JPG at 1920px width, quality 90
- Debug mode available with matplotlib visualizations

## Critical Path Handling

### Python Environment
- Dev: looks for `src/backend/venv/`
- Production: expects `build-venv/` copied to `resources/venv/`
- Auto-setup via `setupPythonEnv()` on first run
- Platform-specific paths: Windows uses `Scripts/python.exe`, Linux/Mac uses `bin/python3`

### File Paths (packaged vs dev)
Always check `app.isPackaged` to determine paths:
- Dev: use `process.cwd()` or relative paths from `__dirname`
- Packaged: use `process.resourcesPath` + `app.asar` paths

### IPC Communication
- Main -> Renderer: `webContents.send()`
- Renderer -> Main: `ipcRenderer.invoke()` (defined in preload.cjs)
- Progress updates: `progress:update`, `csv:progress` events

## Configuration Files

### Thumbnail Profiles
Defined in `media_processor.js`:
- `low_quality`: 640x480, quality 75, WebP
- `gallery`: 1920x1080, quality 75, WebP

### Video Optimization Profiles
Defined in `media_processor.js`:
- `web`: H.264, CRF 23, 1920x1080
- `mobile`: H.264, CRF 28, 1280x720
- `archive`: H.265, CRF 28, 1920x1080

### CSV Mapping
User-configurable mapping stored in `public/csv-mappings.json`:
- Maps CSV columns to document metadata fields
- Supports multi-language fields (it, en, de)
- Handled by `useCsvMapping.js` composable

## Build Process

1. `vite build` - Compiles Vue app to `dist/client/`
2. `prepare-python-build.js` - Creates `build-venv/` with Python dependencies
3. `electron-builder` - Packages app with:
   - extraResources: public files, build-venv
   - asarUnpack: crop.py, requirements.txt
   - Platform-specific targets: AppImage/deb (Linux), nsis (Windows), dmg (Mac)

## CSV Mapping Configuration

The app uses a flexible JSON-based mapping system to connect CSV columns to metadata fields.

### Mapping Files (in `public/`)
- **`default_csv_map.json`**: Default mapping shipped with the app
- **`custom_csv_map.json`**: User-uploaded custom mapping (takes precedence over default)
- **`database_bridge.json`**: Schema documentation describing each field's purpose

### UI Components
- **CustomCsvMapLoader.vue**: Allows users to:
  - Upload custom JSON mapping files
  - Download current mapping (for editing)
  - Remove custom mapping (revert to default)
  - Preview active mapping structure

### Mapping Structure
Maps CSV column names to database field paths for both document and image metadata:

```json
{
  "document": {
    "identifier": "Codice",              // CSV column containing unique ID
    "groupBy": "Titolo",                 // CSV column for document grouping
    "origin_folder": null,               // Optional: CSV column with folder path
    "title": "Titolo",
    "creator": "AUTORE",
    "active": "MOSTRARE NEL LEGGIO",
    "date": "DATA"
  },
  "image": {
    "filename": "Codice",
    "nomenclature": "Soggetto",
    "sequence_number": "1",
    "rich_description_prefix": "DIDASCALIA PER LEGGIO",
    "datetime_created": "DATA"
  }
}
```

### Mapping Resolution (`useCsvMapping.js` composable)
1. Load mapping: tries `custom_csv_map.json` first, falls back to `default_csv_map.json`
2. Flatten nested objects using dot notation (e.g., `image_dimensions.width`)
3. Parse CSV headers to detect base fields and language variants
4. Match CSV column descriptors to actual CSV headers (case-insensitive substring match)
5. Detect available languages per field (from `[lang]` suffixes)
6. Provide resolved mapping to backend

### Multi-Language Support
Supports two CSV header formats:
- **Bracket notation**: `title[it]`, `title[en]`, `title[de]`
- **Underscore notation**: `title_it`, `title_en`, `title_de`

Backend automatically groups language variants into objects: `{ it: "...", en: "...", de: "..." }`

**Special fields** (no multi-language grouping):
`identifier`, `origin_folder`, `groupBy`, `active`, `date`, `language`, `metadata_available`, `metadata_just_year`

## Important Notes

- **ES Modules**: All backend code uses ES modules (import/export), requires shims for `__dirname`
- **Logger**: Centralized logging via `Logger.js` class used throughout backend
- **Error Handling**: Workers use exit codes (crop.py: 0=success, 2=no-crop, other=error)
- **FFmpeg Dependency**: Video optimization requires FFmpeg installed on system
- **CSV origin_folder Logic**:
  - When specified: file MUST exist in `webpDir/origin_folder/` (no fallback to global index)
  - When empty/missing: uses global file index (searches entire webpDir)
  - Prevents ambiguity when multiple files share same name in different folders
- **Excluded Folders**: Defined in `excluded_folders.js` (Thumbs.db, .DS_Store, etc.)
- **File Naming**: Organized files renamed to `{groupBy_slug}_{identifier}.webp` to prevent collisions
