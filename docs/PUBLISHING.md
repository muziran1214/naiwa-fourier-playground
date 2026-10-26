# 上传 GitHub

[返回 README](../README.md) · [项目结构](PROJECT_STRUCTURE.md)

本项目已整理为源码仓库结构。实际 GitHub 地址由你创建仓库后填写，本文不假设用户名、仓库名或远程地址。

## 哪些内容提交

| 提交到源码仓库 | 保留在本机，Git 忽略 |
| --- | --- |
| `README.md`、`requirements.txt`、`run_all.py` | `output/` 下的 MP4、GIF、WAV、NPZ、日志、缓存和诊断图 |
| `scripts/`、`tools/` | `.venv/`、Python 字节码与本地编辑器配置 |
| `web/`（包括页面必需的 `assets/`）、`tests/` | `node_modules/` 与单文件 HTML 分享版 |
| `assets/capture_temp.jpg` | `.env` 和 `.env.*` 本地配置 |
| `docs/` 和两张精选效果图 | 旧版本成片与本地运行存档 |
| `.gitignore`、`.gitattributes` | |

README 使用 `docs/images/` 中的截图，即使没有上传 `output/`，仓库主页仍可展示效果。

Git 忽略规则只影响尚未跟踪的文件。若之后主动提交了生成文件，新增忽略规则不会自动移除它们，因此首次提交前应检查暂存区。

## 首次提交

在项目根目录执行。以下命令只创建本地仓库和提交；请先确认当前目录就是本项目。

```text
git init
git branch -M main
git add README.md requirements.txt run_all.py .gitignore .gitattributes assets scripts tools docs web tests
git diff --cached --stat
git status --short
```

确认暂存内容中没有 `output/`、虚拟环境或本地配置后，再提交：

```text
git commit -m "Organize Milk Frog Fourier animation project"
```

如果 Git 提示缺少作者信息，先按你实际使用的身份配置本仓库，再重试提交：

```text
git config user.name "<YOUR_GIT_NAME>"
git config user.email "<YOUR_GIT_EMAIL>"
```

这些尖括号内容是占位符，执行前替换为真实值；上述作者设置仅对当前仓库生效。

## 连接远程仓库

在 GitHub 创建一个空仓库。如果已经在本地准备了 README 和提交，创建远程仓库时无需再生成 README、`.gitignore` 或许可证文件，以便直接推送本地提交。

将 `<GITHUB_REPOSITORY_URL>` 替换为该仓库页面提供的 HTTPS 或 SSH 地址：

```text
git remote add origin "<GITHUB_REPOSITORY_URL>"
git remote -v
git push -u origin main
```

需要事先具备该仓库的访问权限，并按你现有的 GitHub 认证方式完成认证。不要将访问令牌写入源码或文档。

若已经存在名为 `origin` 的远程，先查看 `git remote -v`，核对当前地址后再决定是否调整。若远程仓库已有提交，应先查看并整合其历史，不要直接强制推送。

## 分享成片

视频和 GIF 默认不进源码提交。需要展示完整视频时，可以在仓库创建后通过 Release 附件等方式另行分享，并把实际链接补到 README。当前 README 不包含尚不存在的下载链接。

浏览器演示所需的 `web/assets/` 是例外：其中的图集、数据和压缩音轨是页面运行资源，需要随 `web/` 一起提交。供单独分享的 HTML 在 `output/web/` 中，不进入源码提交。

## 许可证与素材说明

当前项目未指定许可证，也未提供原参考图的作者和来源记录。本次目录整理没有自动创建 `LICENSE` 或假设素材来源。

如果希望明确允许他人使用、修改或分发代码，请由项目所有者选定许可证并补充 `LICENSE`；参考图与生成素材的说明应按实际来源单独补充。
