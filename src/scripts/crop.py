import cv2, numpy as np, argparse, os
from scipy.optimize import curve_fit
import math


def save_jpg(img, out_path, quality=90):
    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])

def resize_width_hd(img, target_width=1920):
    h, w = img.shape[:2]
    scale = target_width / w
    new_h = int(h * scale)
    resized = cv2.resize(img, (target_width, new_h), interpolation=cv2.INTER_AREA)
    return resized

def auto_detect_side(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    margin = 10
    strip_width = 5

    left_strip = gray[:, margin:margin + strip_width]
    right_strip = gray[:, w - margin - strip_width:w - margin]

    left_brightness = np.mean(left_strip)
    right_brightness = np.mean(right_strip)

    if np.abs(left_brightness - right_brightness) < 10:
        return None
    return 'right' if left_brightness < right_brightness else 'left'


def parabola(x, a, b, c): return a*x**2 + b*x + c

def estimate_angle(gray, x_center, step=3):
    h = gray.shape[0]
    col_strip = gray[:, max(0, x_center - 2):min(gray.shape[1], x_center + 3)]
    mean_profile = col_strip.mean(axis=1)
    smoothed = cv2.GaussianBlur(mean_profile, (1, 11), 0)
    y = np.arange(len(smoothed))

    try:
        popt = np.polyfit(y, smoothed, 2)
        a, b, c = popt
        h_depth = (smoothed.max() - smoothed.min()) / 2
        width_est = int(2 * np.sqrt(h_depth / abs(a.item())))
        width = np.clip(width_est, 7, 50)
    except:
        width = 20
        print("⚠️ Fit parabolico fallito, uso width=20")

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

def detect_fold_hough(img, side, debug=False, debug_dir=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)

    h, w = blur.shape
    if side=='right':
        x0, x1 = int(0.8*w), w
    else:
        x0, x1 = 0, int(0.2*w)
    roi = blur[:, x0:x1]

    rows = np.linspace(0, h-1, num=40, dtype=int)
    x_axis = np.arange(x0, x1)
    tmp = [(r, roi[r, :], roi[r, :].mean()) for r in rows]
    avg_ints = np.array([t[2] for t in tmp])
    mean_int = avg_ints.mean()
    std_int  = avg_ints.std()
    filtered = [prof for (_, prof, avg) in tmp if abs(avg - mean_int) <= 1.5 * std_int]
    if not filtered:
        filtered = [prof for (_, prof, _) in tmp]

    arr = np.array(filtered)
    mean_profile = arr.mean(axis=0)
    std_profile  = arr.std(axis=0)
    smooth = cv2.GaussianBlur(mean_profile + std_profile, (11, 1), 0).flatten()
    x_min = np.argmin(smooth)
    x_fit = np.arange(max(0, x_min-15), min(len(smooth), x_min+16))
    y_fit = smooth[x_fit]
    popt, _ = curve_fit(parabola, x_fit, y_fit)
    x_refined = -popt[1] / (2 * popt[0])
    x_final = int(round(x0 + x_refined))

    angle, a, b, width = estimate_angle(gray, x_final, step=3)

    if debug and debug_dir:
        import matplotlib.pyplot as plt  # Import solo se serve
        os.makedirs(debug_dir, exist_ok=True)

        fig, (ax1, ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [2, 1]}, figsize=(8, 6))
        for prof in filtered:
            ax1.plot(x_axis, prof, color='gray', linewidth=0.5, alpha=0.3)
        ax1.errorbar(x_axis, mean_profile, yerr=std_profile, color='red', ecolor='salmon',
                     linewidth=2, elinewidth=1, capsize=2, label='mean ± std')
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
        ax.plot(x_axis, smooth, label='Smoothed', color='orange')
        ax.axvline(x0 + x_min, color='gray', linestyle='--', label='Min raw')
        ax.axvline(x_final, color='red', linestyle='--', label='Min refined')
        ax.plot(x0 + x_fit, parabola(x_fit, *popt), 'r:', label='Parabolic fit')
        ax.set_title('Profile + Fit')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(debug_dir, 'step_min_fit.png'))
        plt.close(fig)

    return x_final, angle, a, b

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--side", choices=('left','right'), default=None)
    p.add_argument("out", nargs='?')
    p.add_argument("--debug", action='store_true')
    args = p.parse_args()

    img = cv2.imread(args.input)
    width = min(1920, img.shape[1])
    quality = 90  # for jpg

    if img is None:
        raise ValueError(f"Image not found: {args.input}")

    debug_dir = None
    if args.debug and args.out:
        base, _ = os.path.splitext(args.out)
        debug_dir = base + "_debug"

    side = auto_detect_side(img) if args.side is None else args.side

    if side not in ('left', 'right'):
        print("Attenzione: Lato della piega non rilevato, salvo originale")
        hd_img = resize_width_hd(img, target_width=width)
        save_jpg(hd_img, args.out, quality=quality)
        return

    x, angle, a, b = detect_fold_hough(img, side, debug=args.debug, debug_dir=debug_dir)
    print(f"x: {x}, inclinazione stimata: {angle:.2f}°")

    h = img.shape[0]
    if args.out:
        if debug_dir:
            vis = img.copy()
            x0_line = int(a * 0 + b)
            x1_line = int(a * h + b)
            cv2.line(vis, (x0_line, 0), (x1_line, h), (0, 0, 255), 2)
            cv2.imwrite(args.out, vis)

        # Crop e rotazione (porta la piega al bordo destro)
        M = cv2.getRotationMatrix2D(center=(x, h//2), angle=-angle, scale=1.0)
        rotated = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        if side == 'right':
            cropped = rotated[:, :x]
        else:
            cropped = rotated[:, x:]

        # ...dopo il crop...
        cropped_hd = resize_width_hd(cropped, target_width=width)
        save_jpg(cropped_hd, args.out, quality=quality)

if __name__=="__main__":
    main()