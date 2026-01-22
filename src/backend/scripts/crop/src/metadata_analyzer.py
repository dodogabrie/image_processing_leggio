"""
metadata_analyzer.py

Document Metadata Analysis and Format Detection
==============================================

This module analyzes document images to extract metadata information such as
format detection (A4, Letter, etc.), orientation, content analysis, and quality
assessment. It provides the foundation for preprocessing decisions.

Key Features:
- Page format detection (A4, Letter, Legal, etc.)
- Orientation analysis (portrait/landscape)
- Content density analysis
- Fold presence detection
- Quality assessment metrics
- Document type classification

Author: [Generated Documentation]
Version: 1.0
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List
from enum import Enum
from PIL import Image


class PageFormat(Enum):
    """Standard page format enumeration."""
    A4 = "A4"
    A3 = "A3"
    A5 = "A5"
    LETTER = "Letter"
    LEGAL = "Legal"
    TABLOID = "Tabloid"
    UNKNOWN = "Unknown"


class Orientation(Enum):
    """Page orientation enumeration."""
    PORTRAIT = "Portrait"
    LANDSCAPE = "Landscape"
    SQUARE = "Square"


# Standard page dimensions in centimeters
PAGE_FORMATS = {
    PageFormat.A4: {
        "portrait_cm": (21.0, 29.7),
        "landscape_cm": (29.7, 21.0),
        "ratio": 1.414,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0  # 1cm tolerance for size matching
    },
    PageFormat.A3: {
        "portrait_cm": (29.7, 42.0),
        "landscape_cm": (42.0, 29.7),
        "ratio": 1.414,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0
    },
    PageFormat.A5: {
        "portrait_cm": (14.8, 21.0),
        "landscape_cm": (21.0, 14.8),
        "ratio": 1.414,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0
    },
    PageFormat.LETTER: {
        "portrait_cm": (21.6, 27.9),
        "landscape_cm": (27.9, 21.6),
        "ratio": 1.294,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0
    },
    PageFormat.LEGAL: {
        "portrait_cm": (21.6, 35.6),
        "landscape_cm": (35.6, 21.6),
        "ratio": 1.647,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0
    },
    PageFormat.TABLOID: {
        "portrait_cm": (27.9, 43.2),
        "landscape_cm": (43.2, 27.9),
        "ratio": 1.545,
        "tolerance_ratio": 0.05,
        "tolerance_size_cm": 1.0
    }
}


def get_image_dpi(image_path: str) -> Tuple[float, float]:
    """Extract DPI from image metadata."""
    try:
        with Image.open(image_path) as img:
            dpi = img.info.get('dpi', (300, 300))  # Default to 300 DPI if not found
            return dpi
    except:
        return (300, 300)  # Fallback to 300 DPI

def pixels_to_cm(pixels: int, dpi: float) -> float:
    """Convert pixels to centimeters using DPI."""
    inches = pixels / dpi
    return inches * 2.54

def detect_page_format(width: int, height: int, image_path: Optional[str] = None) -> Tuple[PageFormat, Orientation, float]:
    """
    Detect page format based on A4 proportions (aspect ratio).

    Args:
        width (int): Page width in pixels
        height (int): Page height in pixels
        image_path (Optional[str]): Unused, kept for compatibility

    Returns:
        Tuple[PageFormat, Orientation, float]: Detected format, orientation, and confidence
    """
    # Calculate aspect ratio
    aspect_ratio = max(width, height) / min(width, height)
    orientation = Orientation.PORTRAIT if height > width else (
        Orientation.LANDSCAPE if width > height else Orientation.SQUARE
    )

    best_match = PageFormat.UNKNOWN
    best_confidence = 0.0

    # Check against known formats using aspect ratio only
    for page_format, specs in PAGE_FORMATS.items():
        expected_ratio = specs["ratio"]
        tolerance_ratio = specs["tolerance_ratio"]

        # A4 can only be portrait - skip A4 for landscape orientation
        if page_format == PageFormat.A4 and orientation == Orientation.LANDSCAPE:
            continue

        # Check ratio similarity
        ratio_diff = abs(aspect_ratio - expected_ratio) / expected_ratio
        if ratio_diff <= tolerance_ratio:
            confidence = 1.0 - (ratio_diff / tolerance_ratio)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = page_format

    return best_match, orientation, best_confidence


def analyze_content_density(img: np.ndarray, page_boundaries: Optional[Tuple[int, int]] = None) -> Dict:
    """
    Analyze content density within the document.

    Args:
        img (np.ndarray): Input BGR image
        page_boundaries (Optional[Tuple[int, int]]): Page boundaries (start, end)

    Returns:
        Dict: Content density analysis including text coverage, white space, etc.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Use page boundaries if provided, otherwise use full image
    if page_boundaries:
        start_x, end_x = page_boundaries
        analysis_region = gray[:, start_x:end_x]
    else:
        analysis_region = gray

    h, w = analysis_region.shape

    # Calculate basic statistics
    mean_brightness = np.mean(analysis_region)
    std_brightness = np.std(analysis_region)

    # Estimate text coverage using adaptive thresholding
    adaptive_thresh = cv2.adaptiveThreshold(
        analysis_region, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    # Calculate content metrics
    total_pixels = h * w
    dark_pixels = np.sum(adaptive_thresh == 0)  # Assuming text is dark
    content_coverage = dark_pixels / total_pixels

    # Estimate white space
    white_threshold = mean_brightness + 0.5 * std_brightness
    white_pixels = np.sum(analysis_region > white_threshold)
    white_space_ratio = white_pixels / total_pixels

    # Content density classification
    if content_coverage > 0.3:
        density_class = "DENSE"
    elif content_coverage > 0.15:
        density_class = "MODERATE"
    elif content_coverage > 0.05:
        density_class = "SPARSE"
    else:
        density_class = "MINIMAL"

    return {
        "content_coverage": content_coverage,
        "white_space_ratio": white_space_ratio,
        "mean_brightness": mean_brightness,
        "brightness_std": std_brightness,
        "density_class": density_class,
        "analysis_area": (w, h),
        "estimated_text_pixels": int(dark_pixels)
    }


def detect_fold_presence(img: np.ndarray, page_boundaries: Optional[Tuple[int, int]] = None) -> Dict:
    """
    Analyze whether the document likely contains a fold.

    This function performs preliminary analysis to determine if fold detection
    should be applied to the document.

    Args:
        img (np.ndarray): Input BGR image
        page_boundaries (Optional[Tuple[int, int]]): Page boundaries for analysis

    Returns:
        Dict: Fold presence analysis results
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Use page boundaries if provided
    if page_boundaries:
        start_x, end_x = page_boundaries
        analysis_region = gray[:, start_x:end_x]
        width_offset = start_x
    else:
        analysis_region = gray
        width_offset = 0

    h, w = analysis_region.shape

    # Look for vertical discontinuities that might indicate folds
    # Calculate horizontal brightness profile
    horizontal_profile = np.mean(analysis_region, axis=0)

    # Look for significant dips in brightness (potential fold lines)
    smoothed_profile = cv2.GaussianBlur(horizontal_profile.reshape(1, -1), (21, 1), 0).flatten()
    profile_std = np.std(smoothed_profile)
    profile_mean = np.mean(smoothed_profile)

    # Find significant dips
    dip_threshold = profile_mean - 1.5 * profile_std
    potential_folds = np.where(smoothed_profile < dip_threshold)[0]

    # Calculate fold likelihood based on various factors
    fold_indicators = []

    # 1. Presence of significant brightness dips
    if len(potential_folds) > 0:
        fold_indicators.append(("brightness_dips", len(potential_folds), 0.3))

    # 2. Document width suggests double-page spread
    aspect_ratio = w / h
    if aspect_ratio > 1.5:  # Wide documents more likely to have folds
        fold_indicators.append(("wide_aspect", aspect_ratio, 0.4))

    # 3. Brightness variance suggests multiple pages
    brightness_variance = np.var(horizontal_profile)
    if brightness_variance > profile_mean * 0.1:
        fold_indicators.append(("brightness_variance", brightness_variance, 0.2))

    # 4. Look for symmetrical patterns (double-page spreads)
    left_half = horizontal_profile[:w//2]
    right_half = horizontal_profile[w//2:]
    if len(right_half) == len(left_half):
        correlation = np.corrcoef(left_half, right_half[::-1])[0, 1]  # Reverse right for comparison
        if correlation > 0.7:
            fold_indicators.append(("symmetry", correlation, 0.3))

    # Calculate overall fold likelihood
    total_confidence = sum(weight for _, _, weight in fold_indicators)
    fold_likelihood = min(total_confidence, 1.0)

    # Determine recommendation
    if fold_likelihood > 0.7:
        recommendation = "STRONGLY_RECOMMENDED"
    elif fold_likelihood > 0.4:
        recommendation = "RECOMMENDED"
    elif fold_likelihood > 0.2:
        recommendation = "POSSIBLE"
    else:
        recommendation = "UNLIKELY"

    return {
        "fold_likelihood": fold_likelihood,
        "recommendation": recommendation,
        "indicators": fold_indicators,
        "potential_fold_positions": [pos + width_offset for pos in potential_folds],
        "analysis_width": w,
        "brightness_profile": horizontal_profile
    }


def assess_image_quality(img: np.ndarray) -> Dict:
    """
    Assess overall image quality for processing.

    Args:
        img (np.ndarray): Input BGR image

    Returns:
        Dict: Quality assessment metrics
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 1. Resolution assessment
    total_pixels = h * w
    if total_pixels > 8_000_000:  # > 8MP
        resolution_quality = "EXCELLENT"
    elif total_pixels > 3_000_000:  # > 3MP
        resolution_quality = "GOOD"
    elif total_pixels > 1_000_000:  # > 1MP
        resolution_quality = "FAIR"
    else:
        resolution_quality = "POOR"

    # 2. Sharpness assessment using Laplacian variance
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var > 500:
        sharpness_quality = "EXCELLENT"
    elif laplacian_var > 200:
        sharpness_quality = "GOOD"
    elif laplacian_var > 50:
        sharpness_quality = "FAIR"
    else:
        sharpness_quality = "POOR"

    # 3. Contrast assessment
    contrast = np.std(gray)
    if contrast > 60:
        contrast_quality = "EXCELLENT"
    elif contrast > 40:
        contrast_quality = "GOOD"
    elif contrast > 25:
        contrast_quality = "FAIR"
    else:
        contrast_quality = "POOR"

    # 4. Overall quality score
    quality_scores = {
        "EXCELLENT": 4,
        "GOOD": 3,
        "FAIR": 2,
        "POOR": 1
    }

    avg_score = (
        quality_scores[resolution_quality] +
        quality_scores[sharpness_quality] +
        quality_scores[contrast_quality]
    ) / 3

    if avg_score >= 3.5:
        overall_quality = "EXCELLENT"
    elif avg_score >= 2.5:
        overall_quality = "GOOD"
    elif avg_score >= 1.5:
        overall_quality = "FAIR"
    else:
        overall_quality = "POOR"

    return {
        "overall_quality": overall_quality,
        "resolution_quality": resolution_quality,
        "sharpness_quality": sharpness_quality,
        "contrast_quality": contrast_quality,
        "metrics": {
            "resolution_mp": total_pixels / 1_000_000,
            "laplacian_variance": laplacian_var,
            "contrast_std": contrast,
            "dimensions": (w, h)
        }
    }


def analyze_document_metadata(img: np.ndarray, page_boundaries: Optional[Tuple[int, int]] = None, image_path: Optional[str] = None) -> Dict:
    """
    Comprehensive document metadata analysis.

    This is the main entry point that combines all analysis functions to provide
    complete document metadata.

    Args:
        img (np.ndarray): Input BGR image
        page_boundaries (Optional[Tuple[int, int]]): Page boundaries if available
        image_path (Optional[str]): Path to image for DPI extraction

    Returns:
        Dict: Complete metadata analysis results
    """
    h, w = img.shape[:2]

    # 1. Format detection using overall image dimensions
    page_format, orientation, format_confidence = detect_page_format(w, h, image_path)

    # 2. Use full image dimensions for format detection (consistent approach)
    document_format = page_format
    document_orientation = orientation
    document_confidence = format_confidence

    # 3. Content analysis
    content_analysis = analyze_content_density(img, page_boundaries)

    # 4. Fold presence detection
    fold_analysis = detect_fold_presence(img, page_boundaries)

    # 5. Quality assessment
    quality_analysis = assess_image_quality(img)

    # 6. Skip DPI analysis - using proportions only

    # 7. Determine format types using document boundaries
    is_a4 = document_format == PageFormat.A4 and document_confidence > 0.7
    is_a3 = document_format == PageFormat.A3 and document_confidence > 0.7
    is_a3_landscape = document_format == PageFormat.A3 and document_orientation == Orientation.LANDSCAPE and document_confidence > 0.7

    # 8. Processing recommendations
    recommendations = []

    # Recommend fold detection for:
    # - A3 landscape (double-page spreads)
    # - Non-A4 formats with high fold likelihood
    if (is_a3_landscape or
        (not is_a4 and fold_analysis["recommendation"] in ["STRONGLY_RECOMMENDED", "RECOMMENDED"])):
        recommendations.append("APPLY_FOLD_DETECTION")

    if quality_analysis["overall_quality"] in ["POOR", "FAIR"]:
        recommendations.append("ENHANCE_IMAGE_QUALITY")

    if content_analysis["density_class"] == "MINIMAL":
        recommendations.append("CHECK_SCAN_QUALITY")

    if not is_a4 and document_confidence < 0.7:
        recommendations.append("VERIFY_PAGE_FORMAT")

    result = {
        "page_format": document_format.value,
        "orientation": document_orientation.value,
        "format_confidence": document_confidence,
        "is_a4": is_a4,
        "is_a3": is_a3,
        "dimensions": (w, h),
        "document_boundaries": page_boundaries,
        "document_dimensions": (w, h),
        "content_analysis": content_analysis,
        "fold_analysis": fold_analysis,
        "quality_analysis": quality_analysis,
        "recommendations": recommendations,
        "processing_suitable": quality_analysis["overall_quality"] in ["GOOD", "EXCELLENT"],
        "fold_detection_recommended": (is_a3_landscape or
                                       (not is_a4 and fold_analysis["recommendation"] in ["STRONGLY_RECOMMENDED", "RECOMMENDED"]))
    }

    return result