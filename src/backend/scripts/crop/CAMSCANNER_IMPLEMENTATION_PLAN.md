# CamScanner-like API Implementation Plan

## Overview

Create a clean, class-based API in `crop/camscanner/` that automatically detects document type and applies appropriate processing. The API will handle:
- Single documents (receipts, papers, ID cards)
- Full book spreads (both pages visible)
- Partial books (one page + lateral fold)

## Goals

- **Simple API**: `scanner = CamScanner(); result = scanner.scan(image)`
- **Auto-detection**: No manual document type selection
- **Graceful fallback**: Returns original if detection fails
- **Quality metrics**: Confidence scores for validation
- **Warnings**: Alerts for ambiguous cases

## Architecture

```
crop/camscanner/
├── __init__.py                  # Main API export
├── scanner.py                   # CamScanner class
├── detectors.py                 # Document type detection
├── processors.py                # Processing pipelines
├── utils.py                     # Shared utilities
├── fold_detection_hough.py      # Hough line fold detection
├── examples/                    # Usage examples
│   ├── example_single_doc.py
│   ├── example_book.py
│   └── example_partial_book.py
└── README.md                    # API documentation
```

## API Design

### Main Interface

```python
from camscanner import CamScanner

# Create scanner instance
scanner = CamScanner(
    debug=False,
    quality_threshold=0.6
)

# Process image (path or numpy array)
result = scanner.scan("image.jpg")

# Access results
processed = result.processed_image   # Main output
left_page = result.left_image         # For book spreads
right_page = result.right_image       # For book spreads
doc_type = result.document_type       # "single", "book_spread", etc.
confidence = result.confidence        # 0.0-1.0
warnings = result.warnings            # List of warning messages
```

### Result Object

```python
class ScanResult:
    processed_image: np.ndarray      # Main processed image
    left_image: np.ndarray | None    # Left page (books only)
    right_image: np.ndarray | None   # Right page (books only)
    document_type: str               # Document classification
    confidence: float                # Quality score 0.0-1.0
    warnings: List[str]              # Warning messages
    debug_info: dict                 # Detection details
    success: bool                    # True if processing succeeded
```

### Document Types

1. **"single"** - Single flat document (no folds)
2. **"book_spread"** - Full book with center fold (both pages visible)
3. **"partial_left"** - Left page + right fold to crop
4. **"partial_right"** - Right page + left fold to crop
5. **"unknown"** - Detection failed (returns original)

## Implementation Steps

### Step 1: Setup Directory Structure

**Files to create:**
```
camscanner/__init__.py
camscanner/scanner.py
camscanner/detectors.py
camscanner/processors.py
camscanner/utils.py
camscanner/fold_detection_hough.py
camscanner/examples/example_single_doc.py
camscanner/examples/example_book.py
camscanner/examples/example_partial_book.py
camscanner/README.md
```

**Actions:**
- Create directory structure
- Add empty files with docstrings
- Add MIT license header to each file

---

### Step 2: Implement Utils Module

**File:** `camscanner/utils.py`

**Purpose:** Bridge to existing codebase, provide shared utilities

**Components:**
```python
# Import wrappers for existing functionality
from contour_detector import find_page_contour, warp_image, preprocess_image
from fold_detection import detect_fold_brightness_profile
from image_io import load_image, save_image_with_metadata

# Utility functions
def normalize_image_input(image) -> np.ndarray
def calculate_aspect_ratio(contour) -> float
def estimate_rotation_angle(contour) -> float
def is_valid_contour(contour, img_shape) -> bool
```

**Estimated:** ~150 lines

---

### Step 3: Implement Hough Line Fold Detection

**File:** `camscanner/fold_detection_hough.py`

**Purpose:** Detect folds using vertical line detection (complements brightness method)

**Components:**
```python
def detect_fold_hough_lines(img, side="center", search_ratio=0.3) -> tuple:
    """
    Detect vertical lines using Hough transform.

    Returns:
        (fold_x_position, quality_score)
    """
    # 1. Convert to grayscale
    # 2. Define search region (left/right/center)
    # 3. Canny edge detection
    # 4. HoughLinesP for line detection
    # 5. Filter for vertical lines (angle < 15° from vertical)
    # 6. Cluster lines by x position
    # 7. Return strongest cluster position + quality

def detect_fold_combined(img, side="center") -> tuple:
    """
    Combine brightness + Hough methods, pick best result.

    Returns:
        (fold_x, quality, method_used)
    """
```

**Algorithm:**
- Search region based on expected fold location
- Detect lines with `cv2.HoughLinesP`
- Filter for near-vertical lines (±15° tolerance)
- Cluster lines by x position (within 2% of width)
- Quality score from: line count, length, angle consistency

**Estimated:** ~250 lines

---

### Step 4: Implement Document Type Detector

**File:** `camscanner/detectors.py`

**Purpose:** Classify input image into document types

**Components:**
```python
class DocumentTypeDetector:
    def detect(self, img: np.ndarray) -> tuple:
        """
        Classify document type.

        Returns:
            (document_type, confidence, metadata)
        """
        # 1. Detect page edges (4 corners)
        # 2. Detect fold lines (brightness + Hough)
        # 3. Classify based on fold position
        # 4. Calculate confidence score

    def _detect_page_boundary(self, img) -> tuple:
        """Edge detection → 4 corners"""

    def _detect_fold(self, img) -> tuple:
        """Combined fold detection"""

    def _classify_by_fold_position(self, fold_x, page_contour, img_width) -> str:
        """Determine document type from fold location"""
```

**Classification Logic:**

```python
# Calculate page coverage
page_width = get_page_width_from_contour(page_contour)
page_center_x = get_page_center_x(page_contour)

# No fold detected
if fold_x is None:
    return "single"

# Calculate fold position relative to page
fold_position_ratio = (fold_x - page_left) / page_width

if 0.4 <= fold_position_ratio <= 0.6:
    # Fold at page center
    if page_covers_full_image(page_contour, img.shape):
        return "book_spread"
    else:
        return "book_spread" + warning("Full book spread detected")

elif fold_position_ratio < 0.2:
    # Fold at left edge
    return "partial_left"

elif fold_position_ratio > 0.8:
    # Fold at right edge
    return "partial_right"

else:
    # Ambiguous
    return "unknown"
```

**Estimated:** ~300 lines

---

### Step 5: Implement Processing Pipelines

**File:** `camscanner/processors.py`

**Purpose:** Three specialized processing pipelines

**Components:**

```python
class DocumentProcessor:
    """Base processor with shared logic"""

    def __init__(self, config):
        self.contour_border = config.get('contour_border', 150)
        self.fold_border = config.get('fold_border', 150)
        self.quality_threshold = config.get('quality_threshold', 0.6)


class SingleDocumentProcessor(DocumentProcessor):
    def process(self, img: np.ndarray, page_contour) -> dict:
        """
        Process single flat document.

        Steps:
        1. Perspective correction (warp_image)
        2. Smart crop (irregolar_border)
        3. Return processed image
        """


class BookSpreadProcessor(DocumentProcessor):
    def process(self, img: np.ndarray, page_contour, fold_x) -> dict:
        """
        Process full book spread with center fold.

        Steps:
        1. Perspective correction
        2. Detect fold quality
        3. Split at fold (left/right)
        4. Check if both pages visible (warning)
        5. Return left + right images
        """


class PartialBookProcessor(DocumentProcessor):
    def process(self, img: np.ndarray, page_contour, fold_x, fold_side) -> dict:
        """
        Process partial book (page + lateral fold).

        Steps:
        1. Determine crop direction (keep page, remove other side)
        2. Crop to fold boundary
        3. Perspective correction on remaining area
        4. Return single processed page
        """
```

**Estimated:** ~400 lines

---

### Step 6: Implement Main CamScanner Class

**File:** `camscanner/scanner.py`

**Purpose:** Orchestrate detection and processing

**Components:**

```python
class CamScanner:
    def __init__(self, debug=False, quality_threshold=0.6, **config):
        """
        Initialize scanner with configuration.

        Args:
            debug: Enable debug visualizations
            quality_threshold: Minimum quality for fold detection
            **config: Additional configuration
        """
        self.debug = debug
        self.detector = DocumentTypeDetector(config)
        self.processors = {
            'single': SingleDocumentProcessor(config),
            'book_spread': BookSpreadProcessor(config),
            'partial_left': PartialBookProcessor(config),
            'partial_right': PartialBookProcessor(config)
        }

    def scan(self, image) -> ScanResult:
        """
        Process image with automatic document type detection.

        Args:
            image: File path, numpy array, or PIL Image

        Returns:
            ScanResult object with processed image(s)
        """
        try:
            # 1. Load and normalize input
            img = self._load_image(image)

            # 2. Detect document type
            doc_type, confidence, metadata = self.detector.detect(img)

            # 3. Route to appropriate processor
            processor = self.processors.get(doc_type)
            if processor is None:
                return self._create_fallback_result(img, doc_type)

            # 4. Process image
            result = processor.process(img, **metadata)

            # 5. Package result
            return self._create_result(img, result, doc_type, confidence)

        except Exception as e:
            if self.debug:
                raise
            return self._create_error_result(img, str(e))

    def _create_result(self, original, processed, doc_type, confidence) -> ScanResult:
        """Package processing results"""

    def _create_fallback_result(self, img, doc_type) -> ScanResult:
        """Return original image if processing failed"""

    def _create_error_result(self, img, error_msg) -> ScanResult:
        """Handle processing errors gracefully"""


class ScanResult:
    def __init__(self, **kwargs):
        self.processed_image = kwargs.get('processed_image')
        self.left_image = kwargs.get('left_image')
        self.right_image = kwargs.get('right_image')
        self.document_type = kwargs.get('document_type', 'unknown')
        self.confidence = kwargs.get('confidence', 0.0)
        self.warnings = kwargs.get('warnings', [])
        self.debug_info = kwargs.get('debug_info', {})
        self.success = kwargs.get('success', False)

    def save(self, output_path):
        """Save processed image(s) to disk"""

    def show(self):
        """Display result using matplotlib"""
```

**Estimated:** ~250 lines

---

### Step 7: Create API Export

**File:** `camscanner/__init__.py`

```python
"""
CamScanner-like Document Processing API

Simple, automatic document scanning with support for:
- Single flat documents
- Book spreads with center fold
- Partial books with lateral fold

Usage:
    from camscanner import CamScanner

    scanner = CamScanner()
    result = scanner.scan("document.jpg")

    if result.success:
        result.save("output.jpg")
"""

from .scanner import CamScanner, ScanResult

__version__ = "1.0.0"
__all__ = ["CamScanner", "ScanResult"]
```

**Estimated:** ~30 lines

---

### Step 8: Create Usage Examples

#### Example 1: Single Document
**File:** `camscanner/examples/example_single_doc.py`

```python
"""
Example: Process single flat document (receipt, ID card, paper)
"""
from camscanner import CamScanner

def main():
    # Create scanner
    scanner = CamScanner(debug=True)

    # Process image
    result = scanner.scan("receipt.jpg")

    # Check results
    print(f"Document type: {result.document_type}")
    print(f"Confidence: {result.confidence:.2f}")

    if result.success:
        result.save("receipt_scanned.jpg")
        print("Success!")
    else:
        print("Processing failed, using fallback")

if __name__ == "__main__":
    main()
```

#### Example 2: Book Spread
**File:** `camscanner/examples/example_book.py`

```python
"""
Example: Process book spread with center fold
"""
from camscanner import CamScanner

def main():
    scanner = CamScanner()
    result = scanner.scan("book_spread.jpg")

    if result.document_type == "book_spread":
        # Save both pages
        if result.left_image is not None:
            cv2.imwrite("page_left.jpg", result.left_image)
        if result.right_image is not None:
            cv2.imwrite("page_right.jpg", result.right_image)

        # Check for warnings
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

if __name__ == "__main__":
    main()
```

#### Example 3: Partial Book
**File:** `camscanner/examples/example_partial_book.py`

```python
"""
Example: Process partial book (one page + lateral fold)
"""
from camscanner import CamScanner

def main():
    scanner = CamScanner(quality_threshold=0.5)
    result = scanner.scan("partial_page.jpg")

    print(f"Detected: {result.document_type}")

    if result.document_type in ["partial_left", "partial_right"]:
        print(f"Fold on {result.document_type.split('_')[1]} side")
        result.save("page_cropped.jpg")

if __name__ == "__main__":
    main()
```

**Estimated:** ~150 lines total

---

### Step 9: Create Documentation

**File:** `camscanner/README.md`

**Contents:**
- API overview and features
- Installation (none required, uses existing deps)
- Quick start guide
- API reference (CamScanner class, ScanResult)
- Document type descriptions
- Configuration options
- Troubleshooting guide

**Estimated:** ~200 lines

---

## Testing Strategy

### Manual Testing
1. **Single documents**: Test with receipts, papers, ID cards
2. **Book spreads**: Test with open books (both pages visible)
3. **Partial books**: Test with one page + fold edge
4. **Edge cases**: Tilted documents, poor lighting, shadows

### Test Images Needed
- `test_receipt.jpg` - Single document
- `test_book_spread.jpg` - Full book
- `test_partial_left.jpg` - Page with right fold
- `test_partial_right.jpg` - Page with left fold
- `test_rotated.jpg` - Tilted document

---

## Development Workflow

### Phase 1: Foundation (Steps 1-2)
- Create directory structure
- Implement utils module
- Test imports from parent modules

### Phase 2: Detection (Steps 3-4)
- Implement Hough fold detection
- Implement document type classifier
- Test detection on sample images

### Phase 3: Processing (Step 5)
- Implement three processors
- Test each pipeline independently
- Verify output quality

### Phase 4: Integration (Steps 6-7)
- Implement CamScanner class
- Create API exports
- End-to-end testing

### Phase 5: Documentation (Steps 8-9)
- Create usage examples
- Write README
- Add inline documentation

---

## Estimated Effort

### Lines of Code
- `utils.py`: ~150 lines
- `fold_detection_hough.py`: ~250 lines
- `detectors.py`: ~300 lines
- `processors.py`: ~400 lines
- `scanner.py`: ~250 lines
- `__init__.py`: ~30 lines
- Examples: ~150 lines
- README: ~200 lines

**Total: ~1,730 lines**

### Time Estimate
- Phase 1: 1 hour
- Phase 2: 3 hours
- Phase 3: 4 hours
- Phase 4: 2 hours
- Phase 5: 1 hour

**Total: ~11 hours**

---

## Success Criteria

✅ API works with single function call: `scanner.scan(image)`
✅ Auto-detects document type without user input
✅ Returns original image if detection fails (no data loss)
✅ Provides confidence scores for validation
✅ Handles all three document types correctly
✅ Generates warnings for ambiguous cases
✅ Clean, documented code with examples
✅ No dependencies beyond existing codebase

---

## Future Enhancements (Out of Scope)

- Batch processing multiple images
- OCR integration
- PDF output support
- Real-time video processing
- Mobile app integration
- Cloud API deployment
