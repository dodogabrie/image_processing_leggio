import cv2, numpy as np, os
from scipy.ndimage import convolve
import matplotlib.pyplot as plt

def estimate_peak_width(col_scores, peak_idx, threshold_ratio=0.5):
    peak_val = col_scores[peak_idx]
    threshold = peak_val * threshold_ratio
    left = right = peak_idx

    while left > 0 and col_scores[left] > threshold:
        left -= 1
    while right < len(col_scores)-1 and col_scores[right] > threshold:
        right += 1

    return right - left + 1


def parabolic_valley_kernel(h=41, w=7):
    y = np.linspace(-1, 1, h)
    curve = y**2
    curve = 2 * (curve - curve.min()) / (curve.max() - curve.min()) - 1
    return np.tile(curve[:, None], (1, w))

def estimate_angle(gray, x_center, step=3):
    h = gray.shape[0]
    col_strip = gray[:, max(0, x_center - 2):min(gray.shape[1], x_center + 3)]
    mean_profile = col_strip.mean(axis=1)
    smoothed = cv2.GaussianBlur(mean_profile, (1, 11), 0)
    y = np.arange(len(smoothed))

    # fit parabolico: y ↦ x(y)
    try:
        popt = np.polyfit(y, smoothed, 2)
        a, b, c = popt
        # larghezza a mezza profondità
        h_depth = (smoothed.max() - smoothed.min()) / 2
        width_est = int(2 * np.sqrt(h_depth / abs(a)))
        width = np.clip(width_est, 7, 50)
    except:
        width = 20  # fallback
        print("⚠️ Fit parabolico fallito, uso width=20")

    # stima inclinazione con nuova width
    x_start = max(0, x_center - width // 2)
    x_end = min(gray.shape[1], x_center + width // 2 + 1)
    roi_strip = gray[:, x_start:x_end]

    xs, ys = [], []
    for y in range(0, h, step):
        col = roi_strip[y, :]
        x_local = np.argmin(col)
        xs.append(x_start + x_local)
        ys.append(y)

    a, b = np.polyfit(ys, xs, 1)
    angle = np.degrees(np.arctan(a))
    return angle, a, b, width


def apply_fold_detector(img, out_path, x0_ratio=0.4, x1_ratio=0.6, debug=False):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    x0, x1 = int(w * x0_ratio), int(w * x1_ratio)
    roi = gray[:, x0:x1]

    kernel = parabolic_valley_kernel(h=41, w=7)
    response = convolve(roi.astype(float), kernel)

    col_scores = response.sum(axis=0)
    best_x_local = np.argmax(col_scores)
    best_x_global = x0 + best_x_local

    angle, a, b, peak_width = estimate_angle(gray, best_x_global, step=3)
    print(f"Peak width stimata da parabola: {peak_width} px")

    vis = img.copy()
    y0, y1 = 0, h
    x0_line = int(a * y0 + b)
    x1_line = int(a * y1 + b)
    cv2.line(vis, (x0_line, y0), (x1_line, y1), (0, 0, 255), 2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, vis)

    print(f"Fold at x ≈ {best_x_global}, inclinazione stimata: {angle:.2f}°")

    if debug:
        debug_dir = out_path.replace(".jpg", "_debug")
        os.makedirs(debug_dir, exist_ok=True)
        norm = cv2.normalize(response, None, 0, 255, cv2.NORM_MINMAX)
        heatmap = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_HOT)
        cv2.imwrite(os.path.join(debug_dir, "response_heatmap.jpg"), heatmap)

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(col_scores)
        ax.set_title("Column scores (response sum)")
        ax.set_xlabel("Column index")
        ax.set_ylabel("Score")
        ax.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(debug_dir, "scores_plot.jpg"))
        plt.close()

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--side", choices=('left', 'right'), default='right')
    p.add_argument("out", nargs='?')
    p.add_argument("--debug", action='store_true')
    args = p.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        raise ValueError(f"Image not found: {args.input}")

    if args.side == 'left':
        x0_ratio = 0
        x1_ratio = 0.2
    else:
        x0_ratio = 0.8
        x1_ratio = 1

    out_path = args.out or "media/kernel_analysis/fold_parabola_detected.jpg"
    apply_fold_detector(img, out_path, x0_ratio=x0_ratio, x1_ratio=x1_ratio, debug=args.debug)

if __name__ == "__main__":
    main()
