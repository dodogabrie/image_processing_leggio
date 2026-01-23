"""
Plot gradients with matplotlib to debug edge detection
"""

import argparse
import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks


def plot_gradient_analysis(image_path, threshold=30):
    """
    Create detailed matplotlib plots showing gradient analysis.
    """
    # Load image
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    print(f"Image size: {width}x{height}")
    print(f"Threshold: {threshold}")

    # Create figure with multiple subplots
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle(f'Gradient Analysis: {image_path}', fontsize=14, fontweight='bold')

    # ====================
    # TOP EDGE ANALYSIS
    # ====================
    ax_top = axes[0, 0]
    ax_top.set_title('TOP Edge Detection (scan from top downward)', fontweight='bold')
    ax_top.set_xlabel('Y position (pixels from top)')
    ax_top.set_ylabel('Gradient magnitude')

    # Sample 5 vertical scanlines from top
    x_positions = np.linspace(width * 0.2, width * 0.8, 5, dtype=int)

    for i, x in enumerate(x_positions):
        scanline = gray[:, x]
        gradient = np.abs(np.diff(scanline))

        # Find peaks
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold*0.3)

        # Plot gradient
        ax_top.plot(gradient, alpha=0.7, label=f'x={x}', linewidth=2)

        # Mark peaks
        if len(peaks) > 0:
            ax_top.scatter(peaks, gradient[peaks], s=100, zorder=10, marker='o')
            # Annotate first peak
            first_peak = peaks[0]
            ax_top.annotate(f'1st peak\ny={first_peak}',
                           (first_peak, gradient[first_peak]),
                           xytext=(10, 20), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    ax_top.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold={threshold}')
    ax_top.legend(fontsize=8)
    ax_top.grid(True, alpha=0.3)

    # ====================
    # BOTTOM EDGE ANALYSIS
    # ====================
    ax_bottom = axes[0, 1]
    ax_bottom.set_title('BOTTOM Edge Detection (scan from top, take last peak)', fontweight='bold')
    ax_bottom.set_xlabel('Y position (pixels from top)')
    ax_bottom.set_ylabel('Gradient magnitude')

    for i, x in enumerate(x_positions):
        scanline = gray[:, x]
        gradient = np.abs(np.diff(scanline))
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold*0.3)

        ax_bottom.plot(gradient, alpha=0.7, label=f'x={x}', linewidth=2)

        if len(peaks) > 0:
            ax_bottom.scatter(peaks, gradient[peaks], s=100, zorder=10, marker='o')
            # Annotate last peak
            last_peak = peaks[-1]
            ax_bottom.annotate(f'Last peak\ny={last_peak}',
                              (last_peak, gradient[last_peak]),
                              xytext=(10, 20), textcoords='offset points',
                              bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                              arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    ax_bottom.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold={threshold}')
    ax_bottom.legend(fontsize=8)
    ax_bottom.grid(True, alpha=0.3)

    # ====================
    # LEFT EDGE ANALYSIS
    # ====================
    ax_left = axes[1, 0]
    ax_left.set_title('LEFT Edge Detection (scan from left rightward)', fontweight='bold')
    ax_left.set_xlabel('X position (pixels from left)')
    ax_left.set_ylabel('Gradient magnitude')

    y_positions = np.linspace(height * 0.2, height * 0.8, 5, dtype=int)

    for i, y in enumerate(y_positions):
        scanline = gray[y, :]
        gradient = np.abs(np.diff(scanline))
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold*0.3)

        ax_left.plot(gradient, alpha=0.7, label=f'y={y}', linewidth=2)

        if len(peaks) > 0:
            ax_left.scatter(peaks, gradient[peaks], s=100, zorder=10, marker='o')
            first_peak = peaks[0]
            ax_left.annotate(f'1st peak\nx={first_peak}',
                            (first_peak, gradient[first_peak]),
                            xytext=(10, 20), textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    ax_left.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold={threshold}')
    ax_left.legend(fontsize=8)
    ax_left.grid(True, alpha=0.3)

    # ====================
    # RIGHT EDGE ANALYSIS
    # ====================
    ax_right = axes[1, 1]
    ax_right.set_title('RIGHT Edge Detection (scan from left, take last peak)', fontweight='bold')
    ax_right.set_xlabel('X position (pixels from left)')
    ax_right.set_ylabel('Gradient magnitude')

    for i, y in enumerate(y_positions):
        scanline = gray[y, :]
        gradient = np.abs(np.diff(scanline))
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold*0.3)

        ax_right.plot(gradient, alpha=0.7, label=f'y={y}', linewidth=2)

        if len(peaks) > 0:
            ax_right.scatter(peaks, gradient[peaks], s=100, zorder=10, marker='o')
            last_peak = peaks[-1]
            ax_right.annotate(f'Last peak\nx={last_peak}',
                             (last_peak, gradient[last_peak]),
                             xytext=(10, 20), textcoords='offset points',
                             bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                             arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    ax_right.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold={threshold}')
    ax_right.legend(fontsize=8)
    ax_right.grid(True, alpha=0.3)

    # ====================
    # GRADIENT STATISTICS
    # ====================
    ax_stats = axes[2, 0]
    ax_stats.set_title('Gradient Histogram (entire image)', fontweight='bold')
    ax_stats.set_xlabel('Gradient magnitude')
    ax_stats.set_ylabel('Frequency (log scale)')

    # Compute all gradients
    all_gradients = []
    for y in range(0, height, 10):  # Sample every 10 rows
        scanline = gray[y, :]
        grad = np.abs(np.diff(scanline))
        all_gradients.extend(grad)

    all_gradients = np.array(all_gradients)

    # Plot histogram
    ax_stats.hist(all_gradients, bins=100, alpha=0.7, edgecolor='black', log=True)
    ax_stats.axvline(x=threshold, color='red', linestyle='--', linewidth=3, label=f'Current threshold={threshold}')

    # Calculate percentiles
    p50 = np.percentile(all_gradients, 50)
    p75 = np.percentile(all_gradients, 75)
    p90 = np.percentile(all_gradients, 90)
    p95 = np.percentile(all_gradients, 95)

    ax_stats.axvline(x=p50, color='green', linestyle=':', linewidth=2, label=f'50th percentile={p50:.1f}')
    ax_stats.axvline(x=p75, color='orange', linestyle=':', linewidth=2, label=f'75th percentile={p75:.1f}')
    ax_stats.axvline(x=p90, color='purple', linestyle=':', linewidth=2, label=f'90th percentile={p90:.1f}')
    ax_stats.axvline(x=p95, color='brown', linestyle=':', linewidth=2, label=f'95th percentile={p95:.1f}')

    ax_stats.legend(fontsize=9)
    ax_stats.grid(True, alpha=0.3)

    # ====================
    # IMAGE PREVIEW
    # ====================
    ax_image = axes[2, 1]
    ax_image.set_title('Original Image (grayscale)', fontweight='bold')
    ax_image.imshow(gray, cmap='gray')
    ax_image.axis('off')

    # Draw scanline positions
    for x in x_positions:
        ax_image.axvline(x=x, color='cyan', alpha=0.5, linewidth=1)
    for y in y_positions:
        ax_image.axhline(y=y, color='cyan', alpha=0.5, linewidth=1)

    plt.tight_layout()

    # Print statistics
    print("\n" + "="*60)
    print("GRADIENT STATISTICS")
    print("="*60)
    print(f"Median gradient:      {p50:.1f}")
    print(f"75th percentile:      {p75:.1f}")
    print(f"90th percentile:      {p90:.1f}")
    print(f"95th percentile:      {p95:.1f}")
    print(f"Current threshold:    {threshold:.1f}")
    print("="*60)
    print(f"\n💡 RECOMMENDATION:")
    suggested = max(p75, 10)  # At least 10
    print(f"   Try threshold between {p75:.0f} and {p90:.0f}")
    print(f"   Suggested starting point: {suggested:.0f}")
    print("="*60)

    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Plot gradient analysis with matplotlib')
    parser.add_argument('image', help='Path to input image')
    parser.add_argument('--threshold', type=float, default=30,
                       help='Gradient threshold (default: 30)')

    args = parser.parse_args()

    plot_gradient_analysis(args.image, args.threshold)


if __name__ == '__main__':
    main()
