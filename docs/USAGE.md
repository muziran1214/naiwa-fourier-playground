# 使用说明

[返回 README](../README.md)

## 环境与依赖

Python 依赖见 [requirements.txt](../requirements.txt)。以下是本项目实际完成生成时的环境记录，并非跨平台测试矩阵，也不是完整依赖锁文件。

| 组件 | 验证版本 | 用途 |
| --- | --- | --- |
| Python | 3.13.9 | 执行生成管线 |
| NumPy | 2.3.5 | 数组计算、FFT 与数据保存 |
| SciPy | 1.17.1 | 距离计算、滤波、卷积与 WAV 写入 |
| OpenCV | 4.13.0 | 图像处理、绘图、变形与缩放 |
| Pillow | 12.0.0 | 字体、文字与 GIF 导出 |
| Matplotlib | 3.10.9 | 辅助工具可视化 |
| FFmpeg | 7.1 | H.264 / AAC 编码与 MP4 封装 |

操作系统验证范围：Windows。macOS / Linux 的命令与字体候选已提供，但尚未实机验证。

### 安装 Python 包

在项目根目录创建虚拟环境并安装依赖。无需激活环境，也无需修改 PowerShell 执行策略。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

后文以 `python` 表示已安装这些依赖的解释器；使用虚拟环境时，将它替换为 `.\.venv\Scripts\python.exe` 或 `./.venv/bin/python`。

### 准备 FFmpeg

需要带有 `libx264` 与 `aac` 编码器的 FFmpeg。先确认当前终端能找到它：

```text
ffmpeg -version
ffmpeg -hide_banner -encoders
```

如果已有 FFmpeg，但未加入 `PATH`，可仅对当前终端增加它的所在目录。例如程序位于 `D:\Tools\ffmpeg\ffmpeg.exe` 时：

```powershell
$env:PATH = 'D:\Tools\ffmpeg;' + $env:PATH
ffmpeg -version
```

路径应指向包含可执行文件的目录。上述命令不修改系统或用户的永久环境变量。

### 准备中文字体

[渲染脚本](../scripts/render_epicycle_video.py) 按 `font_candidates` 的顺序寻找字体：

- Linux：列出的 Noto Sans CJK 路径；最后还提供 DejaVu Sans 候选。
- macOS：`/System/Library/Fonts/PingFang.ttc`。
- Windows：`C:/Windows/Fonts/msyhbd.ttc` 或 `C:/Windows/Fonts/simhei.ttf`。

若都不存在，脚本会提示找不到支持的字体。可以将本机已有中文字体的路径加入 `font_candidates` 并优先选择它。DejaVu Sans 可用于拉丁文字，但不能保证中文正常显示；出现方框时应换成中文字体。

## 一键运行

在项目根目录执行：

```text
python run_all.py
```

入口顺序执行轮廓提取、音频合成、视频渲染。启动前检查 FFmpeg 是否可找到；任一子进程失败都会停止后续阶段并返回错误。

从其他目录启动时，向解释器传入 `run_all.py` 的实际路径即可。输入和输出位置仍以项目目录为准。

## 分步运行

```text
python scripts/prepare_tour_data.py
python scripts/generate_soundtrack.py
python scripts/render_epicycle_video.py
```

| 步骤 | 输入 | 输出 |
| --- | --- | --- |
| 轮廓提取 | `assets/capture_temp.jpg` | `output/data/naiwa_tour_data.npz` |
| 音频合成 | 脚本中的和弦、节拍与笑声时间表 | `output/audio/naiwa_soundtrack.wav`、`output/data/audio_sync_features.npz` |
| 视频渲染 | 参考图、轮廓数据、WAV 与同步数据 | `output/` 下的 MP4、GIF 及 `output/previews/` 截图 |

前两步互不依赖，第三步需要它们都完成。只修改画面逻辑时，可以保留已有中间文件并单独执行第三步；修改音频时序后，应先重新生成音频和同步数据。

## 辅助可视化工具

```text
python tools/extract_vectors.py
python tools/preview_dft_tour.py
python tools/preview_laugh_rig.py
```

| 工具 | 输出到 `output/diagnostics/` | 用途 |
| --- | --- | --- |
| `extract_vectors.py` | `vector_segments.png` | 对照原图、提取轮廓与叠加结果 |
| `preview_dft_tour.py` | `dft_reconstructions.png` | 对比 5、18、60、200、800 项的重建效果 |
| `preview_laugh_rig.py` | `laugh_poses_test_v2.png` | 对比平静、吸气、大笑等六种姿态 |

这些工具是独立的可视化实验，不是自动化断言测试；部分逻辑与主管线有所区别。修改辅助图的参数不会自动改变最终视频。

## 参数位置与修改约束

| 内容 | 位置 | 注意事项 |
| --- | --- | --- |
| 参考图与轮廓阈值 | `assets/capture_temp.jpg`、`scripts/prepare_tour_data.py` | 阈值、腹部区域和特征坐标针对当前图片编写 |
| 闭环采样点数 | 轮廓脚本中的 `N` | 修改后需要重建轮廓数据 |
| 音频长度、采样率、节拍 | 音频脚本中的 `DURATION`、`SR`、`BEAT_DUR`、`BAR_DUR` | 需要同步检查乐句、笑声时间表和动画阶段 |
| 帧率 | 音频脚本中的 `FPS` | 渲染脚本从同步数据读取；修改后应重新生成音频同步数据 |
| 输出尺寸与谐波项数 | 渲染脚本中的 `W`、`H`、`MAX_M` | HUD、相机和摆放坐标含固定值，不能仅改尺寸就认为已适配 |
| 嘴部、眼部、手部与腹部变形 | 渲染脚本中的 `render_laughing_naiwa_roi()` | 使用参考图像素坐标，替换图像时需要重新校准 |
| GIF 截取范围 | 渲染循环中收集 `gif_frames` 的条件 | 当前截取约 20.1–25.1 秒的隔帧画面 |

视频生成主管线目前没有命令行参数或统一配置文件。修改时序、分辨率或输入图时，应同时审查关联坐标与曲线，避免只改一个常量造成画面裁切或声画错位。浏览器资源导出工具的选项见 [HTML 演示说明](WEB_DEMO.md)。

## 常见问题

### `python` 或 `py` 找不到解释器

确认本机 Python 的实际安装位置。也可以直接调用 `python.exe` 的完整路径，再用同一个解释器执行 `-m pip` 安装依赖。不要混用不同解释器的 `pip` 与运行命令。

### `ModuleNotFoundError`

用运行项目的同一个解释器执行 `-m pip install -r requirements.txt`。虚拟环境中的包不会自动出现在其他 Python 环境。

### `FFmpeg was not found on PATH`

在同一终端执行 `ffmpeg -version`，确认终端可找到程序。安装 Python 包不能解决外部 FFmpeg 缺失的问题。

### `Missing input` 或参考图无法读取

确认 `assets/capture_temp.jpg` 可读。渲染阶段缺少 NPZ 或 WAV 时，按错误提示先运行相应准备脚本；也可重新运行一键入口。

### 中文显示方框或字体无法打开

检查 `font_candidates` 中的文件是否存在，并将支持中文的本机字体放在候选列表前面。

### GIF 没有声音，或时长与截取范围不同

GIF 不包含音轨；带声音的成片是 MP4。GIF 帧延时以 10 毫秒为单位，当前脚本设置的 66 毫秒在已验证环境中编码为 60 毫秒，因此 75 帧成品实际播放约 4.5 秒。

### 渲染失败或生成文件不完整

保留终端异常与 FFmpeg 错误信息。渲染脚本检查编码退出码；文件存在不代表编码完成。重新生成会覆盖同名输出，需保留的版本应先另存。
