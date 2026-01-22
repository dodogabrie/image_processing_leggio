import time

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


def image_entropy(img_gray):
    """Compute image entropy (measure of information content)."""
    hist = cv2.calcHist([img_gray], [0], None, [256], [0, 256])
    hist /= hist.sum()
    entropy = -np.sum([p * np.log2(p) for p in hist if p > 0])
    return entropy


def edge_density(img_gray):
    """Compute edge density (fraction of edge pixels)."""
    edges = cv2.Canny(img_gray, 100, 200)
    density = np.sum(edges > 0) / edges.size
    return density


def estimate_skew_angle(img_gray):
    """Estimate residual skew angle using Hough line detection."""
    edges = cv2.Canny(img_gray, 100, 200)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
    if lines is None:
        return 0.0
    angles = []
    for rho, theta in lines[:, 0]:
        angle = np.rad2deg(theta) - 90
        angles.append(angle)
    if len(angles) == 0:
        return 0.0
    return np.median(angles)


def evaluate_quality(
    original, processed, compute_psnr_ssim=False, compression_info=None
):
    """
    Valuta la qualità dell'immagine processata rispetto all'originale.

    Cosa misura:
    - Sharpness (nitidezza residua)
    - Entropia (informazione residua)
    - Edge density (presenza di contorni netti)
    - Residual skew angle (quanto è dritta la pagina)
    - PSNR / SSIM opzionali (poco significativi se immagine ruotata)

    Args:
        original (np.ndarray): Crop originale senza rotazione
        processed (np.ndarray): Crop ruotato
        compute_psnr_ssim (bool): Se True, calcola anche PSNR / SSIM
        compression_info (str): Information about compression used

    Returns:
        dict: Quality evaluation results
    """

    # --- Pre-processing ---
    # Convert to grayscale
    gray_orig = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    gray_proc = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

    # Crop automatico su area comune
    h_common = min(gray_orig.shape[0], gray_proc.shape[0])
    w_common = min(gray_orig.shape[1], gray_proc.shape[1])

    gray_orig_cropped = gray_orig[0:h_common, 0:w_common]
    gray_proc_cropped = gray_proc[0:h_common, 0:w_common]

    # --- Sharpness ---
    sharp_orig = cv2.Laplacian(gray_orig_cropped, cv2.CV_64F).var()
    sharp_proc = cv2.Laplacian(gray_proc_cropped, cv2.CV_64F).var()

    # --- Entropy ---
    entropy_orig = image_entropy(gray_orig_cropped)
    entropy_proc = image_entropy(gray_proc_cropped)

    # --- Edge Density ---
    edges_orig = edge_density(gray_orig_cropped)
    edges_proc = edge_density(gray_proc_cropped)

    # --- Residual Skew Angle ---
    skew_proc = estimate_skew_angle(gray_proc_cropped)

    # --- Print Results ---
    print("=== QUALITY EVALUATION ===")
    print(f"Sharpness (orig): {sharp_orig:.2f}")
    print(f"Sharpness (proc): {sharp_proc:.2f}")
    print(f"Entropy (orig): {entropy_orig:.3f}")
    print(f"Entropy (proc): {entropy_proc:.3f}")
    print(f"Edge Density (orig): {edges_orig:.4f}")
    print(f"Edge Density (proc): {edges_proc:.4f}")
    print(f"Residual skew angle (proc): {skew_proc:.2f} deg")

    # --- Optional PSNR / SSIM ---
    if compute_psnr_ssim:
        psnr_val = cv2.PSNR(gray_orig_cropped, gray_proc_cropped)
        ssim_val = ssim(gray_orig_cropped, gray_proc_cropped)
        print(f"PSNR: {psnr_val:.2f} dB")
        print(f"SSIM: {ssim_val:.4f}")

    print("=========================\n")

    results = {
        "sharpness": {"original": sharp_orig, "processed": sharp_proc},
        "entropy": {"original": entropy_orig, "processed": entropy_proc},
        "edge_density": {"original": edges_orig, "processed": edges_proc},
        "residual_skew_angle": skew_proc,
        "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if compression_info:
        results["compression_settings"] = compression_info

    if compute_psnr_ssim:
        psnr_val = cv2.PSNR(gray_orig_cropped, gray_proc_cropped)
        ssim_val = ssim(gray_orig_cropped, gray_proc_cropped)
        results["psnr"] = psnr_val
        results["ssim"] = ssim_val

    return results
