"""
fold_detection.py

Simplified Book Fold Detection System
====================================

This module implements a simplified fold detection algorithm using brightness profile
analysis and parabolic curve fitting. The fold is always assumed to be in the center.

Key Functions:
- find_fold_center: Main function for detecting fold position in center ROI
- extract_simple_brightness_profiles: Extract brightness profiles with basic statistics

Author: [Generated Documentation]
Version: 3.0 (Simplified)
"""

import cv2
import numpy as np
from scipy.optimize import curve_fit

from .utils import parabola


def extract_simple_brightness_profiles(roi, rows=None, num_samples=60):
    """
    Simple Brightness Profile Extraction
    ===================================

    Extracts horizontal brightness profiles from random row positions
    and applies basic statistical filtering.

    Args:
        roi (np.ndarray): Region of Interest grayscale image
        num_samples (int): Number of horizontal profiles to extract

    Returns:
        tuple: (mean_profile, std_profile)
               - mean_profile (np.ndarray): Mean brightness profile
               - std_profile (np.ndarray): Standard deviation profile
    """
    h = roi.shape[0]

    # Use provided rows or generate random row indices
    if rows is None:
        if h <= num_samples:
            rows = np.arange(h)
        else:
            rows = np.random.choice(h, size=num_samples, replace=False)

    # Extract brightness profiles
    profiles = [roi[r, :] for r in rows]
    avg_ints = [prof.mean() for prof in profiles]

    # Simple outlier filtering using 1.5 sigma rule
    mean_int = np.mean(avg_ints)
    std_int = np.std(avg_ints)

    filtered_profiles = [
        prof
        for prof, avg in zip(profiles, avg_ints)
        if abs(avg - mean_int) <= 1.5 * std_int
    ]

    # Fallback if all profiles filtered out
    if not filtered_profiles:
        filtered_profiles = profiles

    # Calculate ensemble statistics
    arr = np.array(filtered_profiles)
    mean_profile = arr.mean(axis=0)
    std_profile = arr.std(axis=0)

    return mean_profile, std_profile


def find_fold_center(img=None, roi=None):
    """
    Find Fold Center Position with Quality Assessment
    ================================================

    Main function to detect fold position using parabolic curve fitting.
    Can work with either full image (uses center ROI) or custom ROI.
    Now includes position consistency analysis across iterations.

    Args:
        img (np.ndarray): Full BGR image (will extract center ROI)
        roi (np.ndarray): Custom ROI grayscale image (optional)

    Returns:
        tuple: (x_position, quality_score)
               - x_position (int): Fold x-position in global image coordinates
               - quality_score (float): Quality score based on position consistency (0.0-1.0)
    """
    if roi is not None:
        # Use provided ROI
        gray_roi = roi if len(roi.shape) == 2 else cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        x_offset = 0  # No offset needed for custom ROI
    elif img is not None:
        # Extract center ROI from full image
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        # Use center 20% of image
        x_start = int(0.4 * w)
        x_end = int(0.6 * w)
        gray_roi = gray[:, x_start:x_end]
        x_offset = x_start
    else:
        raise ValueError("Either img or roi must be provided")

    # Apply noise reduction with adaptive kernel size
    roi_height, roi_width = gray_roi.shape

    # Calculate kernel size as percentage of ROI dimensions (must be odd)
    # Use smaller dimension to ensure kernel fits properly
    min_roi_size = min(roi_height, roi_width)
    kernel_size = max(3, int(min_roi_size * 0.02))  # 2% of smaller dimension, minimum 3
    if kernel_size % 2 == 0:  # Ensure odd number
        kernel_size += 1

    blur_roi = cv2.GaussianBlur(gray_roi, (kernel_size, kernel_size), 0)

    iterations = 20
    detected_positions = []
    profiles_sum = None

    # Pre-shuffle all rows to ensure different samples across iterations
    h = blur_roi.shape[0]
    all_rows = np.arange(h)
    np.random.shuffle(all_rows)

    profile_sum = None

    # Track position across all iterations
    for i in range(iterations):
        # Extract brightness profiles for this iteration using different row partitions
        rows_per_iteration = min(60, h // iterations)
        start_idx = (i * rows_per_iteration) % h
        end_idx = min(start_idx + rows_per_iteration, h)

        # Use different rows for each iteration
        iteration_rows = all_rows[start_idx:end_idx]
        if len(iteration_rows) < 10:  # Fallback if partition too small
            iteration_rows = all_rows[
                np.random.choice(h, size=min(10, h), replace=False)
            ]

        mean_profile, std_profile = extract_simple_brightness_profiles(
            blur_roi, iteration_rows
        )

        # Enhance fold contrast by combining mean brightness with uncertainty
        enhanced_profile = mean_profile + std_profile

        # Remove linear trend to focus on fold signal
        x_coords = np.arange(len(enhanced_profile))
        # Fast linear detrend: subtract linear fit
        linear_fit = np.polyfit(x_coords, enhanced_profile, 1)
        linear_trend = np.polyval(linear_fit, x_coords)
        enhanced_profile = enhanced_profile - linear_trend

        # Accumulate profiles for final average
        if profiles_sum is None:
            profiles_sum = enhanced_profile.copy()
        else:
            profiles_sum += enhanced_profile

        # Apply smoothing for this iteration with adaptive kernel size
        # For 1D smoothing, use smaller kernel (1% of profile width)
        profile_length = len(enhanced_profile)
        smooth_kernel_size = max(
            3, int(profile_length * 0.01)
        )  # 1% of profile width, minimum 3
        if smooth_kernel_size % 2 == 0:  # Ensure odd number
            smooth_kernel_size += 1

        smooth = cv2.GaussianBlur(
            enhanced_profile, (smooth_kernel_size, 1), 0
        ).flatten()

        # Find approximate minimum position for this iteration
        x_min = np.argmin(smooth)

        # Define fitting window around minimum
        x_fit = np.arange(max(0, x_min - 15), min(len(smooth), x_min + 16))
        y_fit = smooth[x_fit]

        # Fit parabolic curve for this iteration
        try:
            popt, _ = curve_fit(parabola, x_fit, y_fit)
            # Calculate exact parabola vertex (minimum) position
            x_refined = -popt[1] / (2 * popt[0])
            x_iteration = x_offset + x_refined
        except Exception as e:
            # Fallback to simple minimum if curve fitting fails
            print("Error in curve fitting:", e)
            x_iteration = x_offset + x_min

        detected_positions.append(x_iteration)

    # Calculate average and final result
    profiles_sum /= iterations

    # Detect multiple minima in the final averaged profile
    from scipy.signal import find_peaks

    # Apply smoothing to remove spikes before peak detection
    smooth_kernel = max(3, int(len(profiles_sum) * 0.02))  # 2% of profile length
    if smooth_kernel % 2 == 0:
        smooth_kernel += 1
    smoothed_profile = cv2.GaussianBlur(profiles_sum, (smooth_kernel, 1), 0).flatten()

    # Find peaks in inverted profile (minima become peaks)
    inverted_profile = -smoothed_profile

    # Use prominence instead of height - more robust to spikes
    peaks, properties = find_peaks(
        inverted_profile,
        prominence=np.std(inverted_profile) * 3,
        distance=roi_width * 0.1,  # Minimum distance between peaks (10% of ROI width)
        width=3,  # Minimum width in samples
    )

    num_minima = len(peaks)
    print(
        f"Detected {num_minima} potential fold minima at positions: {peaks + x_offset}"
    )

    quality_score = 0
    best_peak_idx = None
    peak_depth_score = 0.0

    if num_minima == 1:
        x_final = int(peaks[0] + x_offset)
        best_peak_idx = 0
        print(f"Single minimum detected at x={x_final}")
    elif num_minima <= 3:
        # Multiple minima detected - choose the most central one
        center_roi = roi_width // 2
        distances_from_center = np.abs(peaks - center_roi)
        best_peak_idx = np.argmin(distances_from_center)
        best_peak_position = peaks[best_peak_idx]
        x_final = int(best_peak_position + x_offset)

        # Check if the selected peak is actually close enough to center
        # Good fold should be within 5% of ROI width from center
        # Maximum acceptable distance is 15% of ROI width
        good_center_distance = roi_width * 0.05  # Good: within 5%
        max_center_distance = roi_width * 0.15   # Acceptable: within 15%
        distance_from_center = abs(best_peak_position - center_roi)

        if distance_from_center > max_center_distance:
            # Selected peak too far from center - unreliable
            print(f"Multiple minima detected but closest one at x={x_final} is {distance_from_center:.1f}px from center (>{max_center_distance:.1f}px)")
            print(f"Peak too far from center - treating as unreliable")
            x_final = int(round(np.mean(detected_positions)))
            best_peak_idx = None  # Mark as unreliable
        elif distance_from_center <= good_center_distance:
            # Peak very close to center - excellent
            print(f"Multiple minima detected! Using most central at x={x_final} (distance from center: {distance_from_center:.1f}px - GOOD)")
        else:
            # Peak within acceptable range but not ideal
            print(f"Multiple minima detected! Using most central at x={x_final} (distance from center: {distance_from_center:.1f}px - acceptable)")
    else:
        # Too many minima - unreliable peak detection
        x_final = int(round(np.mean(detected_positions)))
        quality_score = 0.5
        best_peak_idx = None  # No reliable peak
        print(f"Too many minima ({num_minima}) - using mean position at x={x_final}")

    # Calculate peak depth score and centrality score (only if we have a reliable peak)
    centrality_score = 0.0

    if best_peak_idx is not None and num_minima <= 3:
        # Calculate centrality score based on distance from center
        fold_center_roi = x_final - x_offset
        center_roi = roi_width // 2
        distance_from_center = abs(fold_center_roi - center_roi)

        # Centrality score: excellent within 5%, degrades linearly to 15%
        good_center_distance = roi_width * 0.05
        max_center_distance = roi_width * 0.15

        if distance_from_center <= good_center_distance:
            centrality_score = 1.0  # Excellent: within 5%
        elif distance_from_center <= max_center_distance:
            # Linear interpolation from 1.0 at 5% to 0.3 at 15%
            ratio = (distance_from_center - good_center_distance) / (max_center_distance - good_center_distance)
            centrality_score = 1.0 - (ratio * 0.7)  # Goes from 1.0 to 0.3
        else:
            centrality_score = 0.0  # Too far from center

        # Get prominence of the selected peak
        peak_prominence = properties['prominences'][best_peak_idx]

        # Calculate noise level: std of profile excluding peak region
        exclude_width = max(20, int(roi_width * 0.05))  # Exclude 5% around peak
        exclude_start = max(0, fold_center_roi - exclude_width)
        exclude_end = min(len(smoothed_profile), fold_center_roi + exclude_width)

        # Profile without peak region
        profile_without_peak = np.concatenate([
            profiles_sum[:exclude_start],
            profiles_sum[exclude_end:]
        ]) if exclude_start < exclude_end else profiles_sum

        noise_level = np.std(profile_without_peak)

        # Signal-to-noise ratio
        snr = peak_prominence / noise_level if noise_level > 0 else 0

        # Convert SNR to score (0.0 to 1.0)
        # SNR > 5 is excellent, 3-5 is good, 1-3 is acceptable, <1 is poor
        if snr >= 6:
            peak_depth_score = 1.0
        elif snr >= 5:
            peak_depth_score = 0.8
        elif snr >= 4:
            peak_depth_score = 0.6
        elif snr >= 3:
            peak_depth_score = 0.4
        else:
            peak_depth_score = 0.2

        print(f"Peak depth analysis: prominence={peak_prominence:.2f}, noise={noise_level:.2f}, SNR={snr:.2f}, score={peak_depth_score:.2f}")
        print(f"Centrality analysis: distance={distance_from_center:.1f}px, score={centrality_score:.2f}")

    # Calculate position consistency quality score
    position_std = np.std(detected_positions)

    # Calculate ROI width to make thresholds relative to image size
    roi_width = gray_roi.shape[1]

    # Quality thresholds as percentage of ROI width
    # These percentages are based on typical fold detection accuracy expectations
    excellent_threshold = roi_width * 0.01  # 1% of ROI width (very tight)
    good_threshold = roi_width * 0.02  # 2% of ROI width (tight)
    acceptable_threshold = roi_width * 0.05  # 5% of ROI width (moderate)
    poor_threshold = roi_width * 0.1  # 10% of ROI width (loose)

    print(excellent_threshold, poor_threshold)
    print(position_std)

    # Quality score based on position stability relative to ROI size
    consistency_score = 0.0
    if position_std <= excellent_threshold:
        consistency_score = 1.0  # Excellent consistency
    elif position_std <= good_threshold:
        consistency_score = 0.6  # Good consistency
    elif position_std <= acceptable_threshold:
        consistency_score = 0.4  # Acceptable consistency
    elif position_std <= poor_threshold:
        consistency_score = 0.2  # Poor consistency
    else:
        consistency_score = 0.1  # Very poor consistency

    # Calculate final quality score from three components
    if best_peak_idx is not None:
        # All three scores available: SNR, consistency, centrality
        quality_score = (peak_depth_score + consistency_score + centrality_score) / 3.0
    else:
        # Only consistency available (unreliable peak detection)
        quality_score = consistency_score * 0.5  # Cap at 0.5 for unreliable cases

    print(f"Consistency: {consistency_score:.2f}, SNR: {peak_depth_score:.2f}, Centrality: {centrality_score:.2f}, Final: {quality_score:.2f}")

    # import matplotlib.pyplot as plt

    # plt.plot(profiles_sum)
    # plt.title(
    #     f"Fold Detection - Quality: {quality_score:.2f} (std: {position_std:.1f}px)"
    #     + "\n"
    #     + f"Vertical variations: {np.std(profiles_sum):.3f}px"
    # )
    # plt.show()

    return x_final, quality_score


def detect_fold_brightness_profile(img, side, debug=False, debug_dir=None):
    """
    Main Fold Detection Function with Quality Assessment
    ===================================================

    Maintains compatibility with existing code while using simplified algorithm.
    Always assumes center fold regardless of side parameter.
    Now includes position consistency-based quality assessment.

    Args:
        img (np.ndarray): Input BGR image
        side (str): Fold side (ignored - always uses center)
        debug (bool): Debug flag (ignored in simplified version)
        debug_dir (str): Debug directory (ignored in simplified version)

    Returns:
        tuple: (x_final, angle, slope, intercept, confidence)
               - x_final (int): Fold position
               - angle (float): Always 0.0 (angle estimation removed)
               - slope (float): Always 0.0 (slope estimation removed)
               - intercept (float): Always 0.0 (intercept estimation removed)
               - confidence (float): Quality score based on position consistency (0.0-1.0)
    """
    # Use fold detection with quality assessment
    x_final, quality_score = find_fold_center(img=img)

    # Return quality score as confidence for compatibility
    # For vertical line at x=x_final: equation is x = 0*y + x_final
    # So: angle=0, slope=0, intercept=x_final (NOT 0!)
    return x_final, 0.0, 0.0, x_final, quality_score
