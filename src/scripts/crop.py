import sys
import cv2
from PIL import Image
import numpy as np

def load_image(input_path):
    pil_image = Image.open(input_path).convert('RGB')
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

def find_largest_contour(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    return largest, area

def crop_and_warp(image, contour):
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    box = box.astype("float32")
    W, H = cv2.boundingRect(box)[2:]
    dst_pts = cv2.boxPoints(((W/2, H/2), (W, H), 0))
    M = cv2.getPerspectiveTransform(box, dst_pts)
    warped = cv2.warpPerspective(image, M, (W, H))
    return warped

def crop_image(input_path, output_path, min_area=200000):
    try:
        image = load_image(input_path)
    except Exception as e:
        return False, f"Failed to load image: {e}"

    contour, area = find_largest_contour(image)
    if contour is None:
        return False, "No contours found"

    warped = crop_and_warp(image, contour)
    cv2.imwrite(output_path, warped)

    if area < min_area:
        return False, f"Contour too small ({area} < {min_area})"
    return True, None

def main_worker():
    if len(sys.argv) < 3:
        print("Usage: python crop.py input output [min_area]", file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1:3]
    min_area = int(sys.argv[3]) if len(sys.argv) > 3 else 200000

    ok, msg = crop_image(input_path, output_path, min_area)
    if not ok:
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)

if __name__ == "__main__":
    main_worker()