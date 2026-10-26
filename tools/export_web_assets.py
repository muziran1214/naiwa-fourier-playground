"""Export the browser animation assets and a self-contained HTML copy."""
from pathlib import Path
import argparse
import base64
import json
import math
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from preview_laugh_rig import img_rgb, render_laughing_naiwa


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
ASSETS = WEB / 'assets'
CELL_WIDTH = 258
CELL_HEIGHT = round(img_rgb.shape[0] * CELL_WIDTH / img_rgb.shape[1])
COLS = 8
ROWS = 8


def cutout(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat, value = hsv[:, :, 1], hsv[:, :, 2]
    mask = ((sat > 24) | (value < 195)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError('No character foreground found for browser assets.')
    alpha = np.zeros_like(mask)
    cv2.drawContours(alpha, [max(contours, key=cv2.contourArea)], -1, 255, cv2.FILLED)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.65)
    return np.dstack((rgb, alpha))


def save_atlas(frames, name):
    pages = []
    count = len(frames)
    for start in range(0, count, COLS * ROWS):
        batch = frames[start:start + COLS * ROWS]
        rows = math.ceil(len(batch) / COLS)
        atlas = Image.new('RGBA', (CELL_WIDTH * COLS, CELL_HEIGHT * rows))
        for index, frame in enumerate(batch):
            cell = Image.fromarray(frame).resize((CELL_WIDTH, CELL_HEIGHT), Image.Resampling.LANCZOS)
            atlas.paste(cell, ((index % COLS) * CELL_WIDTH, (index // COLS) * CELL_HEIGHT))
        relative = f'assets/{name}-{len(pages)}.webp'
        atlas.save(WEB / relative, 'WEBP', quality=86, method=6)
        pages.append(relative)
    return {'pages': pages, 'width': CELL_WIDTH, 'height': CELL_HEIGHT, 'cols': COLS, 'rows': ROWS, 'count': count}


def uri(path):
    mime = {'.png': 'image/png', '.webp': 'image/webp', '.mp3': 'audio/mpeg'}[path.suffix]
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def bundle(scene):
    embedded = json.loads(json.dumps(scene))
    embedded['image'] = uri(WEB / embedded['image'])
    embedded['audio'] = uri(WEB / embedded['audio'])
    for key in ('reveal', 'laugh'):
        embedded[key]['pages'] = [uri(WEB / source) for source in embedded[key]['pages']]
    html = (WEB / 'index.html').read_text(encoding='utf-8')
    css = (WEB / 'style.css').read_text(encoding='utf-8')
    js = (WEB / 'app.js').read_text(encoding='utf-8')
    data = 'window.NAIWA_SCENE = ' + json.dumps(embedded, ensure_ascii=False, separators=(',', ':')) + ';'
    html = html.replace('<link rel="stylesheet" href="style.css">', f'<style>\n{css}\n</style>')
    html = html.replace('<script src="assets/scene.js"></script>', f'<script>\n{data}\n</script>')
    html = html.replace('<script src="app.js"></script>', f'<script>\n{js}\n</script>')
    destination = ROOT / 'output' / 'web' / 'naiwa_fourier_playground.html'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding='utf-8')
    print(f'Saved standalone HTML -> {destination}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-only', action='store_true', help='Rebuild the standalone HTML using existing browser assets.')
    args = parser.parse_args()
    scene_path = ASSETS / 'scene.js'
    if args.bundle_only:
        data = scene_path.read_text(encoding='utf-8').removeprefix('window.NAIWA_SCENE = ').strip().removesuffix(';')
        bundle(json.loads(data))
        return

    inputs = [ROOT / 'output/data/naiwa_tour_data.npz', ROOT / 'output/data/audio_sync_features.npz', ROOT / 'output/audio/naiwa_soundtrack.wav']
    for source in inputs:
        if not source.is_file():
            raise FileNotFoundError(f'Missing {source}. Run the contour and soundtrack scripts first.')
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        raise FileNotFoundError('FFmpeg was not found on PATH. See docs/USAGE.md.')
    ASSETS.mkdir(parents=True, exist_ok=True)
    with np.load(inputs[0]) as source:
        ux, uy, bridge = source['ux'], source['uy'], source['ubridge']
    with np.load(inputs[1]) as source:
        sync = {key: source[key].copy() for key in source.files}
    height, width = img_rgb.shape[:2]
    scale = 1.16
    scaled_width, scaled_height = round(width * scale), round(height * scale)
    x_off, y_off = (720 - scaled_width) // 2, 138
    center_x, center_y = x_off + scaled_width / 2, y_off + scaled_height / 2
    z = ux * scale + x_off - center_x + 1j * (uy * scale + y_off - center_y)
    coefficients = np.fft.fft(z) / len(z)
    frequencies = np.rint(np.fft.fftfreq(len(z)) * len(z)).astype(int)
    non_dc = np.flatnonzero(frequencies != 0)
    order = np.r_[0, non_dc[np.argsort(np.abs(coefficients[non_dc]))[::-1][:749]]]
    selected = coefficients[order]
    filtered = np.zeros_like(coefficients)
    filtered[order] = selected
    reconstructed = np.fft.ifft(filtered * len(z))
    foreground = cutout(img_rgb)
    Image.fromarray(foreground).save(ASSETS / 'frog.png')

    print('Preparing progressive reveal atlas...', flush=True)
    y_grid, x_grid = np.mgrid[0:height, 0:width]
    tree = cKDTree(np.column_stack((ux[~bridge], uy[~bridge])))
    distance, nearest = tree.query(np.column_stack((x_grid.ravel(), y_grid.ravel())))
    nearest_u = (np.arange(len(ux)) / len(ux))[~bridge][nearest].reshape(height, width).astype(np.float32)
    smoothed = cv2.GaussianBlur(nearest_u, (39, 39), 12)
    effective_u = np.where(distance.reshape(height, width) < 55 / scale, nearest_u, smoothed)
    effective_u = cv2.GaussianBlur(effective_u, (19, 19), 5.2)
    reveal_frames = []
    for progress in np.linspace(0, 1, 40):
        frame = foreground.copy()
        opacity = np.clip((progress - effective_u + 0.025) * 22.22, 0, 1) * (0.58 + 0.12 * progress)
        frame[:, :, 3] = np.round(foreground[:, :, 3] * opacity).astype(np.uint8)
        reveal_frames.append(frame)
    reveal = save_atlas(reveal_frames, 'reveal')
    del reveal_frames

    print('Rendering 138 browser laugh frames...', flush=True)
    laugh_frames = []
    channels = {'mouth_open': 'laugh_mouth', 'eye_squint': 'laugh_squint', 'lean_back_deg': 'laugh_lean', 'head_tilt_deg': 'laugh_head', 'belly_inflate': 'laugh_belly_inf', 'belly_dy': 'laugh_belly_dy', 'hand_pat': 'laugh_hand', 'body_bounce_y': 'laugh_bounce'}
    for frame_index in range(588, 864, 2):
        time = frame_index / 30
        params = {name: float(sync[key][frame_index]) for name, key in channels.items()}
        frame = render_laughing_naiwa(img_rgb, **params, tongue_wave=time * 32, tear_prog=((time - 20.4) * 1.35) % 1 if 20.5 <= time <= 27.6 else -1)
        laugh_frames.append(cutout(frame))
    laugh = save_atlas(laugh_frames, 'laugh')
    laugh.update({'fps': 15, 'start': 19.6})
    del laugh_frames

    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(inputs[2]), '-codec:a', 'libmp3lame', '-b:a', '160k', str(ASSETS / 'soundtrack.mp3')], check=True)
    scene = {
        'version': 1, 'width': 720, 'height': 1280, 'duration': 28.8, 'fps': 30,
        'image': 'assets/frog.png', 'audio': 'assets/soundtrack.mp3',
        'placement': {'x': x_off, 'y': y_off, 'width': scaled_width, 'height': scaled_height, 'cx': center_x, 'cy': center_y},
        'coefficients': [[round(float(c.real), 6), round(float(c.imag), 6), int(k)] for c, k in zip(selected, frequencies[order])],
        'reconstruction': np.round(np.column_stack((reconstructed.real + center_x, reconstructed.imag + center_y)), 3).tolist(),
        'bridge': bridge.astype(int).tolist(), 'spectrum': np.round(sync['frame_spec'], 3).tolist(),
        'rms': np.round(sync['frame_rms'], 3).tolist(), 'mouth': np.round(sync['laugh_mouth'], 3).tolist(),
        'reveal': reveal, 'laugh': laugh,
    }
    scene_path.write_text('window.NAIWA_SCENE = ' + json.dumps(scene, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    print(f'Saved browser assets -> {ASSETS}', flush=True)
    bundle(scene)


if __name__ == '__main__':
    main()
