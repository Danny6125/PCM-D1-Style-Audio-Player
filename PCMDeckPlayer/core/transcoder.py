# core/transcoder.py

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from config import CACHE_DIR, DSD_ISO_EXTENSIONS, SUPPORTED_EXTENSIONS


class TranscodeResult:
    def __init__(self, play_path, converted=False, message="DIRECT", target_rate=None):
        self.play_path = play_path
        self.converted = converted
        self.message = message
        self.target_rate = target_rate


def is_dsd_or_iso(path: str) -> bool:
    return Path(path).suffix.lower() in DSD_ISO_EXTENSIONS


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def _hdiutil_available() -> bool:
    return shutil.which("hdiutil") is not None


def _get_source_sample_rate(path: str):
    if not _ffprobe_available():
        return None

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        text = output.decode("utf-8", errors="ignore").strip()
        if text.isdigit():
            return int(text)
    except Exception:
        return None

    return None


def _choose_pcm_rate(source_rate):
    """
    DSD 转 PCM 时，不能直接使用 2.8224MHz / 5.6448MHz 作为 WAV 采样率。
    这里转换为常见 Hi-Res PCM 采样率。
    """

    if not source_rate:
        return 176400

    if source_rate >= 11289600:
        return 352800

    if source_rate >= 5644800:
        return 352800

    if source_rate >= 2822400:
        return 176400

    common_pcm_rates = {
        44100, 48000, 88200, 96000,
        176400, 192000, 352800, 384000
    }

    if source_rate in common_pcm_rates:
        return source_rate

    return 176400


def _cache_file_name(path: str, target_rate: int) -> Path:
    p = Path(path)

    try:
        stat = p.stat()
        raw = f"{p.resolve()}-{stat.st_mtime}-{stat.st_size}-{target_rate}-32bit"
    except Exception:
        raw = f"{p.resolve()}-{target_rate}-32bit"

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    safe_name = p.stem[:40].replace("/", "_").replace(":", "_")

    return CACHE_DIR / f"{safe_name}_{target_rate}_32bit_{digest}.wav"


def _transcode_to_32bit_wav(input_path: str, output_path: Path, target_rate: int) -> bool:
    """
    将输入文件转成 32bit PCM WAV。
    """

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-map", "a:0",
        "-vn",
        "-ac", "2",
        "-ar", str(target_rate),
        "-acodec", "pcm_s32le",
        str(output_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return (
            result.returncode == 0
            and output_path.exists()
            and output_path.stat().st_size > 1024
        )
    except Exception:
        return False


def _find_audio_files_inside(folder: Path):
    """
    扫描挂载后的 ISO 目录，寻找里面的音频文件。
    """

    candidates = []

    try:
        for item in folder.rglob("*"):
            if not item.is_file():
                continue

            suffix = item.suffix.lower()

            if suffix in SUPPORTED_EXTENSIONS and suffix != ".iso":
                candidates.append(item)
    except Exception:
        pass

    # 优先找 DSD / WAV / FLAC 这类更可能是真实音频的文件
    priority = {
        ".dsf": 0,
        ".dff": 1,
        ".wav": 2,
        ".flac": 3,
        ".aiff": 4,
        ".aif": 5,
        ".m4a": 6,
        ".aac": 7,
        ".mp3": 8,
    }

    candidates.sort(
        key=lambda p: (
            priority.get(p.suffix.lower(), 99),
            str(p).lower()
        )
    )

    return candidates


def _try_mount_iso_and_transcode(iso_path: str, output_path: Path, target_rate: int) -> bool:
    """
    macOS 专用：
    用 hdiutil 挂载 ISO，然后扫描里面的音频文件，再转成 32bit WAV。
    """

    if not _hdiutil_available():
        return False

    mount_dir = Path(tempfile.mkdtemp(prefix="pcmdeck_iso_"))
    mounted = False

    try:
        attach_cmd = [
            "hdiutil",
            "attach",
            "-nobrowse",
            "-readonly",
            "-mountpoint",
            str(mount_dir),
            iso_path
        ]

        result = subprocess.run(
            attach_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode != 0:
            return False

        mounted = True

        audio_files = _find_audio_files_inside(mount_dir)

        if not audio_files:
            return False

        # 找到第一个可疑音频文件，转成 WAV
        source_audio = str(audio_files[0])
        return _transcode_to_32bit_wav(source_audio, output_path, target_rate)

    finally:
        if mounted:
            try:
                subprocess.run(
                    ["hdiutil", "detach", str(mount_dir), "-force"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

        try:
            shutil.rmtree(mount_dir, ignore_errors=True)
        except Exception:
            pass


def get_or_create_playable_path(path: str) -> TranscodeResult:
    """
    普通音频：直接返回。
    DSF / DFF：转 32bit WAV。
    ISO：优先 FFmpeg 直接转；失败后尝试挂载 ISO 后提取音频再转。
    """

    p = Path(path)
    ext = p.suffix.lower()

    if ext not in DSD_ISO_EXTENSIONS:
        return TranscodeResult(
            play_path=path,
            converted=False,
            message="DIRECT",
            target_rate=None
        )

    if not _ffmpeg_available():
        return TranscodeResult(
            play_path=path,
            converted=False,
            message="NO FFMPEG",
            target_rate=None
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    source_rate = _get_source_sample_rate(path)
    target_rate = _choose_pcm_rate(source_rate)

    # ISO 默认给 176.4kHz；如果 ffprobe 能识别再按识别结果来
    if ext == ".iso" and not source_rate:
        target_rate = 176400

    output_path = _cache_file_name(path, target_rate)

    if output_path.exists() and output_path.stat().st_size > 1024:
        return TranscodeResult(
            play_path=str(output_path),
            converted=True,
            message="CACHE WAV 32",
            target_rate=target_rate
        )

    # 第一轮：FFmpeg 直接尝试
    if _transcode_to_32bit_wav(path, output_path, target_rate):
        return TranscodeResult(
            play_path=str(output_path),
            converted=True,
            message="WAV 32",
            target_rate=target_rate
        )

    # 第二轮：ISO 尝试挂载后转码
    if ext == ".iso":
        if _try_mount_iso_and_transcode(path, output_path, target_rate):
            return TranscodeResult(
                play_path=str(output_path),
                converted=True,
                message="ISO MOUNT WAV 32",
                target_rate=target_rate
            )

        return TranscodeResult(
            play_path=None,
            converted=False,
            message="ISO UNSUPPORTED",
            target_rate=target_rate
        )

    # DSF / DFF 如果转码失败，仍然让 VLC 直接试一下
    return TranscodeResult(
        play_path=path,
        converted=False,
        message="TRANSCODE FAILED",
        target_rate=target_rate
    )