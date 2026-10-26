#!/usr/bin/env python3
"""一键运行：奶蛙傅里叶本轮慢速揭晓 + 捧腹大笑缝合视频生成管线"""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

steps = [
    ("Step 1/3: 提取奶蛙单闭环轮廓与特征点", "prepare_tour_data.py"),
    ("Step 2/3: 合成 28.8s 配乐与笑声同步曲线", "generate_soundtrack.py"),
    ("Step 3/3: 渲染傅里叶动画、捧腹大笑视频与 GIF", "render_epicycle_video.py"),
]

def main():
    if shutil.which('ffmpeg') is None:
        raise FileNotFoundError("FFmpeg was not found on PATH. See docs/USAGE.md.")
    (ROOT / 'output').mkdir(exist_ok=True)
    for desc, script in steps:
        print(f"\n=== {desc} ===", flush=True)
        subprocess.run([sys.executable, '-u', str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)

    print(f"\n全部生成完成！输出目录：{ROOT / 'output'}")
    print("  - naiwa_fourier_epicycle_reveal.mp4")
    print("  - naiwa_belly_laugh.gif")


if __name__ == '__main__':
    main()
