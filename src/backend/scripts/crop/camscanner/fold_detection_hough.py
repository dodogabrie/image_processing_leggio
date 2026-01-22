"""
Fold detection using Hough Line Transform.

Alternative to brightness-based detection for cases where book spine
is not significantly darker than pages (e.g., light-colored books).

Detects strong vertical lines that may indicate book fold or page edge.
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict


def detect_fold_hough_lines(
    img: np.ndarray,
    side: str = "center",
    search_ratio: float = 0.3,
    min_line_length: Optional[int] = None,
    debug: bool = False
) -> Tuple[Optional[int], float]:
    """
    Detect book fold/spine using Hough Line Transform for vertical lines.

    Args:
        img: Input image (BGR or grayscale)
        side: Expected fold location - 'left', 'right', or 'center'
        search_ratio: Fraction of image width to search (0.3 = middle 30%)
        min_line_length: Minimum line length in pixels (None = auto from height)
        debug: Print debug information

    Returns:
        tuple: (fold_x_position, quality_score)
            - fold_x_position: X coordinate of detected fold (None if not found)
            - quality_score: Confidence 0.0-1.0 (based on line strength)
    """
    h, w = img.shape[:2]

    # Convert to grayscale if needed
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # Define search region based on expected fold location
    if side == "left":
        x_start, x_end = 0, int(w * 0.33)
    elif side == "right":
        x_start, x_end = int(w * 0.67), w
    else:  # center
        center = w // 2
        search_width = int(w * search_ratio / 2)
        x_start = max(0, center - search_width)
        x_end = min(w, center + search_width)

    # Extract search region
    search_region = gray[:, x_start:x_end]

    if debug:
        print(f"[Hough] Image size: {w}x{h}")
        print(f"[Hough] Search region: x={x_start} to x={x_end} (width={x_end-x_start})")

    # Edge detection (stronger edges for line detection)
    edges = cv2.Canny(search_region, 50, 150, apertureSize=3)

    # Auto-calculate min_line_length if not provided
    if min_line_length is None:
        min_line_length = int(h * 0.4)  # Line must span at least 40% of height

    # Detect lines using probabilistic Hough transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,              # Distance resolution in pixels
        theta=np.pi/180,    # Angular resolution in radians
        threshold=80,       # Minimum votes to be considered a line
        minLineLength=min_line_length,
        maxLineGap=h//10    # Max gap between segments to treat as single line
    )

    if lines is None or len(lines) == 0:
        if debug:
            print("[Hough] No lines detected")
        return None, 0.0

    # Filter for vertical lines (angle close to 90 degrees)
    vertical_lines = []
    angle_threshold = 15  # degrees from vertical

    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Calculate angle from vertical (0 = perfectly vertical)
        if x2 - x1 == 0:
            angle = 0  # Perfectly vertical
        else:
            angle = abs(90 - abs(np.degrees(np.arctan2(y2 - y1, x2 - x1))))

        # Keep only near-vertical lines
        if angle <= angle_threshold:
            # Calculate line strength (length and straightness)
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            x_pos = (x1 + x2) / 2  # Average x position

            vertical_lines.append({
                'x': x_pos,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'length': length,
                'angle': angle
            })

    if len(vertical_lines) == 0:
        if debug:
            print(f"[Hough] Found {len(lines)} lines but none vertical (within {angle_threshold}°)")
        return None, 0.0

    if debug:
        print(f"[Hough] Found {len(vertical_lines)} vertical lines from {len(lines)} total")

    # Cluster vertical lines by x position (lines close together = same spine)
    cluster_threshold = w * 0.02  # 2% of width
    clusters = _cluster_lines_by_position(vertical_lines, cluster_threshold)

    if debug:
        print(f"[Hough] Clustered into {len(clusters)} groups")

    # Find strongest cluster (most lines + longest combined length)
    best_cluster = max(
        clusters,
        key=lambda c: len(c) + sum(l['length'] for l in c) / 1000
    )

    # Calculate fold position as weighted average (weight by length)
    total_weight = sum(l['length'] for l in best_cluster)
    fold_x_relative = sum(l['x'] * l['length'] for l in best_cluster) / total_weight

    # Convert back to full image coordinates
    fold_x = int(fold_x_relative + x_start)

    # Calculate quality score
    quality = _calculate_line_quality(best_cluster, h, angle_threshold)

    if debug:
        num_lines = len(best_cluster)
        avg_length = sum(l['length'] for l in best_cluster) / num_lines
        avg_angle = sum(l['angle'] for l in best_cluster) / num_lines
        print(f"[Hough] Best cluster: {num_lines} lines, avg_length={avg_length:.1f}px, avg_angle={avg_angle:.2f}°")
        print(f"[Hough] Fold detected at x={fold_x}, quality={quality:.3f}")

    return fold_x, quality


def _cluster_lines_by_position(lines: List[Dict], threshold: float) -> List[List[Dict]]:
    """
    Cluster lines by x position.

    Args:
        lines: List of line dictionaries with 'x' key
        threshold: Maximum distance for same cluster

    Returns:
        List of clusters (each cluster is a list of lines)
    """
    clusters = []

    for line in sorted(lines, key=lambda x: x['x']):
        placed = False
        for cluster in clusters:
            # Check if line belongs to existing cluster
            cluster_center = np.mean([l['x'] for l in cluster])
            if abs(line['x'] - cluster_center) <= threshold:
                cluster.append(line)
                placed = True
                break

        if not placed:
            clusters.append([line])

    return clusters


def _calculate_line_quality(cluster: List[Dict], img_height: int, angle_threshold: float) -> float:
    """
    Calculate quality score for a cluster of lines.

    Based on: number of lines, average length, angle consistency.

    Args:
        cluster: List of line dictionaries
        img_height: Image height for normalization
        angle_threshold: Maximum angle deviation

    Returns:
        float: Quality score 0.0-1.0
    """
    num_lines = len(cluster)
    avg_length = sum(l['length'] for l in cluster) / num_lines
    avg_angle = sum(l['angle'] for l in cluster) / num_lines

    # Quality components (0-1 each)
    q_count = min(num_lines / 5, 1.0)  # More lines = more confident
    q_length = min(avg_length / img_height, 1.0)  # Longer lines = more confident
    q_angle = 1.0 - (avg_angle / angle_threshold)  # Closer to vertical = more confident

    # Weighted combination
    quality = (q_count * 0.4 + q_length * 0.4 + q_angle * 0.2)

    return quality


def detect_fold_combined(
    img: np.ndarray,
    side: str = "center",
    debug: bool = False
) -> Tuple[Optional[int], float, str]:
    """
    Combine brightness-based and Hough-based fold detection.

    Tries both methods and returns the best result based on quality scores.

    Args:
        img: Input image
        side: Expected fold location
        debug: Print debug info

    Returns:
        tuple: (fold_x, quality, method_used)
            - fold_x: X coordinate of detected fold (None if not found)
            - quality: Best quality score 0.0-1.0
            - method_used: "brightness", "hough", or "none"
    """
    # Import here to avoid circular dependency
    from .utils import detect_fold_brightness

    if debug:
        print("\n[Combined] Running both fold detection methods...")

    # Try brightness-based detection
    fold_brightness, quality_brightness = detect_fold_brightness(img, side=side, debug=debug)

    # Try Hough-based detection
    fold_hough, quality_hough = detect_fold_hough_lines(img, side=side, debug=debug)

    # Pick best result
    if fold_brightness is None and fold_hough is None:
        if debug:
            print("[Combined] Both methods failed")
        return None, 0.0, "none"

    elif fold_brightness is None:
        if debug:
            print(f"[Combined] Using Hough result (quality={quality_hough:.3f})")
        return fold_hough, quality_hough, "hough"

    elif fold_hough is None:
        if debug:
            print(f"[Combined] Using brightness result (quality={quality_brightness:.3f})")
        return fold_brightness, quality_brightness, "brightness"

    else:
        # Both detected - pick higher quality
        if quality_brightness > quality_hough:
            if debug:
                print(f"[Combined] Brightness better ({quality_brightness:.3f} vs {quality_hough:.3f})")
            return fold_brightness, quality_brightness, "brightness"
        else:
            if debug:
                print(f"[Combined] Hough better ({quality_hough:.3f} vs {quality_brightness:.3f})")
            return fold_hough, quality_hough, "hough"


if __name__ == "__main__":
    """Test Hough fold detection on sample image."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fold_detection_hough.py <image_path> [--debug]")
        sys.exit(1)

    img_path = sys.argv[1]
    debug = "--debug" in sys.argv

    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load image {img_path}")
        sys.exit(1)

    print(f"Testing Hough fold detection on: {img_path}")
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")

    # Test Hough detection
    print("\n=== Hough Detection ===")
    fold_x, quality = detect_fold_hough_lines(img, side="center", debug=True)

    if fold_x is not None:
        print(f"\nFold detected at x={fold_x} (quality={quality:.3f})")

        # Draw result
        vis = img.copy()
        h = vis.shape[0]
        cv2.line(vis, (fold_x, 0), (fold_x, h), (0, 255, 0), 3)
        cv2.putText(vis, f"Hough: x={fold_x}", (fold_x+10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        output_path = "fold_detection_hough_result.jpg"
        cv2.imwrite(output_path, vis)
        print(f"Visualization saved to: {output_path}")
    else:
        print("\nNo fold detected")

    # Test combined detection
    print("\n=== Combined Detection ===")
    fold_x, quality, method = detect_fold_combined(img, side="center", debug=True)

    if fold_x is not None:
        print(f"\nBest result: x={fold_x} (quality={quality:.3f}, method={method})")
    else:
        print("\nNo fold detected by any method")
