"""
debug_tools.py

Modulo per funzioni di debug e visualizzazione.
"""

import cv2
import os
import numpy as np
from scipy.optimize import curve_fit
from .utils import parabola


def save_debug_visualization(filtered_profiles, mean_profile, std_profile, x_axis, x0, x_min, x_final, roi, debug_dir):
    """
    Salva le immagini di debug per l'analisi visiva.
    """
    import matplotlib.pyplot as plt
    os.makedirs(debug_dir, exist_ok=True)

    # Plot profili di luminosità e fit parabolico
    fig, (ax1, ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [2, 1]}, figsize=(8, 6))
    for prof in filtered_profiles:
        ax1.plot(x_axis, prof, color='gray', linewidth=0.5, alpha=0.3)
    ax1.errorbar(x_axis, mean_profile, yerr=std_profile, color='red', ecolor='salmon',
                 linewidth=2, elinewidth=1, capsize=2, label='mean +/- std')
    ax1.set_title('Brightness profiles (filtered)')
    ax1.set_ylabel('Gray value')
    ax1.grid(True)
    ax1.legend(fontsize='xx-small', loc='upper right', framealpha=0.6)
    ax2.imshow(roi, cmap='gray', aspect='auto')
    ax2.set_title('ROI preview')
    ax2.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, 'step_profiles.png'))
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_axis, mean_profile, label='Mean profile', alpha=0.5)
    smooth = cv2.GaussianBlur(mean_profile + std_profile, (11, 1), 0).flatten()
    ax.plot(x_axis, smooth, label='Smoothed', color='orange')
    ax.axvline(x0 + x_min, color='gray', linestyle='--', label='Min raw')
    ax.axvline(x_final, color='red', linestyle='--', label='Min refined')
    x_fit = np.arange(max(0, x_min-15), min(len(smooth), x_min+16))
    popt, _ = curve_fit(parabola, x_fit, smooth[x_fit])
    ax.plot(x0 + x_fit, parabola(x_fit, *popt), 'r:', label='Parabolic fit')
    ax.set_title('Profile + Fit')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(debug_dir, 'step_min_fit.png'))
    plt.close(fig)


def save_debug_line_visualization(img, x_fold, angle, a, b, output_path,
                                   original_img=None, transformation_matrix=None):
    """
    Salva un'immagine con la linea della piega visualizzata per debug.

    Args:
        img: Image where fold was detected (rectified)
        x_fold: X coordinate of fold
        angle: Angle of fold
        a: Slope of fold line (x = a*y + b)
        b: Intercept of fold line
        output_path: Where to save visualization
        original_img: Original image before rectification (optional)
        transformation_matrix: Transformation matrix M from warp_image (optional)

    If transformation_matrix and original_img are provided, the fold line will be
    inverse-transformed and drawn on the original image. Otherwise, it's drawn on
    the rectified image.
    """
    # Calculate fold line endpoints in the space where fold was detected
    h = img.shape[0]
    fold_p1_rect = (int(b), 0)  # Top: x = b when y=0
    fold_p2_rect = (int(a * h + b), h)  # Bottom: x = a*h + b when y=h

    # Determine which image to draw on and transform coordinates if needed
    if transformation_matrix is not None and original_img is not None:
        # Inverse transform fold line from rectified to original space
        import numpy as np

        # Compute inverse transformation matrix
        M_inv = cv2.invertAffineTransform(transformation_matrix)

        # Transform fold endpoints
        p1_h = np.array([fold_p1_rect[0], fold_p1_rect[1], 1.0], dtype=np.float32)
        p2_h = np.array([fold_p2_rect[0], fold_p2_rect[1], 1.0], dtype=np.float32)

        p1_orig_h = M_inv @ p1_h
        p2_orig_h = M_inv @ p2_h

        fold_p1_orig = (int(p1_orig_h[0]), int(p1_orig_h[1]))
        fold_p2_orig = (int(p2_orig_h[0]), int(p2_orig_h[1]))

        # Draw on original image
        vis = original_img.copy()
        cv2.line(vis, fold_p1_orig, fold_p2_orig, (0, 0, 255), 2)
    else:
        # Draw on rectified image (fallback)
        vis = img.copy()
        cv2.line(vis, fold_p1_rect, fold_p2_rect, (0, 0, 255), 2)

    cv2.imwrite(output_path, vis)
