import matplotlib.pyplot as plt
import cv2, numpy as np, argparse, os
from scipy.optimize import curve_fit
from scipy.signal import argrelextrema

def parabola(x, a, b, c): return a*x**2 + b*x + c

def detect_fold_hough(img, side, debug=False, debug_dir=None):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)

    h, w = blur.shape
    if side=='right':
        x0, x1 = int(0.8*w), w
    else:
        x0, x1 = 0, int(0.2*w)
    roi = blur[:, x0:x1]

    if debug and debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        rows = np.linspace(0, h-1, num=40, dtype=int)
        x_axis = np.arange(x0, x1)
        tmp = [(r, roi[r, :], roi[r, :].mean()) for r in rows]
        avg_ints = np.array([t[2] for t in tmp])
        mean_int = avg_ints.mean()
        std_int  = avg_ints.std()
        filtered = [prof for (_, prof, avg) in tmp if abs(avg - mean_int) <= 1.5 * std_int]
        if not filtered: filtered = [prof for (_, prof, _) in tmp]

        fig, (ax1, ax2) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [2, 1]}, figsize=(8, 6))
        for prof in filtered:
            ax1.plot(x_axis, prof, color='gray', linewidth=0.5, alpha=0.3)
        arr = np.array(filtered)
        mean_profile = arr.mean(axis=0)
        std_profile  = arr.std(axis=0)
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

        # fit parabolico
        smooth = cv2.GaussianBlur(mean_profile + std_profile, (11, 1), 0).flatten()
        x_min = np.argmin(smooth)
        x_fit = np.arange(max(0, x_min-15), min(len(smooth), x_min+16))
        y_fit = smooth[x_fit]
        popt, _ = curve_fit(parabola, x_fit, y_fit)
        x_refined = -popt[1] / (2 * popt[0])

        # salva debug fit
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(x_axis, mean_profile, label='Mean profile', alpha=0.5)
        ax.plot(x_axis, smooth, label='Smoothed', color='orange')
        ax.axvline(x0 + x_min, color='gray', linestyle='--', label='Min raw')
        ax.axvline(x0 + x_refined, color='red', linestyle='--', label='Min refined')
        ax.plot(x0 + x_fit, parabola(x_fit, *popt), 'r:', label='Parabolic fit')
        ax.set_title('Profile + Fit')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(debug_dir, 'step_min_fit.png'))
        plt.close(fig)
    else:
        mean_profile = roi.mean(axis=0)
        smooth = cv2.GaussianBlur(mean_profile, (11, 1), 0).flatten()
        x_min = np.argmin(smooth)
        x_fit = np.arange(max(0, x_min-15), min(len(smooth), x_min+16))
        y_fit = smooth[x_fit]
        popt, _ = curve_fit(parabola, x_fit, y_fit)
        x_refined = -popt[1] / (2 * popt[0])

    return int(round(x0 + x_refined))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--side", choices=('left','right'), default='right')
    p.add_argument("out", nargs='?')
    p.add_argument("--debug", action='store_true')
    args = p.parse_args()

    img = cv2.imread(args.input)
    debug_dir = None
    if args.debug and args.out:
        base, _ = os.path.splitext(args.out)
        debug_dir = base + "_debug"

    x = detect_fold_hough(img, args.side, debug=args.debug, debug_dir=debug_dir)
    print(x if x else -1)

    if args.out:
        vis = img.copy()
        if x:
            cv2.line(vis, (x,0), (x,img.shape[0]), (0,0,255), 2)
        cv2.imwrite(args.out, vis)

if __name__=="__main__":
    main()
