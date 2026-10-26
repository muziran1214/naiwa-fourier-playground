from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
image_path = ROOT / 'assets' / 'capture_temp.jpg'
data_dir = ROOT / 'output' / 'data'
data_dir.mkdir(parents=True, exist_ok=True)

img_bgr = cv2.imread(str(image_path))
if img_bgr is None:
    raise FileNotFoundError(f"Cannot read reference image: {image_path}")
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
h, w, _ = img_rgb.shape

gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

S = hsv[:, :, 1]
V = hsv[:, :, 2]
Y_grid, X_grid = np.mgrid[0:h, 0:w]
fg_mask = np.where(Y_grid < 745, (S > 22) | (V < 230), (S > 42) | (V < 168)).astype(np.uint8) * 255

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

cnts, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
outer_cnt = max(cnts, key=cv2.contourArea)[:, 0, :].astype(np.float64)

def smooth_closed(pts, win=3):
    pad = np.vstack([pts[-win:], pts, pts[:win]])
    ker = np.ones(2*win+1) / (2*win+1)
    xs = np.convolve(pad[:, 0], ker, mode='valid')
    ys = np.convolve(pad[:, 1], ker, mode='valid')
    return np.column_stack([xs, ys])

outer_cnt = smooth_closed(outer_cnt, win=3)
# Roll outer_cnt so it starts at the top of the head (minimum y)
top_idx = np.argmin(outer_cnt[:, 1])
outer_cnt = np.roll(outer_cnt, -top_idx, axis=0)
# Check direction: we want it to go counter-clockwise (left down forehead -> snout -> mouth -> chest -> belly -> feet -> back -> top)
# At top_idx, if we step +50 indices, does x decrease (going left toward eye/snout) or increase?
if outer_cnt[50, 0] > outer_cnt[0, 0]:
    outer_cnt = outer_cnt[::-1]
    top_idx = np.argmin(outer_cnt[:, 1])
    outer_cnt = np.roll(outer_cnt, -top_idx, axis=0)

print("Start point (top of head):", outer_cnt[0], "Next +50 pt (toward forehead/snout):", outer_cnt[50])

# Internal Canny edges
edges_l = cv2.Canny(cv2.GaussianBlur(lab[:, :, 0], (5, 5), 1.0), 25, 75)
edges_a = cv2.Canny(cv2.GaussianBlur(lab[:, :, 1], (5, 5), 1.0), 15, 45)
edges_b = cv2.Canny(cv2.GaussianBlur(lab[:, :, 2], (5, 5), 1.0), 18, 50)
combined_edges = (edges_l | edges_a | edges_b)

# Cream belly upper arch
belly_region = ((Y_grid > 260) & (Y_grid < 550) & (X_grid > 30) & (X_grid < 310) & (fg_mask > 0))
belly_mask = ((S < 122) & (V > 160) & belly_region).astype(np.uint8) * 255
belly_mask = cv2.morphologyEx(belly_mask, cv2.MORPH_OPEN, kernel, iterations=2)
belly_mask = cv2.morphologyEx(belly_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
belly_edges = cv2.Canny(belly_mask, 50, 150)
belly_arch_mask = ((Y_grid > 265) & (Y_grid < 405) & (X_grid > 85) & (X_grid < 255)).astype(np.uint8)
belly_arch_edges = belly_edges & (belly_arch_mask * 255)

outer_edge_mask = np.zeros((h, w), dtype=np.uint8)
cv2.polylines(outer_edge_mask, [outer_cnt.astype(np.int32)], True, 255, thickness=9)
internal_edges = ((combined_edges | belly_arch_edges) & (fg_mask > 0) & (outer_edge_mask == 0))

num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(internal_edges, connectivity=8)
internal_loops = []
for lbl in range(1, num_labels):
    if stats[lbl, cv2.CC_STAT_AREA] < 16:
        continue
    comp_mask = (labels == lbl).astype(np.uint8) * 255
    sub_cnts, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for sc in sub_cnts:
        if len(sc) >= 20:
            pts = sc[:, 0, :].astype(np.float64)
            pts = smooth_closed(pts, win=2)
            internal_loops.append(pts)

# Stitch internal loops into main_tour
main_tour = outer_cnt.copy()
is_bridge = np.zeros(len(main_tour), dtype=bool)

remaining = list(range(len(internal_loops)))
while remaining:
    best_dist = 1e9
    best_rem_idx = -1
    best_tour_pt_idx = -1
    best_loop_pt_idx = -1
    step = max(1, len(main_tour) // 1000)
    tour_sub = main_tour[::step]
    for r_i in remaining:
        loop = internal_loops[r_i]
        dmat = cdist(tour_sub, loop)
        min_flat = np.argmin(dmat)
        t_sub_i, l_i = np.unravel_index(min_flat, dmat.shape)
        dist = dmat[t_sub_i, l_i]
        if dist < best_dist:
            best_dist = dist
            best_rem_idx = r_i
            best_tour_pt_idx = t_sub_i * step
            best_loop_pt_idx = l_i
    loop = internal_loops[best_rem_idx]
    pt_l = loop[best_loop_pt_idx]
    win_start = max(0, best_tour_pt_idx - step)
    win_end = min(len(main_tour), best_tour_pt_idx + step + 1)
    local_dists = np.linalg.norm(main_tour[win_start:win_end] - pt_l, axis=1)
    best_tour_pt_idx = win_start + np.argmin(local_dists)
    pt_t = main_tour[best_tour_pt_idx]

    rolled_loop = np.roll(loop, -best_loop_pt_idx, axis=0)
    rolled_loop = np.vstack([rolled_loop, rolled_loop[0:1]])

    n_bridge = max(2, int(np.ceil(best_dist / 1.5)))
    bridge_out = np.linspace(pt_t, pt_l, n_bridge, endpoint=False)[1:]
    bridge_back = np.linspace(pt_l, pt_t, n_bridge, endpoint=False)[1:]

    inserted_pts = np.vstack([bridge_out, rolled_loop, bridge_back])
    inserted_flags = np.concatenate([
        np.ones(len(bridge_out), dtype=bool),
        np.zeros(len(rolled_loop), dtype=bool),
        np.ones(len(bridge_back), dtype=bool)
    ])

    main_tour = np.vstack([main_tour[:best_tour_pt_idx+1], inserted_pts, main_tour[best_tour_pt_idx+1:]])
    is_bridge = np.concatenate([is_bridge[:best_tour_pt_idx+1], inserted_flags, is_bridge[best_tour_pt_idx+1:]])
    remaining.remove(best_rem_idx)

diffs = np.diff(np.vstack([main_tour, main_tour[0:1]]), axis=0)
seg_lens = np.linalg.norm(diffs, axis=1)
cum_len = np.concatenate([[0], np.cumsum(seg_lens)])
total_len = cum_len[-1]

N = 4096
target_s = np.linspace(0, total_len, N, endpoint=False)
tour_closed = np.vstack([main_tour, main_tour[0:1]])
ux = np.interp(target_s, cum_len, tour_closed[:, 0])
uy = np.interp(target_s, cum_len, tour_closed[:, 1])
ubridge = np.interp(target_s, cum_len[:-1], is_bridge.astype(float)) > 0.3

# Find progress t in [0, 1] for key landmarks:
landmarks = {
    'Top of Head': (185, 65),
    'Eye & Pupil': (163, 112),
    'Mouth': (120, 160),
    'Cream Belly & Left Hand': (50, 415),
    'Right Hand & Arm': (155, 430),
    'Lower Belly Fold': (160, 585),
    'Left Webbed Foot': (85, 735),
    'Right Webbed Foot': (245, 775),
    'Mid Back Curve': (375, 430),
}
for name, (lx, ly) in landmarks.items():
    d = np.hypot(ux - lx, uy - ly)
    idx = np.argmin(d)
    print(f"Landmark {name:25s}: t = {idx/N:.3f} (x={ux[idx]:.1f}, y={uy[idx]:.1f})")

tour_path = data_dir / 'naiwa_tour_data.npz'
np.savez(tour_path,
         ux=ux, uy=uy, ubridge=ubridge, w=w, h=h)
print(f"Saved tour data -> {tour_path}")
