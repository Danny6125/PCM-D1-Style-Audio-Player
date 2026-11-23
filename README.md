# PCMDeck Player

A retro-styled desktop audio player built with **Python + PySide6**, featuring stereo analog VU meters, a digital LCD-style panel and VLC-based playback.

本仓库使用当前上传的 PCMDeckPlayer 版本源码，适用于 macOS（其他平台可能需要额外配置）。

## 环境要求

- Python 3.11 或 3.12（建议）
- VLC Media Player（提供 `libVLC`，必需）
- FFmpeg / ffprobe（音频分析与部分音频格式转换）
- macOS 和 VS Code（推荐）

## macOS 上启动（VS Code / 终端）

1. 克隆仓库，或下载 Code → Download ZIP 后解压。
2. 在 VS Code 里 **File → Open Folder**，打开包含 `main.py` 和 `requirements.txt` 的 `PCMDeckPlayer` 文件夹。
3. 打开 VS Code 内置终端，按顺序运行：

```bash
# 先安装系统工具（如未安装 Homebrew，请先安装 Homebrew）
brew install ffmpeg
brew install --cask vlc

# 在项目根目录下创建隔离的 Python 环境
python3 -m venv .venv
source .venv/bin/activate

# 安装 Python 依赖
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 启动播放器
python main.py
```

如果 VS Code 提示选择解释器，使用 Command+Shift+P → `Python: Select Interpreter` → `.venv/bin/python`。

**注意**：`python-vlc` 是 Python 封装，不能代替 VLC 应用所提供的 `libVLC`。如果出现 `no function 'libvlc_new'` 或 `Cannot find libvlc`，请确认已安装 VLC，完全退出并重新打开 VS Code 后再试。

## 以后再次启动

在项目目录打开终端：

```bash
source .venv/bin/activate
python main.py
```

## 操作简介

- `OPEN`：选择音频文件
- `PLAY / PAUSE`：播放或暂停
- `STOP`：停止播放
- `FR / PREV`、`FF / NEXT`：切换曲目/快进快退（依程序当前状态）
- `LIGHT`：切换 LCD 与 VU 表的背光效果
- 改变窗口宽高比可以切换窗口式圆形 VU 和宽屏双联 VU 布局

支持的格式以当前 VLC / FFmpeg 的解码能力为准；DSD / ISO 可能需要转码，且并非所有 ISO 都能成功读取。

## 目录结构

```text
PCMDeckPlayer/
├── main.py              # 程序入口
├── requirements.txt      # Python 依赖
├── config.py             # 配置
├── core/                 # 播放、分析、元数据、转码
└── ui/                   # 窗口、LCD、VU 表
```

## 排错

- `ModuleNotFoundError`：确认已激活 `.venv` 并执行了 `pip install -r requirements.txt`。
- VLC 加载失败：先安装 VLC.app，并重启终端或 VS Code。
- FFmpeg 未找到：运行 `brew install ffmpeg`，用 `ffmpeg -version` 检查。
- macOS 无法启动 UI：确认是在有图形桌面的 macOS 会话中运行，而不是无图形显示的远程终端。

> 本仓库不包含虚拟环境、缓存及用户个人音频文件。请勿把凭据、个人文件或音乐素材提交进仓库。
