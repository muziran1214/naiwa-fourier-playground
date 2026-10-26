# 项目结构

目录方案已确认，源码、素材与生成文件已按下述结构整理。

[返回 README](../README.md)

## 目标

将现有奶蛙傅里叶动画项目整理为可上传 GitHub、可复现运行的源码仓库。保留现有图像处理、配乐合成和动画算法，以及根目录 `run_all.py` 一键入口。

采用脚本型目录，视频主管线包含三个阶段与三个辅助可视化工具；浏览器演示另设静态页面、资源导出工具和可选测试。无需引入 Python 安装包或前端应用框架，生成流程仍沿用现有 Python 依赖。

## 目录职责

```text
.
├── README.md                          # 项目介绍、效果预览、快速开始
├── requirements.txt                   # 现有 Python 依赖
├── run_all.py                         # 保留一键运行入口
├── .gitignore                         # 忽略生成物、缓存和本地环境
├── .gitattributes                     # 文本换行与二进制文件规则
├── assets/
│   └── capture_temp.jpg               # 现有参考图
├── scripts/
│   ├── prepare_tour_data.py           # 提取轮廓并生成闭环采样数据
│   ├── generate_soundtrack.py         # 合成配乐和逐帧同步数据
│   └── render_epicycle_video.py       # 渲染 MP4、GIF 和阶段预览
├── tools/
│   ├── extract_vectors.py            # 查看轮廓提取结果
│   ├── preview_dft_tour.py            # 比较不同项数的傅里叶重建
│   ├── preview_laugh_rig.py           # 查看笑脸与身体变形姿态
│   └── export_web_assets.py           # 导出浏览器图集、音轨与单文件 HTML
├── web/                              # 可双击打开的互动页面与必要素材
├── tests/                            # 浏览器交互与离线模式验证
├── docs/
│   ├── PROJECT_STRUCTURE.md          # 目录职责、迁移映射与约束
│   ├── USAGE.md                      # 环境准备、分步运行与常见问题
│   ├── PIPELINE.md                   # 数据流、阶段时序与算法说明
│   ├── WEB_DEMO.md                   # HTML 互动操作、素材导出与测试
│   ├── PUBLISHING.md                 # 本地检查与 GitHub 上传步骤
│   └── images/                       # README 使用的少量效果截图
└── output/                           # 自动生成，不纳入 Git
    ├── data/
    │   ├── naiwa_tour_data.npz
    │   └── audio_sync_features.npz
    ├── audio/
    │   └── naiwa_soundtrack.wav
    ├── previews/                     # 渲染阶段截图
    ├── diagnostics/                  # 三个辅助工具生成的对比图
    ├── logs/                         # 本地运行和验证日志（手动重定向）
    ├── archive/                      # 整理前已有成片的本地存档
    ├── web/                          # 单文件 HTML、浏览器检查结果和截图
    ├── naiwa_fourier_epicycle_reveal.mp4
    └── naiwa_belly_laugh.gif
```

`output/` 的子目录由需要它们的脚本创建。仓库提交代码、输入素材、文档、精选截图，以及 `web/assets/` 中运行互动页面所必需的图集、数据和 MP3。主管线的 MP4、GIF、WAV、NPZ、调试图和本地缓存保留在本机。

## 迁移映射

| 当前文件 | 目标位置 |
| --- | --- |
| `1_prepare_tour_data.py` | `scripts/prepare_tour_data.py` |
| `2_generate_soundtrack.py` | `scripts/generate_soundtrack.py` |
| `3_render_epicycle_video.py` | `scripts/render_epicycle_video.py` |
| `utils_extract_vectors.py` | `tools/extract_vectors.py` |
| `utils_test_dft_tour.py` | `tools/preview_dft_tour.py` |
| `utils_test_laugh_rig.py` | `tools/preview_laugh_rig.py` |
| `capture_temp.jpg` | `assets/capture_temp.jpg` |
| 根目录的 `*.npz` | `output/data/` |
| `naiwa_soundtrack.wav` | `output/audio/naiwa_soundtrack.wav` |
| 根目录的 `preview_*.png` | `output/previews/` |
| 已生成的日志 | `output/logs/` |
| 现有 MP4、GIF | 保留在 `output/` |

辅助脚本当前主要用于输出可视化结果，因此使用 `tools/` 和 `preview_` 命名，不把它们描述为自动化断言测试。

## 路径与启动约定

- 使用 `pathlib.Path(__file__).resolve()` 定位项目根目录，输入输出不依赖终端当前目录。
- `run_all.py` 使用当前 Python 解释器，按原顺序启动三个脚本，并检查子进程退出码。
- 单独运行阶段脚本时，缺失上游产物应给出相应生成步骤。
- 继续通过外部 `ffmpeg` 编码；文档明确它与 `requirements.txt` 中 Python 包的区别。
- 保留视频文件名、视频规格、配乐参数和阶段时序。
- 不修改系统 PATH，不安装依赖，不自动执行 GitHub 发布。

## 文档范围

README 展示效果、项目能力、快速运行和输出位置；详细操作放入 `USAGE.md`，实现原理放入 `PIPELINE.md`，首次上传步骤放入 `PUBLISHING.md`。

文档应准确说明：动画使用二维参考图与 OpenCV 图像变形保留泥塑外观，并非三维建模或三维物理模拟。轮廓与变形参数针对随附图片编写，替换任意图片并不能保证得到相同效果。

## 整理范围与验证方式

1. 迁移脚本、素材与已生成文件，同步修正文件引用。
2. 重写 README，补充使用说明、原理说明、上传说明与忽略规则。
3. 检查所有 Python 文件语法、文档相对链接与 Git 忽略匹配。
4. 从其他工作目录启动一键入口，验证路径独立性。
5. 完整生成视频并解码检查：720×1280、30 fps、864 帧、28.8 秒，音轨存在；GIF 可逐帧读取并循环播放。
6. 运行三个辅助工具，确认诊断图写入 `output/diagnostics/`。

这些是本次整理采用的验证方式，不代表仓库已经配置持续集成。辅助脚本使用 Matplotlib 非交互后端，只输出图片，不弹出窗口。

首次目录整理在 Windows 环境中完成以上检查：7 个 Python 文件通过语法检查，19 个文档相对链接有效，三个辅助工具正常输出；从 `docs/` 目录启动一键入口后，MP4 与 GIF 均成功生成。视频全部 864 帧及音轨通过 FFmpeg 解码检查，生成的 MP4、GIF 与整理前成品的 SHA-256 分别一致。

新增互动版后，目录版与离线单文件版均通过 Chromium 浏览器检查，覆盖项数、轨迹、相机、时间轴、真实音频播放及同步、循环和手机布局。具体实现边界与测试命令见 [HTML 演示说明](WEB_DEMO.md)。

初次目录整理通过临时 Git 工作树配置验证，18 个文件符合当时的入库范围。新增浏览器演示后，`web/`、导出工具、浏览器测试与相应文档也纳入源码范围；`output/`、虚拟环境、本地配置和 `node_modules/` 继续被忽略。验证记录保存在本机 `output/logs/` 与 `output/web/`，不纳入源码提交。

许可证尚未由项目所有者指定，本次整理不自动选择许可证，也不编造仓库地址、作者信息或素材来源。
