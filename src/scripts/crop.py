import sys
import cv2
from PIL import Image
import numpy as np

if len(sys.argv) < 3:
    print("Usage: python crop.py input output [min_area]", file=sys.stderr)
    sys.exit(1)

input_path, output_path = sys.argv[1:3]
min_area = int(sys.argv[3]) if len(sys.argv) > 3 else 200000

# Usa PIL per leggere anche webp, poi passa a OpenCV
try:
    pil_image = Image.open(input_path).convert('RGB')
    image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
except Exception as e:
    print(f"Failed to load image: {e}", file=sys.stderr)
    sys.exit(2)

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
edges = cv2.Canny(blurred, 50, 150)

contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if not contours:
    print("No contours found", file=sys.stderr)
    sys.exit(2)

largest = max(contours, key=cv2.contourArea)
area = cv2.contourArea(largest)

# Mostra il crop anche se troppo piccolo
rect = cv2.minAreaRect(largest)
box = cv2.boxPoints(rect)
box = box.astype("float32")

W, H = cv2.boundingRect(box)[2:]
dst_pts = cv2.boxPoints(((W/2, H/2), (W, H), 0))
M = cv2.getPerspectiveTransform(box, dst_pts)
warped = cv2.warpPerspective(image, M, (W, H))

# Salva comunque il crop in output_path (anche se troppo piccolo)
cv2.imwrite(output_path, warped)

if area < min_area:
    print(f"Contour too small ({area} < {min_area})", file=sys.stderr)
    sys.exit(2)

sys.exit(0)