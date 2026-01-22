"""
fold_debug_simple.py

Simplified debug and visualization functions for fold_detection.py.
Contains plotting functions focused on parabolic method only.
"""

import matplotlib.pyplot as plt
import numpy as np
import os


def save_fold_profile_debug(filtered_profiles, mean_profile, std_profile, x_axis, x_final, roi, debug_dir, accumulated_std_profile=None, detection_method=None, second_derivative=None):
    """Simple fold profile visualization using parabolic method."""
    os.makedirs(debug_dir, exist_ok=True)

    # Create enhanced plot if we have accumulated std profile
    if accumulated_std_profile is not None:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Panel 1: Traditional profile analysis
        for prof in filtered_profiles:
            ax1.plot(x_axis, prof, alpha=0.3, color="gray", linewidth=0.5)
        ax1.plot(x_axis, mean_profile, "r-", linewidth=2, label="Mean Profile")
        ax1.fill_between(x_axis, mean_profile - std_profile, mean_profile + std_profile,
                        color="red", alpha=0.2, label="+/- 1 sigma Uncertainty")
        ax1.axvline(x_final, color="blue", linestyle="--", linewidth=2, label=f"Final Fold @ {x_final}")
        ax1.set_title(f"Profile Analysis ({len(filtered_profiles)} samples)")
        ax1.set_xlabel("X Position (pixels)")
        ax1.set_ylabel("Brightness")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Panel 2: Accumulated std profile with second derivative
        ax2_twin = ax2.twinx()

        # Plot accumulated std profile
        ax2.plot(x_axis, accumulated_std_profile, "purple", linewidth=3, label="Accumulated Std Profile")
        ax2.axhline(np.mean(accumulated_std_profile), color="orange", linestyle=":",
                   label=f"Average: {np.mean(accumulated_std_profile):.2f}")

        # Plot second derivative on twin axis if available
        if second_derivative is not None:
            ax2_twin.plot(x_axis, second_derivative, "cyan", linewidth=2, alpha=0.8, label="2nd Derivative")
            ax2_twin.axhline(0, color="gray", linestyle="-", alpha=0.5, label="Zero Line")

        # Mark final detection
        ax2.axvline(x_final, color="blue", linestyle="--", linewidth=3, label=f"Parabolic Detection @ {x_final}")

        ax2.set_title(f"Accumulated Std Profile Analysis")
        ax2.set_xlabel("X Position (pixels)")
        ax2.set_ylabel("Accumulated Std", color="purple")
        ax2_twin.set_ylabel("2nd Derivative", color="cyan")

        # Combine legends
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(os.path.join(debug_dir, "fold_profile_enhanced_debug.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)

    # Always save the simple version
    fig_simple, ax = plt.subplots(figsize=(10, 5))
    for prof in filtered_profiles:
        ax.plot(x_axis, prof, alpha=0.3, color="gray")
    ax.plot(x_axis, mean_profile, "r-", label="Mean")
    ax.fill_between(x_axis, mean_profile - std_profile, mean_profile + std_profile,
                    color="red", alpha=0.2, label="Std")
    ax.axvline(x_final, color="blue", linestyle="--", linewidth=2, label=f"Fold @ {x_final}")
    ax.legend()
    ax.set_title("Fold profile detection")
    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, "fold_profile_debug.png"), dpi=150)
    plt.close(fig_simple)


def save_edge_detection_debug(edge_profiles, side, margin, x_fold, search_start, search_end, debug_dir, gray_img):
    """Save visualization for document edge detection (single side)."""
    os.makedirs(debug_dir, exist_ok=True)
    positions = [pos for pos, _ in edge_profiles]
    brightnesses = [b for _, b in edge_profiles]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    ax1.plot(positions, brightnesses, "b-", linewidth=2)
    ax1.axvline(x_fold, color="red", linestyle="--", linewidth=2, label=f"Fold @ {x_fold}")
    if margin > 0:
        edge_pos = margin if side == "left" else gray_img.shape[1] - margin
        ax1.axvline(edge_pos, color="green", linestyle="--", linewidth=2, label=f"Edge @ {edge_pos}")
    ax1.axvspan(search_start, search_end, alpha=0.2, color="yellow", label="Search area")
    ax1.legend()
    ax1.set_title(f"Edge detection - {side}")

    ax2.imshow(gray_img, cmap="gray")
    ax2.axvline(x_fold, color="red", linewidth=2)
    if margin > 0:
        ax2.axvline(edge_pos, color="green", linewidth=2)
    ax2.axvspan(search_start, search_end, alpha=0.2, color="yellow")
    ax2.set_title("Image overlay")

    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, f"edge_detection_{side}.png"), dpi=150)
    plt.close(fig)


def save_edge_detection_debug_center(left_profiles, right_profiles, left_margin, right_margin, x_fold, debug_dir, gray_img):
    """Save visualization for center fold edge detection."""
    os.makedirs(debug_dir, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    if left_profiles:
        lp, lb = zip(*left_profiles)
        ax1.plot(lp, lb, "b-", label="Left profile")
    if right_profiles:
        rp, rb = zip(*right_profiles)
        ax1.plot(rp, rb, "orange", label="Right profile")

    ax1.axvline(x_fold, color="red", linestyle="--", label=f"Fold @ {x_fold}")
    ax1.legend()
    ax1.set_title(f"Center edge detection - left={left_margin}, right={right_margin}")

    ax2.imshow(gray_img, cmap="gray")
    ax2.axvline(x_fold, color="red", linewidth=2)
    if left_margin > 0:
        ax2.axvline(left_margin, color="green", linewidth=2)
    if right_margin > 0:
        ax2.axvline(gray_img.shape[1] - right_margin, color="purple", linewidth=2)
    ax2.set_title("Image overlay (center edges)")

    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, "edge_detection_center.png"), dpi=150)
    plt.close(fig)


def save_background_analysis_debug(analysis_result, debug_dir, gray_img):
    """Visualize background/page brightness analysis procedure."""
    if analysis_result is None:
        return

    os.makedirs(debug_dir, exist_ok=True)

    profile = analysis_result['profile']
    smooth_profile = analysis_result['smooth_profile']
    gradient = analysis_result['gradient']
    bg_region = analysis_result['bg_region']
    page_region = analysis_result['page_region']
    rises = analysis_result['rises']
    drops = analysis_result['drops']
    gradient_threshold = analysis_result['gradient_threshold']

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # Panel 1: Original vs Smoothed profile
    x_axis = np.arange(len(profile))
    ax1.plot(x_axis, profile, 'b-', linewidth=1, alpha=0.5, label='Original Profile')
    ax1.plot(x_axis, smooth_profile, 'r-', linewidth=2, label='Smoothed Profile')
    ax1.set_xlabel('X Position (pixels)')
    ax1.set_ylabel('Mean Brightness')
    ax1.set_title('Brightness Profile with Heavy Smoothing')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Panel 2: Gradient analysis with transitions
    ax2.plot(x_axis, gradient, 'purple', linewidth=1, label='Gradient')
    ax2.axhline(gradient_threshold, color='orange', linestyle='--', label=f'Rise Threshold: {gradient_threshold:.3f}')
    ax2.axhline(-gradient_threshold, color='red', linestyle='--', label=f'Drop Threshold: {-gradient_threshold:.3f}')

    # Mark rises and drops
    if len(rises) > 0:
        ax2.scatter(rises, gradient[rises], color='green', s=50, label='Rises (BG->Page)', zorder=5)
    if len(drops) > 0:
        ax2.scatter(drops, gradient[drops], color='red', s=50, label='Drops (Page->BG)', zorder=5)

    ax2.set_xlabel('X Position (pixels)')
    ax2.set_ylabel('Gradient')
    ax2.set_title('Gradient Analysis & Transition Detection')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Panel 3: Detected regions
    ax3.plot(x_axis, smooth_profile, 'b-', linewidth=1, alpha=0.7, label='Smoothed Profile')

    # Mark background and page regions
    ax3.axvspan(bg_region[0], bg_region[1], alpha=0.5, color='red', label=f'Background ({analysis_result["background_side"]})')
    ax3.axvspan(page_region[0], page_region[1], alpha=0.3, color='green', label='Page Plateau')

    # Mark transitions
    if len(rises) > 0:
        for rise in rises:
            ax3.axvline(rise, color='green', linestyle=':', alpha=0.7)
    if len(drops) > 0:
        for drop in drops:
            ax3.axvline(drop, color='red', linestyle=':', alpha=0.7)

    ax3.set_xlabel('X Position (pixels)')
    ax3.set_ylabel('Mean Brightness')
    ax3.set_title('Detected Page Plateau & Background Regions')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Panel 4: Statistics summary
    ax4.axis('off')
    stats_text = f"""
    BACKGROUND/PAGE ANALYSIS (Gradient-Based)
    ===========================================

    Algorithm Parameters:
    * Smoothing Kernel: {max(51, len(profile) // 50)} px
    * Gradient Threshold: +/-{gradient_threshold:.3f}

    Detected Transitions:
    - Rises (BG->Page): {len(rises)} at positions {list(rises[:3])}{'...' if len(rises) > 3 else ''}
    - Drops (Page->BG): {len(drops)} at positions {list(drops[:3])}{'...' if len(drops) > 3 else ''}

    Background Region ({analysis_result['background_side']} side):
    * Position: {bg_region[0]}-{bg_region[1]} px
    * Mean: {analysis_result['background_mean']:.1f} +/- {analysis_result['background_std']:.1f}
    * Width: {bg_region[1] - bg_region[0]} px

    Page Plateau:
    * Position: {page_region[0]}-{page_region[1]} px
    * Mean: {analysis_result['page_mean']:.1f} +/- {analysis_result['page_std']:.1f}
    * Width: {page_region[1] - page_region[0]} px

    Quality Assessment:
    * Contrast: {'EXCELLENT' if analysis_result['page_mean'] - analysis_result['background_mean'] > 50 else 'GOOD' if analysis_result['page_mean'] - analysis_result['background_mean'] > 30 else 'POOR'}
    * Background Uniformity: {'GOOD' if analysis_result['background_std'] < 15 else 'POOR'}
    * Page Uniformity: {'GOOD' if analysis_result['page_std'] < 20 else 'POOR'}
    """

    ax4.text(0.05, 0.95, stats_text, transform=ax4.transAxes, fontsize=9,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, "background_analysis_debug.png"), dpi=150, bbox_inches='tight')
    plt.close(fig)

    # Create additional image overlay visualization
    fig2, ax = plt.subplots(figsize=(16, 10))

    # Show the original image
    ax.imshow(gray_img, cmap='gray', aspect='auto')

    # Overlay detected boundaries with thick colored lines
    bg_start, bg_end = bg_region
    page_start, page_end = page_region

    # Background region - RED with transparency
    ax.axvline(bg_start, color='red', linewidth=4, alpha=0.7, label=f'BG Start: {bg_start}px')
    ax.axvline(bg_end, color='red', linewidth=4, linestyle='--', alpha=0.7, label=f'BG End: {bg_end}px')

    # Page plateau region - GREEN with transparency
    ax.axvline(page_start, color='lime', linewidth=4, alpha=0.7, label=f'Page Start: {page_start}px')
    ax.axvline(page_end, color='lime', linewidth=4, linestyle='--', alpha=0.7, label=f'Page End: {page_end}px')

    # Mark transitions with different colors and transparency
    if len(rises) > 0:
        for i, rise in enumerate(rises):
            ax.axvline(rise, color='yellow', linewidth=3, alpha=0.6,
                      label='Rise (BG->Page)' if i == 0 else '')
    if len(drops) > 0:
        for i, drop in enumerate(drops):
            ax.axvline(drop, color='orange', linewidth=3, alpha=0.6,
                      label='Drop (Page->BG)' if i == 0 else '')

    ax.set_title(f'Detected Boundaries Overlay\nPage: {page_start}-{page_end}px | Background ({analysis_result["background_side"]}): {bg_start}-{bg_end}px',
                fontsize=14)
    ax.legend(loc='upper right', fontsize=10)
    ax.set_xlabel('X Position (pixels)')
    ax.set_ylabel('Y Position (pixels)')

    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, "boundaries_overlay.png"), dpi=150, bbox_inches='tight')
    plt.close(fig2)