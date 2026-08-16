"""Generate a benchmark corpus of representative uploads PLUS exact ground-truth masks.

The GT mask is the area that SHOULD be stitched. Deriving it from the same drawing
commands removes all heuristic ambiguity from the fidelity metric.
"""
import os
import cv2
import numpy as np

BASE = os.path.dirname(__file__)
OUT = os.path.join(BASE, "corpus")
GT = os.path.join(BASE, "gt")
os.makedirs(OUT, exist_ok=True)
os.makedirs(GT, exist_ok=True)


def save(name, img, gt):
    cv2.imwrite(os.path.join(OUT, name), img)
    cv2.imwrite(os.path.join(GT, os.path.splitext(name)[0] + ".png"), gt)
    print(f"wrote {name:26s} gt_fg={int((gt > 127).sum()):7d}px")


def curve_pts():
    out = []
    for i in range(300):
        t = i / 299.0
        x = (1 - t) ** 3 * 60 + 3 * (1 - t) ** 2 * t * 250 + 3 * (1 - t) * t * t * 520 + t ** 3 * 740
        y = (1 - t) ** 3 * 400 + 3 * (1 - t) ** 2 * t * 150 + 3 * (1 - t) * t * t * 120 + t ** 3 * 300
        out.append((int(x), int(y)))
    return np.array(out, np.int32)


# 1. Bold flat logo: red annulus + green bar on white
img = np.full((600, 600, 3), 255, np.uint8)
gt = np.zeros((600, 600), np.uint8)
cv2.circle(img, (300, 300), 220, (40, 40, 200), -1)
cv2.circle(img, (300, 300), 150, (255, 255, 255), -1)
cv2.rectangle(img, (240, 100), (360, 500), (30, 160, 30), -1)
cv2.circle(gt, (300, 300), 220, 255, -1)
cv2.circle(gt, (300, 300), 150, 0, -1)
cv2.rectangle(gt, (240, 100), (360, 500), 255, -1)
save("01_bold_logo.png", img, gt)

# 2. Text
img = np.full((400, 900, 3), 255, np.uint8)
gt = np.zeros((400, 900), np.uint8)
cv2.putText(img, "STITCH", (40, 260), cv2.FONT_HERSHEY_DUPLEX, 6.0, (20, 20, 20), 18)
cv2.putText(gt, "STITCH", (40, 260), cv2.FONT_HERSHEY_DUPLEX, 6.0, 255, 18)
save("02_text.png", img, gt)

# 3. Curved swoosh (satin column)
img = np.full((500, 800, 3), 255, np.uint8)
gt = np.zeros((500, 800), np.uint8)
cv2.polylines(img, [curve_pts()], False, (200, 60, 40), 26, cv2.LINE_AA)
cv2.polylines(gt, [curve_pts()], False, 255, 26)
save("03_swoosh.png", img, gt)

# 4. Transparent-background PNG
rgba = np.zeros((600, 600, 4), np.uint8)
cv2.circle(rgba, (300, 300), 200, (60, 60, 220, 255), -1)
cv2.putText(rgba, "A", (215, 400), cv2.FONT_HERSHEY_DUPLEX, 6.0, (255, 255, 255, 255), 20)
gt = (rgba[..., 3] > 127).astype(np.uint8) * 255
save("04_transparent.png", rgba, gt)

# 5. Gradient / photo-like (full-bleed: everything is artwork)
h, w = 500, 500
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
img = np.zeros((h, w, 3), np.uint8)
img[..., 0] = np.clip(80 + 120 * (xx / w), 0, 255)
img[..., 1] = np.clip(60 + 150 * (yy / h), 0, 255)
img[..., 2] = np.clip(200 - 100 * (yy / h), 0, 255)
cv2.circle(img, (250, 250), 150, (40, 90, 190), -1)
img = np.clip(img.astype(np.float32) + np.random.default_rng(0).normal(0, 9, img.shape), 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(OUT, "05_photo_gradient.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 72])
cv2.imwrite(os.path.join(GT, "05_photo_gradient.png"), np.full((h, w), 255, np.uint8))
print("wrote 05_photo_gradient.jpg      gt_fg=full-bleed")

# 6. Thin line art
img = np.full((600, 600, 3), 255, np.uint8)
gt = np.zeros((600, 600), np.uint8)
for c, t in (((30, 30, 30), 5),):
    cv2.circle(img, (300, 300), 200, c, t)
cv2.line(img, (150, 300), (450, 300), (30, 30, 30), 4)
cv2.line(img, (300, 150), (300, 450), (30, 30, 30), 4)
cv2.circle(gt, (300, 300), 200, 255, 5)
cv2.line(gt, (150, 300), (450, 300), 255, 4)
cv2.line(gt, (300, 150), (300, 450), 255, 4)
save("06_lineart.png", img, gt)

# 7. Subject touching the corner
img = np.full((500, 500, 3), 250, np.uint8)
gt = np.zeros((500, 500), np.uint8)
cv2.rectangle(img, (0, 0), (250, 250), (180, 40, 40), -1)
cv2.circle(img, (350, 350), 110, (40, 170, 60), -1)
cv2.rectangle(gt, (0, 0), (250, 250), 255, -1)
cv2.circle(gt, (350, 350), 110, 255, -1)
save("07_corner_subject.png", img, gt)

# 8. Busy striped background — only the blue disc is artwork
img = np.full((500, 500, 3), 255, np.uint8)
gt = np.zeros((500, 500), np.uint8)
for i in range(0, 500, 40):
    cv2.line(img, (0, i), (500, i), (215, 225, 235), 18)
cv2.circle(img, (250, 250), 140, (50, 50, 200), -1)
cv2.circle(gt, (250, 250), 140, 255, -1)
save("08_busy_bg.png", img, gt)
