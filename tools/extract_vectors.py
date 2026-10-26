from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
image_path = ROOT / 'assets' / 'capture_temp.jpg'
diagnostics_dir = ROOT / 'output' / 'diagnostics'
diagnostics_dir.mkdir(parents=True, exist_ok=True)

img_bgr = cv2.imread(str(image_path))
if img_bgr is None:
    raise FileNotFoundError(f"Cannot read reference image: {image_path}")
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
h, w, _ = img_rgb.shape

gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

# 1. Clean foreground mask without floor shadow:
# Notice floor shadow is at y > 740 and has very low saturation (S < 35) and high value (V > 180)
S = hsv[:, :, 1]
V = hsv[:, :, 2]
# For y <= 740, V < 240 or S > 20 is frog. For y > 740, the feet are dark olive-brown (V < 175 or S > 45).
Y_grid, X_grid = np.mgrid[0:h, 0:w]
fg_mask = np.where(Y_grid < 745, (S > 22) | (V < 230), (S > 42) | (V < 168)).astype(np.uint8) * 255

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

# Extract outer silhouette
cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
outer_cnt = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)

# Smooth outer contour slightly
def smooth_closed(pts, win=5):
    pad = np.vstack([pts[-win:], pts, pts[:win]])
    ker = np.ones(2*win+1) / (2*win+1)
    xs = np.convolve(pad[:, 0], ker, mode='valid')
    ys = np.convolve(pad[:, 1], ker, mode='valid')
    return np.column_stack([xs, ys])

outer_cnt = smooth_closed(outer_cnt, win=3)

# 2. Internal Canny edges (eye, pupil, mouth, hands/fingers, belly crease, toes)
edges_l = cv2.Canny(cv2.GaussianBlur(lab[:, :, 0], (5, 5), 1.0), 25, 75)
edges_a = cv2.Canny(cv2.GaussianBlur(lab[:, :, 1], (5, 5), 1.0), 15, 45)
edges_b = cv2.Canny(cv2.GaussianBlur(lab[:, :, 2], (5, 5), 1.0), 18, 50)
combined_edges = (edges_l | edges_a | edges_b)

# Also detect the soft cream belly boundary (upper arch from chest to right armpit)
# In HSV, yellow body has S around 140-190, while cream belly has S around 70-115
belly_region = np.zeros_like(S)
belly_region[(Y_grid > 260) & (Y_grid < 530) & (X_grid > 30) & (X_grid < 310) & (fg_mask > 0)] = 1
belly_mask = ((S < 122) & (V > 160) & (belly_region > 0)).astype(np.uint8) * 255
belly_mask = cv2.morphologyEx(belly_mask, cv2.MORPH_OPEN, kernel, iterations=2)
belly_mask = cv2.morphologyEx(belly_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
belly_edges = cv2.Canny(belly_mask, 50, 150)
# Keep only the upper-right arch of the cream belly (above the arm, y < 410, x > 80)
belly_arch_mask = ((Y_grid > 265) & (Y_grid < 405) & (X_grid > 85) & (X_grid < 255)).astype(np.uint8)
belly_arch_edges = belly_edges & (belly_arch_mask * 255)

# Mask internal edges so we don't duplicate outer_cnt
outer_edge_mask = np.zeros((h, w), dtype=np.uint8)
cv2.polylines(outer_edge_mask, [outer_cnt.astype(np.int32)], True, 255, thickness=9)
internal_edges = ((combined_edges | belly_arch_edges) & (fg_mask > 0) & (outer_edge_mask == 0))

# Find connected components / contours of internal edges
num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(internal_edges, connectivity=8)
internal_segments = []
for lbl in range(1, num_labels):
    if stats[lbl, cv2.CC_STAT_AREA] < 12:
        continue
    comp_mask = (labels == lbl).astype(np.uint8) * 255
    sub_cnts, _ = cv2.findContours(comp_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for sc in sub_cnts:
        if len(sc) >= 15:
            pts = sc[:, 0, :].astype(np.float64)
            internal_segments.append(pts)

print(f"Outer contour points: {len(outer_cnt)}, internal segments: {len(internal_segments)}")

# Visualize extracted segments
fig, axes = plt.subplots(1, 3, figsize=(15, 8))
axes[0].imshow(img_rgb)
axes[0].set_title("Reference Image")
axes[1].imshow(np.ones_like(img_rgb)*255)
axes[1].plot(outer_cnt[:, 0], outer_cnt[:, 1], color='#3D3210', lw=2.0)
for seg in internal_segments:
    axes[1].plot(seg[:, 0], seg[:, 1], color='#C88A14', lw=1.5)
axes[1].set_title(f"Extracted Vector Contours (1 outer + {len(internal_segments)} inner)")
axes[2].imshow(img_rgb, alpha=0.35)
axes[2].plot(outer_cnt[:, 0], outer_cnt[:, 1], color='#3D3210', lw=2.0)
for seg in internal_segments:
    axes[2].plot(seg[:, 0], seg[:, 1], color='#D9381E', lw=1.5)
axes[2].set_title("Overlay on Reference")
for ax in axes:
    ax.axis('off')
plt.tight_layout()
output_path = diagnostics_dir / 'vector_segments.png'
plt.savefig(output_path, dpi=150)
plt.close(fig)
print(f"Saved vector segments -> {output_path}")
