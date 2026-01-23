
"""
Gradient-Based Edge Detection Debug Tool (Luminance-Weighted, Robust, Adaptive-RANSAC + Recovery)
===============================================================================================

Features:
---------
- Anisotropic smoothing (direction-specific) to suppress inner content.
- Global gradient projection seeds for each border (left/right/top/bottom).
- **Luminance-weighted Sobel gradient** (compensates local brightness falloff).
- Contrast-aware peak classification (dark<->light).
- Seed-band gating to keep only edge-adjacent peaks.
- Adaptive RANSAC line fitting (vertical & horizontal).
- Recovery of missing sides using mirrored geometry + adaptive threshold scan.
- RANSAC inliers (cyan) / outliers (red) overlay.
- Matplotlib plots with accepted (green) vs rejected (red) peaks.

Usage:
------
    python debug_gradient_scanner.py <image_path>
        [--scanlines 12] [--threshold 30]
        [--debug-matplotlib] [--debug-opencv]
"""

import argparse
import cv2
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# Try scikit-learn for true RANSAC
try:
    from sklearn import linear_model
    HAVE_SKLEARN = True
except Exception:
    HAVE_SKLEARN = False


# ---------------------------------------------------------------------------
# Utility: Safe image visualization
# ---------------------------------------------------------------------------
def show_image(image, title="Image", max_width=1280, max_height=720, file_path=None):
    """
    Resize and display or save an image for debugging.
    """
    h, w = image.shape[:2]
    scale = min(max_width / w, max_height / h, 1)
    resized = cv2.resize(image, (int(w * scale), int(h * scale)))
    if file_path:
        cv2.imwrite(file_path, resized)
    else:
        cv2.imshow(title, resized)
        cv2.waitKey(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scale_from_shape(h, w):
    return max(h, w) / 2000.0


def _draw_line(img, line, color, thickness):
    if line is None:
        return
    a, b, c = line
    h, w = img.shape[:2]
    if abs(b) > 1e-6:
        x1, x2 = 0, w
        y1 = int((-a * x1 - c) / b)
        y2 = int((-a * x2 - c) / b)
    else:
        x1 = x2 = int(-c / a)
        y1, y2 = 0, h
    cv2.line(img, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Adaptive RANSAC
# ---------------------------------------------------------------------------
def fit_line_ransac(points, min_points=3, residual_threshold=5.0):
    if len(points) < min_points:
        return None, np.array([], dtype=bool)

    pts = np.array(points, dtype=np.float32)
    var_x, var_y = np.var(pts[:, 0]), np.var(pts[:, 1])
    fit_vertical = var_x < var_y

    if HAVE_SKLEARN:
        ransac_kwargs = dict(
            residual_threshold=residual_threshold,
            max_trials=200,
            stop_probability=0.995,
            random_state=0,
        )
        if "estimator" in linear_model.RANSACRegressor.__init__.__code__.co_varnames:
            ransac_kwargs["estimator"] = linear_model.LinearRegression()
        else:
            ransac_kwargs["base_estimator"] = linear_model.LinearRegression()

        try:
            if not fit_vertical:
                X = pts[:, 0].reshape(-1, 1)
                y = pts[:, 1]
                model = linear_model.RANSACRegressor(**ransac_kwargs)
                model.fit(X, y)
                m = float(model.estimator_.coef_[0])
                q = float(model.estimator_.intercept_)
                a, b, c = m, -1.0, q
            else:
                X = pts[:, 1].reshape(-1, 1)
                y = pts[:, 0]
                model = linear_model.RANSACRegressor(**ransac_kwargs)
                model.fit(X, y)
                m = float(model.estimator_.coef_[0])
                q = float(model.estimator_.intercept_)
                a, b, c = 1.0, -m, -q

            return (a, b, c), model.inlier_mask_
        except Exception:
            pass

    # fallback: OpenCV line fitting
    [vx, vy, x0, y0] = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    a, b = float(vy), float(-vx)
    c = float(-(a * x0 + b * y0))
    d = np.abs(a * pts[:, 0] + b * pts[:, 1] + c)
    cutoff = np.quantile(d, 0.80)
    mask = d <= cutoff
    return (a, b, c), mask


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def debug_plot_gradient(scanline, gradient, peaks, accepted, rejected, direction, pos, threshold):
    plt.figure(figsize=(9, 4))
    plt.title(f"{direction.upper()} scanline @ {pos}", fontsize=12)
    if gradient.max() > 0 and scanline.max() > 0:
        plt.fill_between(
            range(len(scanline)),
            (scanline / scanline.max()) * gradient.max(),
            color="lightgray", alpha=0.35, label="Intensity"
        )
    plt.plot(gradient, color="orange", lw=2, label="|∇I| (Sobel, weighted)")
    plt.axhline(threshold, color="red", ls="--", lw=1.2, label=f"Threshold={threshold}")
    if len(rejected):
        plt.scatter(rejected, gradient[rejected], color="red", s=36, label="Rejected Peaks")
    if len(accepted):
        plt.scatter(accepted, gradient[accepted], color="lime", edgecolor="black", s=50, label="Accepted Peaks")
    plt.xlabel("Pixel index"); plt.ylabel("Gradient magnitude")
    plt.grid(alpha=0.25); plt.legend(fontsize=9); plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Contrast classification with luminance weighting
# ---------------------------------------------------------------------------
def classify_peaks_by_contrast(scanline, gradient, peaks, from_start, min_contrast, dark_threshold, paper_value):
    """
    Classify peaks based on contrast polarity and local brightness.
    Now uses *luminance-weighted Sobel gradient* to stabilize detection
    in dark or unevenly lit regions.
    """
    accepted, rejected = [], []
    if len(peaks) == 0:
        return accepted, rejected

    L = len(scanline)
    contrast_sign = 1 if from_start else -1

    # --- Compute local mean brightness & weight gradient ---
    local_win = 31
    kernel = np.ones(local_win) / local_win
    local_mean = np.convolve(scanline, kernel, mode="same")
    eps = 1e-3
    weight = 1.0 / np.clip(local_mean / np.mean(local_mean), 0.5, 2.0)
    weighted_gradient = gradient * weight

    for p in peaks:
        if p < 10 or p > L - 10:
            rejected.append(p)
            continue

        before = float(np.mean(scanline[max(0, p - 10):p]))
        after = float(np.mean(scanline[p:min(L, p + 10)]))
        contrast = after - before
        rel_contrast = (contrast / max(1e-3, paper_value - dark_threshold)) * 100.0
        polarity_ok = (contrast_sign * contrast) > 0.3 * min_contrast
        contrast_ok = abs(rel_contrast) > 2.0

        dark_side = before if from_start else after
        light_side = after if from_start else before
        darkness_ok = (dark_side < (dark_threshold + 0.2 * (paper_value - dark_threshold))) \
                      and (light_side > 0.6 * paper_value)

        is_border_peak = (p < 0.02 * L) or (p > 0.98 * L)

        if (polarity_ok and contrast_ok and darkness_ok) or is_border_peak:
            accepted.append(p)
        else:
            rejected.append(p)

    return accepted, rejected


# ---------------------------------------------------------------------------
# Estimate background/paper
# ---------------------------------------------------------------------------
def estimate_background_and_paper(gray, debug_opencv=False):
    h, w = gray.shape
    c = int(min(h, w) * 0.03)
    corners = np.concatenate([
        gray[:c, :c].ravel(),
        gray[:c, -c:].ravel(),
        gray[-c:, :c].ravel(),
        gray[-c:, -c:].ravel(),
    ])
    dark_value = np.percentile(corners, 10)
    ch1, ch2 = int(h * 0.3), int(h * 0.7)
    cw1, cw2 = int(w * 0.3), int(w * 0.7)
    center_vals = gray[ch1:ch2, cw1:cw2].ravel()
    paper_value = np.percentile(center_vals, 90)

    contrast_span = max(1.0, paper_value - dark_value)
    min_contrast = max(8.0, contrast_span * 0.15)
    dark_threshold = paper_value - contrast_span * 0.35

    print(f"[AUTO] paper≈{paper_value:.1f}, dark≈{dark_value:.1f}, "
          f"contrast_span≈{contrast_span:.1f}, "
          f"min_contrast≈{min_contrast:.1f}, dark_thresh≈{dark_threshold:.1f}")

    if debug_opencv:
        vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(vis, (0, 0), (c, c), (255, 0, 0), 2)
        cv2.rectangle(vis, (w - c, 0), (w - 1, c), (255, 0, 0), 2)
        cv2.rectangle(vis, (0, h - c), (c, h - 1), (255, 0, 0), 2)
        cv2.rectangle(vis, (w - c, h - c), (w - 1, h - 1), (255, 0, 0), 2)
        cv2.rectangle(vis, (cw1, ch1), (cw2, ch2), (0, 255, 255), 2)
        show_image(vis, "Auto Paper/Dark Detection")

    return paper_value, dark_threshold, min_contrast


# ---------------------------------------------------------------------------
# Anisotropic smoothing
# ---------------------------------------------------------------------------
def anisotropic_blurs(gray):
    h, w = gray.shape
    ky = max(15, (h // 60) | 1)
    kx = max(15, (w // 60) | 1)
    kx_small, ky_small = 5 | 1, 5 | 1
    gx_long = cv2.getGaussianKernel(kx, kx / 3.0)
    gy_long = cv2.getGaussianKernel(ky, ky / 3.0)
    gx_small = cv2.getGaussianKernel(kx_small, kx_small / 3.0)
    gy_small = cv2.getGaussianKernel(ky_small, ky_small / 3.0)
    blur_for_vertical = cv2.sepFilter2D(gray, -1, gx_small, gy_long)
    blur_for_horizontal = cv2.sepFilter2D(gray, -1, gx_long, gy_small)
    return blur_for_vertical, blur_for_horizontal


# ---------------------------------------------------------------------------
# Seeds and Scanning
# ---------------------------------------------------------------------------
def projection_seeds(grad_x_abs, grad_y_abs):
    h, w = grad_x_abs.shape
    horiz_profile = grad_x_abs.mean(axis=0)
    vert_profile = grad_y_abs.mean(axis=1)
    kx = max(9, (w // 200) | 1)
    ky = max(9, (h // 200) | 1)
    horiz_s = cv2.GaussianBlur(horiz_profile.reshape(1, -1), (1, kx), 0).ravel()
    vert_s = cv2.GaussianBlur(vert_profile.reshape(-1, 1), (ky, 1), 0).ravel()

    left_win = horiz_s[: max(3, w // 8)]
    right_win = horiz_s[w - len(left_win):]
    top_win = vert_s[: max(3, h // 8)]
    bottom_win = vert_s[h - len(top_win):]

    x_left = int(np.argmax(left_win))
    x_right = int(np.argmax(right_win) + (w - len(right_win)))
    y_top = int(np.argmax(top_win))
    y_bot = int(np.argmax(bottom_win) + (h - len(top_win)))
    return x_left, x_right, y_top, y_bot


# ---------------------------------------------------------------------------
# Recovery for missing sides
# ---------------------------------------------------------------------------
def recover_missing_side(gray, side, results, seeds, bands, threshold_factor=0.6):
    """
    Attempt to recover a missing side using information from the opposite edge.
    Uses a simple adaptive threshold and local gradient search.
    """
    h, w = gray.shape
    recovered_points = []

    # Estimate expected position range from opposite side
    if side == "top_points":
        ref_pts = results["bottom_points"]
        axis = "horizontal"
        pos_guess = int(np.median([p[1] for p in ref_pts])) if ref_pts else int(h * 0.1)
        band = bands[1]
        y_range = range(max(0, pos_guess - band), max(5, pos_guess - band // 2))
    elif side == "bottom_points":
        ref_pts = results["top_points"]
        axis = "horizontal"
        pos_guess = int(np.median([p[1] for p in ref_pts])) if ref_pts else int(h * 0.9)
        band = bands[1]
        y_range = range(min(h - 1, pos_guess + band // 2), min(h, pos_guess + band))
    elif side == "left_points":
        ref_pts = results["right_points"]
        axis = "vertical"
        pos_guess = int(np.median([p[0] for p in ref_pts])) if ref_pts else int(w * 0.1)
        band = bands[0]
        x_range = range(max(0, pos_guess - band), max(5, pos_guess - band // 2))
    else:
        ref_pts = results["left_points"]
        axis = "vertical"
        pos_guess = int(np.median([p[0] for p in ref_pts])) if ref_pts else int(w * 0.9)
        band = bands[0]
        x_range = range(min(w - 1, pos_guess + band // 2), min(w, pos_guess + band))

    # Adaptive threshold based on global histogram
    mean_intensity = np.mean(gray)
    thresh = mean_intensity * threshold_factor
    _, bin_img = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)

    # Morphological cleanup
    bin_img = cv2.medianBlur(bin_img, 5)
    bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    # Search for edge transitions within the band region
    if axis == "horizontal":
        for x in np.linspace(int(0.1 * w), int(0.9 * w), 12, dtype=int):
            for y in y_range:
                if 1 < y < h - 1:
                    grad = abs(int(gray[y + 1, x]) - int(gray[y - 1, x]))
                    if grad > 15:
                        recovered_points.append((x, y))
                        break
    else:
        for y in np.linspace(int(0.1 * h), int(0.9 * h), 12, dtype=int):
            for x in x_range:
                if 1 < x < w - 1:
                    grad = abs(int(gray[y, x + 1]) - int(gray[y, x - 1]))
                    if grad > 15:
                        recovered_points.append((x, y))
                        break

    print(f"[INFO] {side}: recovered {len(recovered_points)} candidate points.")
    return recovered_points


# ---------------------------------------------------------------------------
# Full scanning pipeline
# ---------------------------------------------------------------------------
def scan_and_detect_edges_debug(gray, num_scanlines, threshold, debug_matplotlib=False, debug_opencv=False):
    h, w = gray.shape
    scale = _scale_from_shape(h, w)
    paper_value, dark_threshold, min_contrast = estimate_background_and_paper(gray, debug_opencv)
    blur_v, blur_h = anisotropic_blurs(gray)
    grad_y = cv2.Sobel(blur_v, cv2.CV_64F, 0, 1, ksize=3)
    grad_x = cv2.Sobel(blur_h, cv2.CV_64F, 1, 0, ksize=3)
    abs_gx, abs_gy = np.abs(grad_x), np.abs(grad_y)

    xL_seed, xR_seed, yT_seed, yB_seed = projection_seeds(abs_gx, abs_gy)
    band_x, band_y = max(8, int(0.05 * w)), max(8, int(0.05 * h))
    results = {"top_points": [], "bottom_points": [], "left_points": [], "right_points": []}

    # --- Vertical ---
    x_positions = np.linspace(int(0.10 * w), int(0.90 * w), num_scanlines, dtype=int)
    for x in x_positions:
        scanline = blur_v[:, x]
        gradient = abs_gy[:, x]
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold * 0.30)
        acc_top, _ = classify_peaks_by_contrast(scanline, gradient, peaks, True, min_contrast, dark_threshold, paper_value)
        acc_bot, _ = classify_peaks_by_contrast(scanline, gradient, peaks, False, min_contrast, dark_threshold, paper_value)
        acc_top = [p for p in acc_top if abs(p - yT_seed) <= band_y]
        acc_bot = [p for p in acc_bot if abs(p - yB_seed) <= band_y]

        if debug_matplotlib:
            accepted = sorted(set(acc_top + acc_bot))
            rejected = [p for p in peaks if p not in accepted]
            debug_plot_gradient(scanline, gradient, peaks, accepted, rejected, "vertical", x, threshold)

        for p in acc_top: results["top_points"].append((x, p))
        for p in acc_bot: results["bottom_points"].append((x, p))

    # --- Horizontal ---
    y_positions = np.linspace(int(0.10 * h), int(0.90 * h), num_scanlines, dtype=int)
    for y in y_positions:
        scanline = blur_h[y, :]
        gradient = abs_gx[y, :]
        peaks, _ = find_peaks(gradient, height=threshold, prominence=threshold * 0.30)
        acc_left, _ = classify_peaks_by_contrast(scanline, gradient, peaks, True, min_contrast, dark_threshold, paper_value)
        acc_right, _ = classify_peaks_by_contrast(scanline, gradient, peaks, False, min_contrast, dark_threshold, paper_value)
        acc_left = [p for p in acc_left if abs(p - xL_seed) <= band_x]
        acc_right = [p for p in acc_right if abs(p - xR_seed) <= band_x]

        if debug_matplotlib:
            accepted = sorted(set(acc_left + acc_right))
            rejected = [p for p in peaks if p not in accepted]
            debug_plot_gradient(scanline, gradient, peaks, accepted, rejected, "horizontal", y, threshold)

        for p in acc_left: results["left_points"].append((p, y))
        for p in acc_right: results["right_points"].append((p, y))

    # --- Attempt recovery for missing sides ---
    for side in ["top_points", "bottom_points", "left_points", "right_points"]:
        if len(results[side]) < 5:
            print(f"[WARN] {side} weak or missing — attempting recovery")
            results[side] = recover_missing_side(gray, side, results, (xL_seed, xR_seed, yT_seed, yB_seed), (band_x, band_y))

    if debug_opencv:
        total_points = sum(len(v) for v in results.values())
        if total_points == 0:
            print("[WARN] No accepted peaks found — nothing to display.")
        else:
            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            for side, pts in results.items():
                color = (0, 255, 255)
                for (x, y) in pts:
                    cv2.circle(vis, (int(x), int(y)), 3, color, -1)
            show_image(vis, "Accepted Peaks Overlay")

    return results, (xL_seed, xR_seed, yT_seed, yB_seed), (band_x, band_y)


# ---------------------------------------------------------------------------
# Main Debug Driver
# ---------------------------------------------------------------------------
def debug_gradient_peak_scanner(image_path, num_scanlines=30, gradient_threshold=30,
                                debug_matplotlib=False, debug_opencv=False):
    print('[INFO] Debugging Gradient-Based Page Edge Detection')
    if isinstance(image_path, str):
        img = cv2.imread(image_path)
    else:
        img = image_path
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = _scale_from_shape(h, w)

    print(f"Resolution: {w}x{h}")
    print(f"Scanlines per direction: {num_scanlines}")
    print(f"Threshold: {gradient_threshold}")

    results, seeds, bands = scan_and_detect_edges_debug(
        gray, num_scanlines, gradient_threshold,
        debug_matplotlib=debug_matplotlib, debug_opencv=debug_opencv,
    )

    vis_ransac = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    lines = {}
    inlier_masks = {}

    def fit_and_draw(label_key, color):
        pts = results[label_key]
        if not pts:
            inlier_masks[label_key] = np.array([], bool)
            return None
        line, mask = fit_line_ransac(pts, residual_threshold=max(3.0, 20.0 * scale))
        inlier_masks[label_key] = mask
        _draw_line(vis_ransac, line, color, max(2, int(3 * scale)))
        return line

    lines["top"] = fit_and_draw("top_points", (0, 255, 255))
    lines["bottom"] = fit_and_draw("bottom_points", (0, 255, 255))
    lines["left"] = fit_and_draw("left_points", (0, 255, 255))
    lines["right"] = fit_and_draw("right_points", (0, 255, 255))

    # --- Optional sanity check: ensure detected page covers most of the image ---
    try:
        # Try to compute intersections only if all 4 lines exist
        if all(lines.values()):
            def intersect(l1, l2):
                a1, b1, c1 = l1
                a2, b2, c2 = l2
                det = a1 * b2 - a2 * b1
                if abs(det) < 1e-8:
                    return None
                x = (b1 * c2 - b2 * c1) / det
                y = (c1 * a2 - c2 * a1) / det
                return np.array([x, y], dtype=np.float32)

            tl = intersect(lines["top"], lines["left"])
            tr = intersect(lines["top"], lines["right"])
            br = intersect(lines["bottom"], lines["right"])
            bl = intersect(lines["bottom"], lines["left"])

            if all(pt is not None for pt in [tl, tr, br, bl]):
                box = np.array([tl, tr, br, bl])
                box_w = np.linalg.norm(tr - tl)
                box_h = np.linalg.norm(bl - tl)
                w_ratio = box_w / w
                h_ratio = box_h / h
                if w_ratio < 0.6 or h_ratio < 0.6:
                    print(f"[WARN] Gradient-detected area too small "
                          f"({w_ratio*100:.1f}% x {h_ratio*100:.1f}%) — forcing fallback.")
                    raise ValueError("Invalid page coverage")
    except Exception as e:
        print(f"[DEBUG] Coverage validation failed: {e}")
        raise
        
    # show_image(vis_ransac, "Final RANSAC Fitted Edges")

    # Return both peaks and fitted lines
    return {"points": results, "lines": lines, "inliers": inlier_masks}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gradient-based page edge detection debug tool (luminance weighted + adaptive RANSAC + recovery)")
    parser.add_argument("image", help="Path to input image")
    parser.add_argument("--scanlines", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=20)
    parser.add_argument("--debug-matplotlib", action="store_true")
    parser.add_argument("--debug-opencv", action="store_true")
    args = parser.parse_args()

    debug_gradient_peak_scanner(
        args.image,
        num_scanlines=args.scanlines,
        gradient_threshold=args.threshold,
        debug_matplotlib=args.debug_matplotlib,
        debug_opencv=args.debug_opencv,
    )
