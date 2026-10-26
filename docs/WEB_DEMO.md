# HTML 互动演示

[返回 README](../README.md)

## 直接体验

双击打开 [`web/index.html`](../web/index.html)。页面使用原生 HTML、CSS、Canvas 2D 和浏览器音频，已包含所需素材，无需安装 Python 或前端依赖。

完整保留 `web/` 文件夹即可本地使用，也可以作为普通静态页面托管。已验证本地文件模式；尚未实际部署 GitHub Pages 或其他托管服务。

## 能玩什么

| 操作 | 结果 |
| --- | --- |
| 播放 / 暂停 | 控制 28.8 秒的四幕动画 |
| 拖动时间轴、点击阶段 | 查看任意时刻的画面，跳到谐波唤醒、描绘、显影或大笑 |
| 调节傅里叶项数 | 在 4–750 项之间重算轮廓与本轮链；开场逐级增加到设定上限 |
| 调节速度 | 0.5×、1×、1.5×、2×，音频与画面一起变化 |
| 开关圆圈、轨迹、镜头跟随 | 分别查看数学过程、描绘结果与全景画面 |
| 点击奶蛙或大笑按钮 | 开启声音，跳到 20.4 秒的大笑片段并播放 |
| 开关循环 | 控制结束后是否重播 |
| 放大舞台 | 在浏览器支持时进入全屏 |

声音默认关闭，首次播放需要主动操作。大笑按钮会主动打开声音；也可通过声音按钮单独开关。

键盘快捷键：空格播放或暂停，`L` 触发大笑，`M` 开关声音，左右方向键前后移动 2 秒。焦点位于按钮或输入控件时，保留控件本身的键盘行为；舞台获得焦点后，回车或空格触发大笑。

## 复现方式与范围

浏览器中的本轮链由原始轮廓的 FFT 系数实时计算，调整项数会实际改变绘制结果。轨迹、相机、小地图和频谱由 JavaScript 绘制，并沿用四幕时间线。

逐像素的角色变形没有移植到浏览器运行时。资源导出工具复用 [`preview_laugh_rig.py`](../tools/preview_laugh_rig.py) 中的变形函数，结合原音频同步曲线，预生成 15 fps 的角色帧图集；显影使用 40 帧透明图集插值。原配乐则压缩为 MP3，播放时以音频时间为画面时钟；音频无法播放时仍可静音观看。

因此，这是一份可交互的视觉复现，包含重新设计的页面、相机过渡与较轻量的变形图集，不保证与 Python MP4 逐像素一致。角色图集来自辅助变形实现，与主管线也有局部差异。将傅里叶项数调低只改变本轮与轮廓，参考图和预生成角色帧不会随之变成低细节图片。

初始页面暂停，`prefers-reduced-motion` 模式会关闭界面上的装饰性过渡。动画需主动播放；手机使用相同的画布与纵向控制布局。

## 文件职责

```text
web/
├── index.html               # 页面结构和可访问控件
├── style.css                # 桌面、手机和全屏布局
├── app.js                   # 本轮计算、绘图、时钟和交互
└── assets/
    ├── scene.js             # 系数、重建点、频谱和图集元数据
    ├── frog.png             # 透明参考图
    ├── reveal-0.webp        # 渐进显影图集
    ├── laugh-0.webp         # 大笑帧图集，第 1 页
    ├── laugh-1.webp         # 大笑帧图集，第 2 页
    ├── laugh-2.webp         # 大笑帧图集，第 3 页
    └── soundtrack.mp3       # 浏览器配乐
```

这些 `web/assets/` 文件虽然由工具导出，但属于页面运行必需资源，纳入 Git 提交。`output/` 中的成片、日志与单文件分享版仍被忽略。

数据通过普通 `<script>` 标签加载，运行时不请求 JSON 或远程 CDN；这是本地双击也能运行的原因。没有使用 `<video>` 播放预先编码的完整视频。

## 重新导出素材与单文件 HTML

如果修改了参考图、轮廓或配乐，先按照 [使用说明](USAGE.md) 重新生成前两步数据，再执行：

```text
python tools/export_web_assets.py
```

需要 Python 依赖和当前终端可找到的 FFmpeg。工具读取 `output/data/` 与 `output/audio/`，覆盖 `web/assets/`，并生成：

```text
output/web/naiwa_fourier_playground.html
```

单文件版包含 CSS、JavaScript、图像、图集和音轨，约 4 MB，可单独复制给他人并离线双击打开。

如果只修改了 HTML、CSS 或 JavaScript，无需重算角色帧，只重新打包：

```text
python tools/export_web_assets.py --bundle-only
```

`--bundle-only` 使用已经导出的 `web/assets/`，不调用 FFmpeg；执行该 Python 工具仍需要项目的 Python 依赖。

## 验证

已在本机 Chromium 中验证目录版和离线单文件版，包括暂停、拖动时间轴、四幕跳转、项数切换、绘图开关、声音开关、大笑触发、循环与结尾停止。390 px 宽手机视口无横向溢出。其他浏览器尚未实机验证。

浏览器验证脚本为 [`tests/test_web_browser.cjs`](../tests/test_web_browser.cjs)，运行需要本机已有 Node.js、Playwright Core 与 Chromium。这些是可选开发工具，不是打开页面的依赖。

```text
node tests/test_web_browser.cjs "<PLAYWRIGHT_CORE_MODULE_PATH>" "<CHROMIUM_EXECUTABLE_PATH>"
```

执行前替换为实际模块目录和浏览器可执行文件路径。若本地 `node_modules` 已能解析 `playwright-core` 且它能找到浏览器，也可以不传这两个参数。脚本将检查结果与桌面、手机截图写入 `output/web/`，并在结束时关闭所启动的浏览器。
