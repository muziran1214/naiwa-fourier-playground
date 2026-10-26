from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
image_path = ROOT / 'assets' / 'capture_temp.jpg'
diagnostics_dir = ROOT / 'output' / 'diagnostics'
diagnostics_dir.mkdir(parents=True, exist_ok=True)

img_bgr = cv2.imread(str(image_path))
if img_bgr is None:
    raise FileNotFoundError(f"Cannot read reference image: {image_path}")
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
h, w, _ = img_rgb.shape

Y_base, X_base = np.mgrid[0:h, 0:w].astype(np.float32)

def render_laughing_naiwa(
    img_src,
    mouth_open=0.0,     # 0.0 (closed) to 1.0 (wide open roaring laugh)
    eye_squint=0.0,     # 0.0 (open round) to 1.0 (happy crescent squint)
    lean_back_deg=0.0,  # Spine backward lean angle in degrees
    head_tilt_deg=0.0,  # Additional head backward tilt in degrees
    belly_inflate=0.0,  # -1.0 to +1.0 belly jiggle expansion
    belly_dy=0.0,       # Vertical belly bounce in pixels
    hand_pat=0.0,       # Hand patting displacement on belly
    body_bounce_y=0.0,  # Whole torso/hip vertical laugh bounce
    tongue_wave=0.0,    # Tongue quiver phase
    tear_prog=-1.0      # Tear droplet progress (0..1), <0 if none
):
    canvas = img_src.copy()

    # --- A. CANONICAL JAW DROP & CHEEK RAISE ---
    if mouth_open > 0.01 or eye_squint > 0.01:
        jaw_drop_px = 36.0 * (mouth_open ** 0.82)
        cheek_raise_px = 7.5 * eye_squint

        # Lower jaw / chin region below y=151
        wx_jaw = np.exp(-((X_base - 130.0) / 44.0) ** 2) * (X_base < 198)
        wy_jaw = np.clip((Y_base - 150.0) / 7.5, 0.0, 1.0) * np.exp(-np.maximum(0.0, Y_base - 165.0) / 48.0)
        w_jaw = wx_jaw * wy_jaw

        # Upper snout/lip lift when laughing wide
        wx_ulip = np.exp(-((X_base - 126.0) / 34.0) ** 2)
        wy_ulip = np.exp(-((Y_base - 144.0) / 14.0) ** 2) * (Y_base <= 153.0)
        w_ulip = wx_ulip * wy_ulip

        # Cheek raise under eye when squinting happily
        wx_cheek = np.exp(-((X_base - 165.0) / 28.0) ** 2)
        wy_cheek = np.exp(-((Y_base - 134.0) / 14.0) ** 2)
        w_cheek = wx_cheek * wy_cheek

        map_x_face = (X_base - 4.5 * mouth_open * w_jaw).astype(np.float32)
        map_y_face = (Y_base
                      - jaw_drop_px * w_jaw
                      + 5.5 * mouth_open * w_ulip
                      + cheek_raise_px * w_cheek).astype(np.float32)

        canvas = cv2.remap(canvas, map_x_face, map_y_face, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # --- B. 3D-SHADED ROARING LAUGH MOUTH CAVITY & TONGUE ---
    if mouth_open > 0.03:
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

        # 3D Coral-Pink Frog Tongue
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

        # Laughing cheek dimple arc at right mouth corner
        roi_out_ss = np.clip(roi_f, 0, 255).astype(np.uint8)
        cx_dimple = int((x_right + 1 - rx0) * SS)
        cy_dimple = int((y_corner - ry0) * SS)
        cv2.ellipse(roi_out_ss, (cx_dimple, cy_dimple), (10, 16), -25, -70, 75, (142, 104, 26), thickness=3, lineType=cv2.LINE_AA)

        canvas[ry0:ry1, rx0:rx1] = cv2.resize(roi_out_ss, (roi_w, roi_h), interpolation=cv2.INTER_AREA)

    # --- C. 3D SAGE-GREEN SQUINTED LAUGHING EYES ("眼睛眯成一条缝") ---
    if eye_squint > 0.05:
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

        # Far-side left eye bump at x=113..120, y=108..126: only tint dark pupil pixels (where B channel < 110)
        lx0, ly0, lx1, ly1 = 112, 107, 121, 127
        l_roi = canvas[ly0:ly1, lx0:lx1].astype(np.float32)
        dark_pupil_mask = np.clip((125.0 - l_roi[:, :, 2]) / 45.0, 0.0, 1.0) * eye_squint
        l_lid = np.array([138.0, 168.0, 102.0])
        canvas[ly0:ly1, lx0:lx1] = np.clip(
            l_roi * (1.0 - dark_pupil_mask[:, :, None]) + l_lid * dark_pupil_mask[:, :, None],
            0, 255
        ).astype(np.uint8)

    # --- D. SPARKLING TEAR OF JOY DROPLETS (drawn at outer corner of eye in canonical space so they warp with head!) ---
    if tear_prog >= 0.0:
        for t_offset in [0.0, 0.5]:
            tp = (tear_prog + t_offset) % 1.0
            # Outer right corner of eye is (185, 117), tear flies out to the right-down
            drop_x = int(185.0 + 34.0 * tp)
            drop_y = int(117.0 - 8.0 * tp + 36.0 * (tp ** 2))
            drop_r = max(2, int(5.5 * (1.0 - 0.45 * tp)))
            cv2.circle(canvas, (drop_x, drop_y), drop_r + 1, (135, 192, 232), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (drop_x, drop_y), drop_r, (215, 245, 255), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (drop_x - 1, drop_y - 1), max(1, drop_r // 2), (255, 255, 255), -1, lineType=cv2.LINE_AA)

    # --- E. GLOBAL SKELETAL & BELLY-JIGGLE MESH DEFORMATION ---
    hip_x, hip_y = 215.0, 590.0
    w_spine = np.clip((680.0 - Y_base) / 220.0, 0.0, 1.0) ** 1.25
    theta_rad = -np.deg2rad(lean_back_deg) * w_spine

    neck_x, neck_y = 195.0, 225.0
    w_head = np.clip((255.0 - Y_base) / 70.0, 0.0, 1.0) ** 1.35
    theta_head_rad = -np.deg2rad(head_tilt_deg) * w_head

    # Whole torso vertical bounce (knees flexing down to y=730 while feet stay planted!)
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

    # Rubbery Belly Jiggle ("捧腹颤抖") centered at (135, 425)
    bcx, bcy = 135.0, 425.0
    b_dist2 = ((x_sh - bcx) / 122.0) ** 2 + ((y_sh - bcy) / 138.0) ** 2
    w_belly = np.exp(-b_dist2 * 1.3)
    x_sh = x_sh - (x_sh - bcx) * (0.11 * belly_inflate) * w_belly + 8.0 * belly_inflate * w_belly
    y_sh = y_sh - belly_dy * w_belly

    # Hands Patting / Clutching the Belly
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
    return warped

poses = [
    ("1. Calm Finish (t=20.5s)", dict(mouth_open=0.0, eye_squint=0.0, lean_back_deg=0.0, head_tilt_deg=0.0, belly_inflate=0.0, belly_dy=0.0, hand_pat=0.0, body_bounce_y=0.0)),
    ("2. Deep Inhale / Smirk",   dict(mouth_open=0.22, eye_squint=0.40, lean_back_deg=-2.5, head_tilt_deg=-3.5, belly_inflate=0.9, belly_dy=-8.0, hand_pat=-0.8, body_bounce_y=-6.0)),
    ("3. First Laugh Burst!",    dict(mouth_open=0.92, eye_squint=0.88, lean_back_deg=6.5, head_tilt_deg=9.0, belly_inflate=-0.7, belly_dy=13.0, hand_pat=1.1, body_bounce_y=8.0, tear_prog=0.15)),
    ("4. Belly-Jiggle Peak",     dict(mouth_open=0.70, eye_squint=0.96, lean_back_deg=9.5, head_tilt_deg=5.0, belly_inflate=1.1, belly_dy=-14.0, hand_pat=-1.1, body_bounce_y=-9.0, tear_prog=0.45)),
    ("5. Hysterical Head-Back!", dict(mouth_open=1.00, eye_squint=1.00, lean_back_deg=14.0, head_tilt_deg=15.0, belly_inflate=0.85, belly_dy=15.0, hand_pat=1.3, body_bounce_y=10.0, tear_prog=0.75)),
    ("6. Laughing Out of Breath",dict(mouth_open=0.48, eye_squint=0.85, lean_back_deg=4.5, head_tilt_deg=3.5, belly_inflate=0.35, belly_dy=4.0, hand_pat=0.4, body_bounce_y=3.0, tear_prog=0.92)),
]

def main():
    fig, axes = plt.subplots(1, 6, figsize=(21, 7))
    for ax, (title, kw) in zip(axes, poses):
        out_img = render_laughing_naiwa(img_rgb, **kw)
        ax.imshow(out_img)
        ax.set_title(title, fontsize=11)
        ax.axis('off')
    plt.tight_layout()
    output_path = diagnostics_dir / 'laugh_poses_test_v2.png'
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved laugh poses -> {output_path}")


if __name__ == '__main__':
    main()
