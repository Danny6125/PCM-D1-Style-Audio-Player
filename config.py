# config.py

from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".aiff", ".aif",
    ".m4a", ".aac", ".ogg", ".opus", ".wma",
    ".ape", ".wv", ".tta", ".alac", ".caf",
    ".ac3", ".mp2", ".mp1", ".mka",

    # 允许尝试 DSD / ISO
    ".dsf", ".dff", ".iso"
}

DSD_ISO_EXTENSIONS = {
    ".dsf", ".dff", ".iso"
}

APP_NAME = "PCMDeck Player"
WINDOW_WIDTH = 590
WINDOW_HEIGHT = 760

CACHE_DIR = Path.home() / ".pcmdeck_cache"

# 扫描当前文件夹 + 两级子文件夹
FOLDER_SCAN_DEPTH = 2