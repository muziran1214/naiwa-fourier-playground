from pathlib import Path
import shutil
import subprocess
import time
import cv2
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image, ImageDraw, ImageFont

t0_start = time.time()

ROOT = Path(__file__).resolve().parents[1]
output_dir = ROOT / 'output'
data_dir = output_dir / 'data'
preview_dir = output_dir / 'previews'
image_path = ROOT / 'assets' / 'capture_temp.jpg'
tour_path = data_dir / 'naiwa_tour_data.npz'
sync_path = data_dir / 'audio_sync_features.npz'
wav_path = output_dir / 'audio' / 'naiwa_soundtrack.wav'
ffmpeg_path = shutil.which('ffmpeg')
if ffmpeg_path is None:
    raise FileNotFoundError("FFmpeg was not found on PATH. See docs/USAGE.md.")
for input_path, preparation in [
    (image_path, "Restore assets/capture_temp.jpg."),
    (tour_path, "Run scripts/prepare_tour_data.py first."),
    (sync_path, "Run scripts/generate_soundtrack.py first."),
    (wav_path, "Run scripts/generate_soundtrack.py first."),
]:
    if not input_path.is_file():
        raise FileNotFoundError(f"Missing input: {input_path}. {preparation}")
preview_dir.mkdir(parents=True, exist_ok=True)

# 1. Load Reference Image & Tour Data & 4-Act Audio + Laugh Rig Features
img_bgr = cv2.imread(str(image_path))
if img_bgr is None:
    raise ValueError(f"Cannot decode reference image: {image_path}")
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
ref_h, ref_w, _ = img_rgb.shape

tour_data = np.load(tour_path)
ux = tour_data['ux']
uy = tour_data['uy']
ubridge = tour_data['ubridge']
N = len(ux)

audio_sync = np.load(sync_path)
frame_rms = audio_sync['frame_rms']
frame_spec = audio_sync['frame_spec']
FPS = int(audio_sync['fps'])
N_FRAMES = int(audio_sync['n_frames'])  # 864 frames = 28.8s at 30 fps
DURATION = N_FRAMES / FPS

laugh_mouth = audio_sync['laugh_mouth']
laugh_squint = audio_sync['laugh_squint']
laugh_lean = audio_sync['laugh_lean']
laugh_head = audio_sync['laugh_head']
laugh_belly_inf = audio_sync['laugh_belly_inf']
laugh_belly_dy = audio_sync['laugh_belly_dy']
laugh_hand = audio_sync['laugh_hand']
laugh_bounce = audio_sync['laugh_bounce']

# 2. Setup 720x1280 Studio Portrait Canvas (9:16 HD vertical)
W, H = 720, 1280
SCALE_REF = 1.16
scaled_w = int(round(ref_w * SCALE_REF))
scaled_h = int(round(ref_h * SCALE_REF))
X_OFF = (W - scaled_w) // 2
Y_OFF = 138

cx_canvas = X_OFF + scaled_w / 2.0
cy_canvas = Y_OFF + scaled_h / 2.0
tx = ux * SCALE_REF + X_OFF
ty = uy * SCALE_REF + Y_OFF

# Compute exact DFT via FFT
z_tour = (tx - cx_canvas) + 1j * (ty - cy_canvas)
coeffs = np.fft.fft(z_tour) / N
freqs = np.fft.fftfreq(N) * N

dc_mask = (freqs == 0)
dc_coeff = coeffs[dc_mask][0]
non_dc_coeffs = coeffs[~dc_mask]
non_dc_freqs = freqs[~dc_mask]
order = np.argsort(np.abs(non_dc_coeffs))[::-1]

MAX_M = 750
coeffs_sorted = np.concatenate([[dc_coeff], non_dc_coeffs[order[:MAX_M-1]]])
freqs_sorted = np.concatenate([[0.0], non_dc_freqs[order[:MAX_M-1]]])
radii_sorted = np.abs(coeffs_sorted)

SHIFT = 4
SCALE_FP = 1 << SHIFT

act1_M_steps = [4, 10, 24, 65, 180, 750]
u_grid = np.linspace(0, 1, 1024, endpoint=False)
act1_closed_curves_fp = {}
phase_mat_1024 = np.exp(1j * 2 * np.pi * np.outer(u_grid, freqs_sorted))
for m_val in act1_M_steps:
    z_c = phase_mat_1024[:, :m_val] @ coeffs_sorted[:m_val]
    pts_c = np.column_stack([z_c.real + cx_canvas, z_c.imag + cy_canvas])
    act1_closed_curves_fp[m_val] = (pts_c * SCALE_FP).astype(np.int32)

u_dense = np.linspace(0, 1, N, endpoint=False)
coeffs_filtered = np.zeros_like(coeffs)
coeffs_filtered[dc_mask] = dc_coeff
orig_non_dc_indices = np.where(~dc_mask)[0][order[:MAX_M-1]]
coeffs_filtered[orig_non_dc_indices] = non_dc_coeffs[order[:MAX_M-1]]
z_full_rec = np.fft.ifft(coeffs_filtered * N)
rec_x = z_full_rec.real + cx_canvas
rec_y = z_full_rec.imag + cy_canvas
rec_pts = np.column_stack([rec_x, rec_y])
rec_pts_fp = (rec_pts * SCALE_FP).astype(np.int32)

# 3. Build Studio Reference Layers
ref_scaled = cv2.resize(img_rgb, (scaled_w, scaled_h), interpolation=cv2.INTER_LANCZOS4)

Y_c, X_c = np.mgrid[0:H, 0:W]
dist_center = np.hypot((X_c - W/2.0) / (W*0.65), (Y_c - H*0.48) / (H*0.58))
vig = np.clip(1.0 - 0.065 * (dist_center**1.6), 0.91, 1.0)
studio_bg = np.zeros((H, W, 3), dtype=np.uint8)
studio_bg[:, :, 0] = np.clip(253 * vig, 232, 254).astype(np.uint8)
studio_bg[:, :, 1] = np.clip(251 * vig, 228, 252).astype(np.uint8)
studio_bg[:, :, 2] = np.clip(245 * vig, 216, 248).astype(np.uint8)

grid_mask = ((X_c % 36 == 0) & (Y_c % 36 == 0) & (Y_c > 125) & (Y_c < 1115))
studio_bg[grid_mask] = np.array([228, 222, 206], dtype=np.uint8)

hsv_scaled = cv2.cvtColor(cv2.cvtColor(ref_scaled, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
S_sc = hsv_scaled[:, :, 1].astype(np.float32)
V_sc = hsv_scaled[:, :, 2].astype(np.float32)
Y_sc, X_sc = np.mgrid[0:scaled_h, 0:scaled_w]

frog_alpha = np.clip(np.maximum((S_sc - 15.0) / 30.0, (244.0 - V_sc) / 28.0), 0.0, 1.0)
frog_alpha = cv2.GaussianBlur(frog_alpha, (7, 7), 1.5)
body_only_mask = np.where(Y_sc < 745 * SCALE_REF, (S_sc > 20) | (V_sc < 232), (S_sc > 40) | (V_sc < 170)).astype(np.uint8) * 255
body_only_mask = cv2.morphologyEx(body_only_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
body_alpha = cv2.GaussianBlur(body_only_mask.astype(np.float32) / 255.0, (9, 9), 2.0)

full_ref_canvas = studio_bg.copy()
roi_bg = studio_bg[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w].astype(np.float32)
blended_roi = ref_scaled.astype(np.float32) * frog_alpha[:, :, None] + roi_bg * (1.0 - frog_alpha[:, :, None])
full_ref_canvas[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w] = np.clip(blended_roi, 0, 255).astype(np.uint8)
roi_ref_u16 = full_ref_canvas[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w].astype(np.uint16)
roi_bg_u16 = studio_bg[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w].astype(np.uint16)

tree = cKDTree(np.column_stack([tx[~ubridge] - X_OFF, ty[~ubridge] - Y_OFF]))
u_non_bridge = u_dense[~ubridge]
roi_coords = np.column_stack([X_sc.ravel(), Y_sc.ravel()])
dists_to_tour, idxs_to_tour = tree.query(roi_coords, k=1)
nearest_u_roi = u_non_bridge[idxs_to_tour].reshape(scaled_h, scaled_w)
dist_to_tour_roi = dists_to_tour.reshape(scaled_h, scaled_w)
nearest_u_smooth = cv2.GaussianBlur(nearest_u_roi.astype(np.float32), (45, 45), 14.0)
effective_u_roi = np.where(dist_to_tour_roi < 55.0, nearest_u_roi, nearest_u_smooth)
effective_u_roi = cv2.GaussianBlur(effective_u_roi.astype(np.float32), (21, 21), 6.0)
dist_from_top_roi = (np.hypot(X_sc - scaled_w*0.45, Y_sc - scaled_h*0.1) / (scaled_h * 0.95)).astype(np.float32)

# Precompute local stroke colors & chunks
stroke_colors_N = np.zeros((N, 3), dtype=np.uint8)
for i in range(N):
    px = int(np.clip(ux[i] * SCALE_REF, 0, scaled_w - 1))
    py = int(np.clip(uy[i] * SCALE_REF, 0, scaled_h - 1))
    x0, x1 = max(0, px-3), min(scaled_w, px+4)
    y0, y1 = max(0, py-3), min(scaled_h, py+4)
    patch = ref_scaled[y0:y1, x0:x1].astype(np.float32)
    mean_rgb = np.mean(patch, axis=(0, 1))
    stroke_colors_N[i] = np.clip(mean_rgb * 0.42 + np.array([38, 28, 8]), 18, 165).astype(np.uint8)

contour_chunks = []
i_s = 0
while i_s < N - 1:
    if ubridge[i_s]:
        i_s += 1
        continue
    i_e = i_s + 1
    while i_e < N and (not ubridge[i_e]) and (i_e - i_s < 48):
        i_e += 1
    col = tuple(int(c) for c in stroke_colors_N[(i_s + i_e) // 2])
    contour_chunks.append((i_s, i_e, col, rec_pts_fp[i_s:i_e+1]))
    i_s = i_e

# 4. 3D Belly-Laugh Character Rig Function (operates at native 443x836 for speed & crispness, then scales to ROI!)
Y_base, X_base = np.mgrid[0:ref_h, 0:ref_w].astype(np.float32)

def render_laughing_naiwa_roi(
    mouth_open=0.0,
    eye_squint=0.0,
    lean_back_deg=0.0,
    head_tilt_deg=0.0,
    belly_inflate=0.0,
    belly_dy=0.0,
    hand_pat=0.0,
    body_bounce_y=0.0,
    tongue_wave=0.0,
    tear_prog=-1.0
):
    canvas = img_rgb.copy()

    # A. Canonical Jaw Drop & Cheek Raise
    if mouth_open > 0.008 or eye_squint > 0.008:
        jaw_drop_px = 36.0 * (mouth_open ** 0.82)
        cheek_raise_px = 7.5 * eye_squint

        wx_jaw = np.exp(-((X_base - 130.0) / 44.0) ** 2) * (X_base < 198)
        wy_jaw = np.clip((Y_base - 150.0) / 7.5, 0.0, 1.0) * np.exp(-np.maximum(0.0, Y_base - 165.0) / 48.0)
        w_jaw = wx_jaw * wy_jaw

        wx_ulip = np.exp(-((X_base - 126.0) / 34.0) ** 2)
        wy_ulip = np.exp(-((Y_base - 144.0) / 14.0) ** 2) * (Y_base <= 153.0)
        w_ulip = wx_ulip * wy_ulip

        wx_cheek = np.exp(-((X_base - 165.0) / 28.0) ** 2)
        wy_cheek = np.exp(-((Y_base - 134.0) / 14.0) ** 2)
        w_cheek = wx_cheek * wy_cheek

        map_x_face = (X_base - 4.5 * mouth_open * w_jaw).astype(np.float32)
        map_y_face = (Y_base
                      - jaw_drop_px * w_jaw
                      + 5.5 * mouth_open * w_ulip
                      + cheek_raise_px * w_cheek).astype(np.float32)

        canvas = cv2.remap(canvas, map_x_face, map_y_face, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # B. 3D-Shaded Roaring Laugh Mouth Cavity & Tongue
    if mouth_open > 0.025:
        jaw_drop_px = 36.0 * (mouth_open ** 0.82)
        ulip_lift = 5.0 * mouth_open
        x_left = 107.5
        x_right = 148.0 + 16.0 * mouth_open
        y_corner = 150.5 - 6.5 * mouth_open

        n_pts = 44
        xs_m = np.linspace(x_left, x_right, n_pts)
        u_m = (xs_m - x_left) / (x_right - x_left)

        ys_upper = (151.0 - ulip_lift * np.sin(np.pi * u_m * 0.85)) * (1.0 - u_m) + y_corner * u_m
        bowl_profile = np.sin(np.pi * (u_m ** 0.72))
        ys_lower = ys_upper + (jaw_drop_px + 6.5 * mouth_open) * bowl_profile

        mouth_poly = np.vstack([
            np.column_stack([xs_m, ys_upper]),
            np.column_stack([xs_m[::-1], ys_lower[::-1]])
        ])

        rx0, ry0, rx1, ry1 = 92, 126, 182, 215
        SS = 4
        roi_w, roi_h = rx1 - rx0, ry1 - ry0
        roi_ss = cv2.resize(canvas[ry0:ry1, rx0:rx1], (roi_w * SS, roi_h * SS), interpolation=cv2.INTER_CUBIC)

        poly_ss = ((mouth_poly - np.array([rx0, ry0])) * SS).astype(np.int32)
        mouth_mask_ss = np.zeros((roi_h * SS, roi_w * SS), dtype=np.uint8)
        cv2.fillPoly(mouth_mask_ss, [poly_ss], 255, lineType=cv2.LINE_AA)

        lip_rim_ss = cv2.dilate(mouth_mask_ss, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        lip_rim_blur = cv2.GaussianBlur(lip_rim_ss.astype(np.float32) / 255.0, (9, 9), 2.5)

        roi_f = roi_ss.astype(np.float32)
        rim_only = np.clip(lip_rim_blur - (mouth_mask_ss.astype(np.float32) / 255.0), 0.0, 1.0)
        roi_f = roi_f * (1.0 - 0.42 * rim_only[:, :, None]) + np.array([150.0, 112.0, 28.0]) * (0.42 * rim_only[:, :, None])

        Y_m, X_m = np.mgrid[0:roi_h*SS, 0:roi_w*SS].astype(np.float32) / SS
        cav_depth = np.clip((Y_m - (148 - ry0)) / 34.0, 0.0, 1.0)
        cav_rgb = np.zeros_like(roi_f)
        cav_rgb[:, :, 0] = 64.0 + 38.0 * cav_depth
        cav_rgb[:, :, 1] = 20.0 + 16.0 * cav_depth
        cav_rgb[:, :, 2] = 18.0 + 14.0 * cav_depth

        tongue_cx = (133.0 - rx0) + 2.0 * np.sin(tongue_wave)
        tongue_cy = (151.0 + jaw_drop_px * 0.76 - ry0) + 1.5 * np.cos(tongue_wave)
        tongue_rx = 19.5 * mouth_open
        tongue_ry = 11.5 * mouth_open
        t_dist = np.hypot((X_m - tongue_cx) / max(1.0, tongue_rx), (Y_m - tongue_cy) / max(1.0, tongue_ry))
        tongue_mask = np.clip((1.0 - t_dist) * 4.0, 0.0, 1.0)
        t_highlight = np.exp(-((X_m - (tongue_cx - 3.5))**2 + (Y_m - (tongue_cy - 3.0))**2) / 24.0)
        tongue_rgb = np.zeros_like(roi_f)
        tongue_rgb[:, :, 0] = 222.0 + 30.0 * t_highlight
        tongue_rgb[:, :, 1] = 98.0 + 52.0 * t_highlight
        tongue_rgb[:, :, 2] = 92.0 + 48.0 * t_highlight

        cav_rgb = cav_rgb * (1.0 - tongue_mask[:, :, None]) + tongue_rgb * tongue_mask[:, :, None]

        ulip_ao = np.exp(-np.maximum(0.0, Y_m - (149.0 - ry0)) / 5.0) * 0.55
        cav_rgb *= (1.0 - ulip_ao[:, :, None])

        m_alpha = cv2.GaussianBlur(mouth_mask_ss.astype(np.float32) / 255.0, (5, 5), 1.2)
        roi_f = roi_f * (1.0 - m_alpha[:, :, None]) + cav_rgb * m_alpha[:, :, None]

        roi_out_ss = np.clip(roi_f, 0, 255).astype(np.uint8)
        cx_dimple = int((x_right + 1 - rx0) * SS)
        cy_dimple = int((y_corner - ry0) * SS)
        cv2.ellipse(roi_out_ss, (cx_dimple, cy_dimple), (10, 16), -25, -70, 75, (142, 104, 26), thickness=3, lineType=cv2.LINE_AA)

        canvas[ry0:ry1, rx0:rx1] = cv2.resize(roi_out_ss, (roi_w, roi_h), interpolation=cv2.INTER_AREA)

    # C. 3D Sage-Green Squinted Laughing Eyes ("眼睛眯成一条缝")
    if eye_squint > 0.04:
        ex0, ey0, ex1, ey1 = 138, 88, 194, 140
        SS = 4
        ew, eh = ex1 - ex0, ey1 - ey0
        eroi_ss = cv2.resize(canvas[ey0:ey1, ex0:ex1], (ew * SS, eh * SS), interpolation=cv2.INTER_CUBIC).astype(np.float32)
        Ye, Xe = np.mgrid[0:eh*SS, 0:ew*SS].astype(np.float32) / SS
        Ye += ey0
        Xe += ex0

        ecx, ecy, erx, ery = 165.0, 113.5, 21.5, 19.5
        edist = np.hypot((Xe - ecx) / erx, (Ye - ecy) / ery)
        eye_ball_mask = np.clip((1.0 - edist) * 3.5, 0.0, 1.0)

        nx_e = (Xe - ecx) / erx
        ny_e = (Ye - ecy) / ery
        light_e = np.clip(0.55 - 0.35 * nx_e - 0.45 * ny_e, 0.0, 1.0)
        lid_rgb = np.zeros_like(eroi_ss)
        lid_rgb[:, :, 0] = 105.0 + 78.0 * light_e
        lid_rgb[:, :, 1] = 142.0 + 68.0 * light_e
        lid_rgb[:, :, 2] = 84.0 + 64.0 * light_e

        arch_y = ecy - 3.0 * eye_squint + 0.026 * ((Xe - ecx) ** 2)
        half_open = ery * (1.0 - 0.95 * (eye_squint ** 0.8))
        dist_from_slit = np.abs(Ye - arch_y)
        lid_cover = np.clip((dist_from_slit - half_open + 1.5) / 1.8, 0.0, 1.0) * eye_ball_mask

        eroi_ss = eroi_ss * (1.0 - lid_cover[:, :, None]) + lid_rgb * lid_cover[:, :, None]

        if eye_squint > 0.35:
            crease_w = np.clip((eye_squint - 0.35) / 0.45, 0.0, 1.0)
            crease_mask = np.exp(-((Ye - arch_y) / 1.45) ** 2) * np.clip(1.0 - ((Xe - ecx) / (erx * 0.88)) ** 2, 0.0, 1.0) * crease_w
            crease_rgb = np.array([38.0, 48.0, 22.0])
            eroi_ss = eroi_ss * (1.0 - 0.88 * crease_mask[:, :, None]) + crease_rgb * (0.88 * crease_mask[:, :, None])

        canvas[ey0:ey1, ex0:ex1] = cv2.resize(np.clip(eroi_ss, 0, 255).astype(np.uint8), (ew, eh), interpolation=cv2.INTER_AREA)

        # Far-side left eye pupil only (where RED channel < 95!)
        lx0, ly0, lx1, ly1 = 112, 107, 121, 127
        l_roi = canvas[ly0:ly1, lx0:lx1].astype(np.float32)
        dark_pupil_mask = np.clip((95.0 - l_roi[:, :, 0]) / 40.0, 0.0, 1.0) * eye_squint
        l_lid = np.array([138.0, 168.0, 102.0])
        canvas[ly0:ly1, lx0:lx1] = np.clip(
            l_roi * (1.0 - dark_pupil_mask[:, :, None]) + l_lid * dark_pupil_mask[:, :, None],
            0, 255
        ).astype(np.uint8)

    # D. Sparkling Tear of Joy Droplets
    if tear_prog >= 0.0:
        for t_offset in [0.0, 0.5]:
            tp = (tear_prog + t_offset) % 1.0
            drop_x = int(185.0 + 34.0 * tp)
            drop_y = int(117.0 - 8.0 * tp + 36.0 * (tp ** 2))
            drop_r = max(2, int(5.5 * (1.0 - 0.45 * tp)))
            cv2.circle(canvas, (drop_x, drop_y), drop_r + 1, (135, 192, 232), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (drop_x, drop_y), drop_r, (215, 245, 255), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (drop_x - 1, drop_y - 1), max(1, drop_r // 2), (255, 255, 255), -1, lineType=cv2.LINE_AA)

    # E. Global Skeletal & Belly-Jiggle Mesh Deformation
    hip_x, hip_y = 215.0, 590.0
    w_spine = np.clip((680.0 - Y_base) / 220.0, 0.0, 1.0) ** 1.25
    theta_rad = -np.deg2rad(lean_back_deg) * w_spine

    neck_x, neck_y = 195.0, 225.0
    w_head = np.clip((255.0 - Y_base) / 70.0, 0.0, 1.0) ** 1.35
    theta_head_rad = -np.deg2rad(head_tilt_deg) * w_head

    w_bounce = np.clip((730.0 - Y_base) / 160.0, 0.0, 1.0)

    cos_s = np.cos(theta_rad)
    sin_s = np.sin(theta_rad)
    rx_s = X_base - hip_x
    ry_s = (Y_base + body_bounce_y * w_bounce) - hip_y
    x_s = hip_x + rx_s * cos_s - ry_s * sin_s
    y_s = hip_y + rx_s * sin_s + ry_s * cos_s

    cos_h = np.cos(theta_head_rad)
    sin_h = np.sin(theta_head_rad)
    rx_h = x_s - neck_x
    ry_h = y_s - neck_y
    x_sh = neck_x + rx_h * cos_h - ry_h * sin_h
    y_sh = neck_y + rx_h * sin_h + ry_h * cos_h

    bcx, bcy = 135.0, 425.0
    b_dist2 = ((x_sh - bcx) / 122.0) ** 2 + ((y_sh - bcy) / 138.0) ** 2
    w_belly = np.exp(-b_dist2 * 1.3)
    x_sh = x_sh - (x_sh - bcx) * (0.11 * belly_inflate) * w_belly + 8.0 * belly_inflate * w_belly
    y_sh = y_sh - belly_dy * w_belly

    w_rhand = np.exp(-(((x_sh - 125.0) / 58.0) ** 2 + ((y_sh - 435.0) / 50.0) ** 2))
    w_lhand = np.exp(-(((x_sh - 45.0) / 38.0) ** 2 + ((y_sh - 430.0) / 45.0) ** 2))
    x_sh = x_sh - hand_pat * 7.5 * w_rhand + hand_pat * 4.5 * w_lhand
    y_sh = y_sh - hand_pat * 6.5 * (w_rhand + w_lhand)

    warped = cv2.remap(
        canvas,
        x_sh.astype(np.float32),
        y_sh.astype(np.float32),
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    warped_scaled = cv2.resize(warped, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
    # Compute foreground alpha on warped_scaled so studio_bg dot-grid shows cleanly around the warped frog!
    hsv_w = cv2.cvtColor(cv2.cvtColor(warped_scaled, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
    Sw = hsv_w[:, :, 1].astype(np.float32)
    Vw = hsv_w[:, :, 2].astype(np.float32)
    w_alpha = np.clip(np.maximum((Sw - 15.0) / 30.0, (244.0 - Vw) / 28.0), 0.0, 1.0)
    w_alpha_u16 = (w_alpha * 256.0).astype(np.uint16)[:, :, None]
    out_roi = ((roi_bg_u16 * (256 - w_alpha_u16) + warped_scaled.astype(np.uint16) * w_alpha_u16) >> 8).astype(np.uint8)
    return out_roi

def get_epicycle_color(m_idx):
    if m_idx == 1:
        return (230, 168, 28)
    elif m_idx < 7:
        return (238, 182, 42)
    elif m_idx < 18:
        return (112, 164, 88)
    elif m_idx < 42:
        return (206, 142, 48)
    else:
        return (92, 76, 28)

epi_colors = [get_epicycle_color(m) for m in range(MAX_M)]

landmarks_info = [
    (0.032, "Eye & Pupil",             (112, 164, 88)),
    (0.090, "Mouth",                   (180, 120, 35)),
    (0.215, "Right Hand & Arm",        (110, 90, 32)),
    (0.469, "Cream Belly & Left Hand", (218, 162, 42)),
    (0.634, "Left Webbed Foot",        (110, 90, 32)),
    (0.749, "Lower Belly Fold",        (218, 162, 42)),
    (0.797, "Right Webbed Foot",       (110, 90, 32)),
    (0.925, "Back Silhouette",         (234, 176, 38)),
]

font_candidates = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
selected_font = next((fp for fp in font_candidates if Path(fp).is_file()), None)
if selected_font is None:
    raise FileNotFoundError("No supported font was found. See docs/USAGE.md for font setup.")
font_title = ImageFont.truetype(selected_font, 23)
font_mono = ImageFont.truetype(selected_font, 14)
font_badge = ImageFont.truetype(selected_font, 16)
font_meme_big = ImageFont.truetype(selected_font, 34)
font_meme_med = ImageFont.truetype(selected_font, 26)

def to_fp(x, y):
    return (int(round(x * SCALE_FP)), int(round(y * SCALE_FP)))

cam_cx = W / 2.0
cam_cy = H / 2.0
cam_zoom = 1.0

output_mp4 = output_dir / 'naiwa_fourier_epicycle_reveal.mp4'
output_gif = output_dir / 'naiwa_belly_laugh.gif'

ffmpeg_cmd = [
    ffmpeg_path, "-hide_banner", "-loglevel", "error", "-nostats", "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", f"{W}x{H}",
    "-pix_fmt", "rgb24",
    "-r", str(FPS),
    "-i", "-",
    "-i", str(wav_path),
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "17",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    "-movflags", "+faststart",
    str(output_mp4)
]

proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

preview_frames_to_save = {
    210: "preview_act2_trace.png",          # t = 7.0s (Act II zoomed trace)
    540: "preview_act3_bloom.png",          # t = 18.0s (Act III full 3D bloom)
    598: "preview_act3_tap_stitch.png",     # t = 19.93s (Tap-to-laugh stitch bridge)
    636: "preview_act4_laugh_burst1.png",   # t = 21.2s (Act IV Belly-Laugh Burst 1)
    708: "preview_act4_laugh_peak.png",     # t = 23.6s (Act IV Hysterical Head-Back Peak!)
}

gif_frames = []

for f_idx in range(N_FRAMES):
    t_sec = f_idx / FPS
    rms_val = float(frame_rms[f_idx])
    spec_vals = frame_spec[f_idx]

    beat_phase = (t_sec % 0.60) / 0.60
    beat_pulse = np.exp(-beat_phase * 5.5)

    if t_sec < 6.00:
        # ACT I: Harmonic Awakening (6 steps of 1.0s each)
        act_idx = 1
        step_idx = min(5, int(t_sec / 1.00))
        M_active = act1_M_steps[step_idx]
        u_param = (t_sec / 4.00) % 1.0
        act_label = f"ACT I • HARMONIC AWAKENING (M = {M_active} EPICYCLES)"
        phase_pct = (t_sec / 6.00) * 100.0
    elif t_sec < 16.80:
        # ACT II: Slow-Reveal Precision Epicycle Trace (10.8s full tour u: 0 -> 1)
        act_idx = 2
        M_active = MAX_M
        u_param = np.clip((t_sec - 6.00) / 10.80, 0.0, 0.9999)
        act_label = "ACT II • SLOW-REVEAL PRECISION EPICYCLE TRACE"
        phase_pct = u_param * 100.0
    elif t_sec < 20.40:
        # ACT III: Full 3D Portrait Bloom & Seamless Stitch Bridge (16.8s - 20.4s)
        act_idx = 3
        M_active = MAX_M
        u_param = ((t_sec - 16.80) / 7.20) % 1.0
        act_label = "ACT III • 3D PORTRAIT BLOOM & STITCH TRANSITION"
        phase_pct = 100.0
    else:
        # ACT IV: Stitched "奶蛙捧腹大笑" Finale! (20.4s - 28.8s)
        act_idx = 4
        M_active = MAX_M
        u_param = ((t_sec - 20.40) / 3.60) % 1.0
        act_label = "ACT IV • STITCHED FINALE: 奶蛙捧腹大笑 (BELLY LAUGH)"
        phase_pct = 100.0

    # Compute epicycle chain
    angles = 2.0 * np.pi * freqs_sorted[:M_active] * u_param
    terms = coeffs_sorted[:M_active] * (np.cos(angles) + 1j * np.sin(angles))
    chain_z = np.cumsum(terms)
    chain_x = chain_z.real + cx_canvas
    chain_y = chain_z.imag + cy_canvas
    tip_x, tip_y = float(chain_x[-1]), float(chain_y[-1])

    master = studio_bg.copy()

    # --- LAYER 1: Progressive 3D Reference Image Reveal & Stitched 3D Belly-Laugh Rig ---
    if act_idx == 1:
        if step_idx >= 2:
            alpha_sil = 0.06 + 0.05 * (step_idx / 5.0) + 0.03 * beat_pulse
            w_u16 = (body_alpha * (alpha_sil * 256.0)).astype(np.uint16)[:, :, None]
            gold_u16 = np.array([242, 204, 95], dtype=np.uint16)
            master[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w] = (
                (roi_bg_u16 * (256 - w_u16) + gold_u16 * w_u16) >> 8
            ).astype(np.uint8)
    elif act_idx == 2:
        reveal_prog = np.clip((u_param - effective_u_roi + 0.025) * 22.22, 0.0, 1.0)
        wavefront = (1.4 * reveal_prog * (1.0 - reveal_prog) * body_alpha * 256.0).astype(np.uint16)[:, :, None]
        w_3d = (reveal_prog * body_alpha * (0.58 + 0.12 * u_param) * 256.0).astype(np.uint16)[:, :, None]
        blended_u16 = (roi_bg_u16 * (256 - w_3d) + roi_ref_u16 * w_3d) >> 8
        gold_u16 = np.array([248, 198, 52], dtype=np.uint16)
        blended_u16 = (blended_u16 * (256 - wavefront) + gold_u16 * wavefront) >> 8
        master[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w] = blended_u16.astype(np.uint8)
    elif act_idx == 3 and t_sec < 19.60:
        bloom_t = np.clip((t_sec - 16.80) / 1.10, 0.0, 1.0)
        radial_bloom = np.clip((bloom_t * 1.35 - dist_from_top_roi * 0.5) * 2.85, 0.0, 1.0)
        w_full = ((0.70 + 0.30 * radial_bloom) * 256.0).astype(np.uint16)[:, :, None]
        blended_u16 = (roi_bg_u16 * (256 - w_full) + roi_ref_u16 * w_full) >> 8
        master[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w] = blended_u16.astype(np.uint8)
    else:
        # Seamless Stitch Transition (19.60s - 20.40s) & Full Belly-Laugh Finale (20.40s - 28.80s)!
        tear_p = ((t_sec - 20.40) * 1.35) % 1.0 if (20.50 <= t_sec <= 27.60) else -1.0
        laughed_roi = render_laughing_naiwa_roi(
            mouth_open=float(laugh_mouth[f_idx]),
            eye_squint=float(laugh_squint[f_idx]),
            lean_back_deg=float(laugh_lean[f_idx]),
            head_tilt_deg=float(laugh_head[f_idx]),
            belly_inflate=float(laugh_belly_inf[f_idx]),
            belly_dy=float(laugh_belly_dy[f_idx]),
            hand_pat=float(laugh_hand[f_idx]),
            body_bounce_y=float(laugh_bounce[f_idx]),
            tongue_wave=t_sec * 32.0,
            tear_prog=tear_p
        )
        master[Y_OFF:Y_OFF+scaled_h, X_OFF:X_OFF+scaled_w] = laughed_roi

        # If in the Tap-to-Laugh Stitch Bridge (19.60s - 20.45s), draw expanding golden tap rings on the belly!
        if 19.60 <= t_sec <= 20.45:
            tap_p = (t_sec - 19.60) / 0.85
            belly_tap_x = int(X_OFF + 135 * SCALE_REF)
            belly_tap_y = int(Y_OFF + 425 * SCALE_REF)
            for r_mult in [1.0, 1.6]:
                tap_r = int((14.0 + 95.0 * tap_p * r_mult) * SCALE_FP)
                cv2.circle(master, to_fp(belly_tap_x, belly_tap_y), tap_r, (235, 168, 24), 2, lineType=cv2.LINE_AA, shift=SHIFT)
            cv2.circle(master, to_fp(belly_tap_x, belly_tap_y), int(10 * (1.0 - 0.5 * tap_p) * SCALE_FP), (248, 198, 52), -1, lineType=cv2.LINE_AA, shift=SHIFT)

        # In Act IV (20.40s - 27.80s), draw golden acoustic laugh shockwave rings radiating from mouth/belly!
        if 20.40 <= t_sec <= 27.60 and laugh_mouth[f_idx] > 0.45:
            wave_p = ((t_sec - 20.40) * 2.5) % 1.0
            mouth_canvas_x = X_OFF + (142.0 + laugh_lean[f_idx] * 2.2) * SCALE_REF
            mouth_canvas_y = Y_OFF + (148.0 - laugh_lean[f_idx] * 0.8) * SCALE_REF
            rad_shock = (28.0 + 130.0 * wave_p) * SCALE_FP
            cv2.circle(master, to_fp(mouth_canvas_x, mouth_canvas_y), int(rad_shock), (238, 182, 42), 2, lineType=cv2.LINE_AA, shift=SHIFT)

    # --- LAYER 2: Drawn Fourier Contour Curves (Acts I - III, smoothly dissolving before the laugh at 19.6s) ---
    if act_idx == 1:
        pts_fp = act1_closed_curves_fp[M_active]
        glow_layer = master.copy()
        cv2.polylines(glow_layer, [pts_fp], True, (240, 188, 52), thickness=6, lineType=cv2.LINE_AA, shift=SHIFT)
        master = cv2.addWeighted(glow_layer, 0.35 + 0.15 * beat_pulse, master, 0.65 - 0.15 * beat_pulse, 0)
        cv2.polylines(master, [pts_fp], True, (195, 160, 82), thickness=2, lineType=cv2.LINE_AA, shift=SHIFT)
        n_traced_1 = max(2, int(u_param * len(pts_fp)))
        cv2.polylines(master, [pts_fp[:n_traced_1]], False, (78, 62, 18), thickness=3, lineType=cv2.LINE_AA, shift=SHIFT)
    elif act_idx in (2, 3):
        max_u = u_param if act_idx == 2 else 1.0
        max_idx = max(2, int(max_u * N))
        # Smoothly dissolve static contour between 17.2s and 19.6s so the 3D frog can move freely when laughing!
        if act_idx == 2:
            contour_alpha = 0.92
        else:
            contour_alpha = max(0.0, 0.92 * (1.0 - (t_sec - 17.00) / 2.50))

        if contour_alpha > 0.02:
            contour_layer = master.copy()
            for i_s, i_e, col, seg_fp in contour_chunks:
                if i_s >= max_idx - 1:
                    break
                if i_e <= max_idx:
                    cv2.polylines(contour_layer, [seg_fp], False, col, thickness=2, lineType=cv2.LINE_AA, shift=SHIFT)
                else:
                    cv2.polylines(contour_layer, [seg_fp[:max_idx - i_s + 1]], False, col, thickness=2, lineType=cv2.LINE_AA, shift=SHIFT)

            if act_idx == 2 and max_idx > 3:
                tail_start = max(0, max_idx - 140)
                for t_i in range(tail_start, max_idx - 1, 6):
                    if not ubridge[t_i]:
                        t_end = min(max_idx, t_i + 7)
                        prog_tail = (t_i - tail_start) / max(1, (max_idx - tail_start))
                        col_tail = (
                            int(120 + 130 * prog_tail),
                            int(90 + 100 * prog_tail),
                            int(25 + 20 * prog_tail)
                        )
                        thick_tail = 2 if prog_tail < 0.6 else 3
                        cv2.polylines(contour_layer, [rec_pts_fp[t_i:t_end]], False, col_tail, thickness=thick_tail, lineType=cv2.LINE_AA, shift=SHIFT)

            master = cv2.addWeighted(contour_layer, contour_alpha, master, 1.0 - contour_alpha, 0)

    # --- LAYER 3: 3D-Styled Fourier Epicycle Wheels (In Act IV, they pulse as a gentle harmonic halo!) ---
    if act_idx < 3:
        epi_opacity = 0.88
    elif act_idx == 3:
        epi_opacity = max(0.22, 0.88 - 0.66 * ((t_sec - 16.80) / 2.80))
    else:
        # In Act IV, keep a subtle 22% golden harmonic epicycle halo pulsing with the laughter!
        epi_opacity = 0.18 + 0.12 * float(laugh_mouth[f_idx])

    if epi_opacity > 0.05:
        epi_layer = master.copy()
        n_draw_circles = min(M_active - 1, 55 if act_idx < 4 else 18)

        if act_idx < 3:
            shadow_layer = master.copy()
            for m in range(1, min(n_draw_circles + 1, 26)):
                r = radii_sorted[m]
                if r >= 3.0:
                    cv2.circle(
                        shadow_layer,
                        to_fp(chain_x[m - 1] + 3.0, chain_y[m - 1] + 4.0),
                        int(round(r * SCALE_FP)),
                        (215, 206, 185),
                        thickness=1,
                        lineType=cv2.LINE_AA,
                        shift=SHIFT
                    )
            epi_layer = cv2.addWeighted(shadow_layer, 0.45, epi_layer, 0.55, 0)

        for m in range(1, n_draw_circles + 1):
            r = radii_sorted[m] * (1.0 + 0.08 * float(laugh_mouth[f_idx]) if act_idx == 4 else 1.0)
            cx_m, cy_m = chain_x[m - 1], chain_y[m - 1]
            nx_m, ny_m = chain_x[m], chain_y[m]
            col_c = epi_colors[m]

            if r >= 1.1:
                thick_c = 2 if (m <= 6 and beat_pulse > 0.5) else 1
                cv2.circle(
                    epi_layer,
                    to_fp(cx_m, cy_m),
                    int(round(r * SCALE_FP)),
                    col_c,
                    thickness=thick_c,
                    lineType=cv2.LINE_AA,
                    shift=SHIFT
                )
            if r >= 0.8:
                arm_col = (
                    max(40, col_c[0] - 25),
                    max(35, col_c[1] - 25),
                    max(15, col_c[2] - 15)
                )
                cv2.line(
                    epi_layer,
                    to_fp(cx_m, cy_m),
                    to_fp(nx_m, ny_m),
                    arm_col,
                    thickness=2 if m <= 8 else 1,
                    lineType=cv2.LINE_AA,
                    shift=SHIFT
                )

        if act_idx < 4 and M_active > n_draw_circles + 1:
            rem_pts = np.column_stack([chain_x[n_draw_circles:], chain_y[n_draw_circles:]])
            rem_fp = (rem_pts * SCALE_FP).astype(np.int32)
            cv2.polylines(epi_layer, [rem_fp], False, (92, 76, 28), thickness=1, lineType=cv2.LINE_AA, shift=SHIFT)

        for m in range(min(M_active, 16 if act_idx < 4 else 8)):
            jx, jy = chain_x[m], chain_y[m]
            jr = 3.5 if m < 4 else (2.5 if m < 10 else 1.8)
            cv2.circle(epi_layer, to_fp(jx, jy), int(round(jr * SCALE_FP)), (75, 60, 20), -1, lineType=cv2.LINE_AA, shift=SHIFT)
            cv2.circle(epi_layer, to_fp(jx - 0.7, jy - 0.7), int(round(jr * 0.45 * SCALE_FP)), (250, 232, 165), -1, lineType=cv2.LINE_AA, shift=SHIFT)

        if act_idx < 4:
            tip_r = 4.5 + 3.5 * rms_val + 2.0 * beat_pulse
            cv2.circle(epi_layer, to_fp(tip_x, tip_y), int(round(tip_r * 1.9 * SCALE_FP)), (248, 204, 68), 1, lineType=cv2.LINE_AA, shift=SHIFT)
            cv2.circle(epi_layer, to_fp(tip_x, tip_y), int(round(tip_r * SCALE_FP)), (235, 160, 24), -1, lineType=cv2.LINE_AA, shift=SHIFT)
            cv2.circle(epi_layer, to_fp(tip_x - 1.0, tip_y - 1.0), int(round(tip_r * 0.42 * SCALE_FP)), (255, 250, 225), -1, lineType=cv2.LINE_AA, shift=SHIFT)

        if act_idx == 2:
            for lm_u, lm_name, lm_col in landmarks_info:
                dt_lm = (u_param - lm_u) * 10.80
                if 0.0 <= dt_lm <= 0.85:
                    lm_idx = int(lm_u * N) % N
                    lx, ly = rec_x[lm_idx], rec_y[lm_idx]
                    rip_r = 6.0 + 42.0 * (dt_lm / 0.85)
                    rip_thick = 2 if dt_lm < 0.35 else 1
                    cv2.circle(epi_layer, to_fp(lx, ly), int(round(rip_r * SCALE_FP)), lm_col, rip_thick, lineType=cv2.LINE_AA, shift=SHIFT)

        master = cv2.addWeighted(epi_layer, epi_opacity, master, 1.0 - epi_opacity, 0)

    # Save clean portrait crop for the standalone looping GIF during the peak belly-laugh cycle (20.1s - 25.1s, every 2nd frame -> 15 fps)
    if 20.10 <= t_sec <= 25.10 and (f_idx % 2 == 0):
        gif_crop = master[Y_OFF-10:Y_OFF+scaled_h+10, X_OFF-20:X_OFF+scaled_w+20].copy()
        gif_pil = Image.fromarray(gif_crop).resize((360, 660), resample=Image.Resampling.LANCZOS)
        draw_g = ImageDraw.Draw(gif_pil)
        if t_sec >= 20.40:
            # Add playful floating "哈哈哈!" / "齁齁齁~" meme text on the GIF!
            by_off = int(6 * np.sin(t_sec * 18.0))
            draw_g.text((22, 24 + by_off), "哈哈哈哈!!", font=font_meme_med, fill=(215, 135, 18))
            if t_sec >= 21.60:
                draw_g.text((215, 58 - by_off), "齁齁齁~", font=font_meme_med, fill=(102, 148, 72))
        gif_frames.append(gif_pil)

    # --- LAYER 4: Smooth Dynamic Camera Zoom ---
    if t_sec < 5.70:
        target_zoom = 1.0
        target_cx, target_cy = W / 2.0, H / 2.0
    elif t_sec < 16.50:
        target_zoom = 1.95
        half_vw = (W / target_zoom) / 2.0
        half_vh = (H / target_zoom) / 2.0
        target_cx = np.clip(tip_x, half_vw + 16, W - half_vw - 16)
        target_cy = np.clip(tip_y, 120 + half_vh, 1120 - half_vh)
    elif t_sec < 20.40:
        target_zoom = 1.0
        target_cx, target_cy = W / 2.0, H / 2.0
    else:
        # Subtle dynamic comedy zoom-in (1.08x) pulsing gently with the belly laughter in Act IV!
        target_zoom = 1.0 + 0.08 * np.sin(np.pi * np.clip((t_sec - 20.40) / 7.50, 0.0, 1.0)) + 0.025 * float(laugh_mouth[f_idx])
        target_cx, target_cy = W / 2.0, H * 0.46

    alpha_cam = 0.14 if (5.70 <= t_sec < 16.50) else 0.12
    cam_zoom += alpha_cam * (target_zoom - cam_zoom)
    cam_cx += alpha_cam * (target_cx - cam_cx)
    cam_cy += alpha_cam * (target_cy - cam_cy)

    if cam_zoom > 1.02:
        full_overview = master.copy()
        vw = W / cam_zoom
        vh = H / cam_zoom
        x1 = np.clip(cam_cx - vw / 2.0, 0, W - vw)
        y1 = np.clip(cam_cy - vh / 2.0, 0, H - vh)
        M_warp = np.array([
            [cam_zoom, 0.0, -x1 * cam_zoom],
            [0.0, cam_zoom, -y1 * cam_zoom]
        ], dtype=np.float32)
        view_frame = cv2.warpAffine(master, M_warp, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        # Only show PiP overview map during Act II when cam_zoom > 1.25
        if act_idx == 2 and cam_zoom > 1.25:
            pip_w, pip_h = 172, 304
            pip_x, pip_y = W - pip_w - 22, 148
            cv2.rectangle(
                full_overview,
                (int(x1), int(y1)),
                (int(x1 + vw), int(y1 + vh)),
                (230, 168, 28),
                thickness=6,
                lineType=cv2.LINE_AA
            )
            pip_img = cv2.resize(full_overview[125:1115, 20:700], (pip_w, pip_h), interpolation=cv2.INTER_AREA)

            pip_alpha = np.clip((cam_zoom - 1.25) / 0.35, 0.0, 0.94)
            sub_bg = view_frame[pip_y:pip_y+pip_h, pip_x:pip_x+pip_w].astype(np.float32)
            view_frame[pip_y:pip_y+pip_h, pip_x:pip_x+pip_w] = (
                sub_bg * (1.0 - pip_alpha) + pip_img.astype(np.float32) * pip_alpha
            ).astype(np.uint8)
            cv2.rectangle(view_frame, (pip_x, pip_y), (pip_x + pip_w, pip_y + pip_h), (195, 168, 102), 2, lineType=cv2.LINE_AA)
    else:
        view_frame = master

    # --- LAYER 5: Studio HUD Header, Meme Laugh Callouts & Synced Audio-Harmonic Spectrum Deck ---
    hud_overlay = view_frame.copy()
    cv2.rectangle(hud_overlay, (16, 16), (W - 16, 114), (248, 244, 232), -1)
    cv2.rectangle(hud_overlay, (16, 1132), (W - 16, H - 16), (248, 244, 232), -1)
    view_frame = cv2.addWeighted(hud_overlay, 0.88, view_frame, 0.12, 0)
    cv2.rectangle(view_frame, (16, 16), (W - 16, 114), (212, 198, 162), 1, lineType=cv2.LINE_AA)
    cv2.rectangle(view_frame, (16, 1132), (W - 16, H - 16), (212, 198, 162), 1, lineType=cv2.LINE_AA)

    y_base = 1234
    for b_i in range(32):
        bx = 34 + b_i * 9
        bh = int(4 + 54 * spec_vals[b_i])
        b_col = (
            int(110 + 125 * (b_i / 31.0)),
            int(145 + 35 * np.sin(b_i / 10.0)),
            int(45 + 30 * (1.0 - b_i / 31.0))
        )
        cv2.rectangle(view_frame, (bx, y_base - bh), (bx + 6, y_base), b_col, -1)

    for k_i in range(1, 33):
        bx = 376 + (k_i - 1) * 9
        if k_i < M_active:
            amp_norm = np.log1p(radii_sorted[k_i]) / np.log1p(radii_sorted[1])
            osc_factor = (0.75 + 0.25 * float(laugh_mouth[f_idx]) * np.sin(t_sec * 20 + k_i)) if act_idx == 4 else (0.82 + 0.18 * np.sin(2 * np.pi * freqs_sorted[k_i] * u_param + t_sec * 4))
            bh = int(4 + 50 * amp_norm * osc_factor)
            col_bar = epi_colors[k_i]
        else:
            bh = 3
            col_bar = (218, 210, 192)
        cv2.rectangle(view_frame, (bx, y_base - bh), (bx + 6, y_base), col_bar, -1)

    cv2.rectangle(view_frame, (34, 1250), (W - 34, 1256), (226, 218, 198), -1)
    prog_w = int((W - 68) * (t_sec / DURATION))
    cv2.rectangle(view_frame, (34, 1250), (34 + prog_w, 1256), (224, 162, 28), -1)

    pil_img = Image.fromarray(view_frame)
    draw = ImageDraw.Draw(pil_img)

    draw.text((32, 26), "FOURIER EPICYCLE PORTRAIT  •  奶蛙 (MILK FROG)", font=font_title, fill=(62, 48, 16))
    draw.text((32, 58), act_label, font=font_badge, fill=(178, 118, 18))

    cur_feature = "Full Portrait Harmonics"
    if act_idx == 2:
        for lm_u, lm_name, _ in landmarks_info:
            if abs(u_param - lm_u) < 0.065:
                cur_feature = lm_name
                break
    elif act_idx == 3:
        cur_feature = "Tap-to-Laugh Stitch" if t_sec >= 19.60 else "3D Reference Portrait"
    elif act_idx == 4:
        cur_feature = "捧腹狂笑 (Belly Laugh)"

    tele_str = f"z(t) = Σ c_k e^(i2πkt)  |  Harmonics: M={M_active}  |  Trace: {phase_pct:5.1f}%  |  Focus: {cur_feature}"
    draw.text((32, 84), tele_str, font=font_mono, fill=(98, 84, 48))

    draw.text((34, 1142), "SYNCED SOUNDTRACK & LAUGH SPECTRUM", font=font_mono, fill=(82, 68, 32))
    draw.text((376, 1142), f"FOURIER EPICYCLE AMPLITUDES |c_k| (M={M_active})", font=font_mono, fill=(82, 68, 32))

    if act_idx == 2 and cam_zoom > 1.28:
        draw.text((W - 190, 152), "OVERVIEW MAP", font=font_mono, fill=(92, 76, 28))

    # Floating Meme Typography during Stitch Bridge (19.6s - 20.4s) & Belly-Laugh Finale (20.4s - 27.6s)!
    if 19.60 <= t_sec < 20.40:
        draw.text((225, 162), "★ 点一下奶蛙 • 触发捧腹狂笑! ★", font=font_meme_med, fill=(195, 122, 14))
    elif 20.40 <= t_sec <= 27.60:
        dy_b1 = int(9 * np.sin(t_sec * 22.0))
        dy_b2 = int(9 * np.cos(t_sec * 20.0))
        draw.text((52, 175 + dy_b1), "哈哈哈哈!!", font=font_meme_big, fill=(215, 132, 16))
        if t_sec >= 21.50:
            draw.text((485, 225 + dy_b2), "齁齁齁~", font=font_meme_big, fill=(98, 146, 68))
        if 22.80 <= t_sec <= 26.80:
            draw.text((58, 520 - dy_b1), "捧腹狂笑!", font=font_meme_med, fill=(165, 108, 22))
        if 24.50 <= t_sec <= 27.20:
            draw.text((485, 485 + dy_b1), "笑出眼泪!!", font=font_meme_med, fill=(75, 138, 185))

    final_frame = np.array(pil_img)
    proc.stdin.write(final_frame.tobytes())

    if f_idx in preview_frames_to_save:
        p_path = preview_dir / preview_frames_to_save[f_idx]
        cv2.imwrite(str(p_path), cv2.cvtColor(final_frame, cv2.COLOR_RGB2BGR))
        print(f"Saved preview frame {f_idx} -> {p_path}")

proc.stdin.close()
stderr_out = proc.stderr.read().decode('utf-8', errors='ignore')
proc.wait()
print(f"FFmpeg exit code: {proc.returncode}, total time: {time.time() - t0_start:.1f}s")
if proc.returncode != 0:
    raise RuntimeError(f"FFmpeg failed with exit code {proc.returncode}:\n{stderr_out}")

# Save standalone looping GIF of 奶蛙捧腹大笑!
if gif_frames:
    gif_frames[0].save(
        output_gif,
        save_all=True,
        append_images=gif_frames[1:],
        duration=66,  # ~15 fps smooth looping GIF
        loop=0,
        optimize=True
    )
    print(f"Saved standalone looping GIF ({len(gif_frames)} frames) -> {output_gif}")
