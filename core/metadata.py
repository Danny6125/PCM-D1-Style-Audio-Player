# core/metadata.py

from pathlib import Path
from mutagen import File as MutagenFile
from core.utils import format_time


class TrackInfo:
    """Audio metadata shown on the LCD panel."""

    def __init__(self):
        self.file_name = "NO FILE"
        self.codec = "----"
        self.sample_rate = "----"
        self.bit_depth = "----"
        self.channels = "----"
        self.duration = "00:00"

    @staticmethod
    def from_file(path: str):
        info = TrackInfo()
        p = Path(path)

        info.file_name = p.name
        info.codec = p.suffix.replace(".", "").upper() or "UNKNOWN"

        try:
            audio = MutagenFile(path)
            if audio is not None and hasattr(audio, "info"):
                meta = audio.info

                sample_rate = getattr(meta, "sample_rate", None)
                if sample_rate:
                    info.sample_rate = f"{sample_rate / 1000:.1f} kHz"

                bits_per_sample = getattr(meta, "bits_per_sample", None)
                if bits_per_sample:
                    info.bit_depth = f"{bits_per_sample} bit"

                channels = getattr(meta, "channels", None)
                if channels:
                    info.channels = f"{channels} CH"

                length = getattr(meta, "length", None)
                if length:
                    info.duration = format_time(int(length * 1000))
        except Exception:
            pass

        return info
