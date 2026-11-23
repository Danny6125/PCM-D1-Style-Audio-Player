# core/analyzer.py

import shutil
import subprocess
import threading
import numpy as np


class FFmpegLevelAnalyzer:
    """
    FFmpeg side-chain level analyzer.

    Strategy:
    1. VLC handles actual playback.
    2. FFmpeg decodes a parallel PCM stream.
    3. Python reads PCM from stdout.
    4. RMS + peak values drive the VU meters.

    DSD / ISO are not blocked. Whether they can be decoded depends on FFmpeg.
    """

    def __init__(self):
        self.process = None
        self.thread = None
        self.running = False

        self.left_level = 0.0
        self.right_level = 0.0

        self.available = shutil.which("ffmpeg") is not None
        self.lock = threading.Lock()

    def start(self, path: str):
        self.stop()

        if not self.available:
            return

        self.running = True
        self.left_level = 0.0
        self.right_level = 0.0

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-re",
            "-i", path,
            "-map", "a:0",
            "-f", "f32le",
            "-ac", "2",
            "-ar", "48000",
            "pipe:1",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except Exception:
            self.process = None
            self.running = False
            return

        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

        if self.process is not None:
            try:
                self.process.kill()
            except Exception:
                pass

        self.process = None
        self.thread = None

        with self.lock:
            self.left_level = 0.0
            self.right_level = 0.0

    def _read_loop(self):
        if self.process is None or self.process.stdout is None:
            return

        # 4096 frames * 2 channels * float32 4 bytes
        chunk_bytes = 4096 * 2 * 4

        while self.running:
            try:
                data = self.process.stdout.read(chunk_bytes)
            except Exception:
                break

            if not data:
                break

            try:
                samples = np.frombuffer(data, dtype=np.float32)
                if samples.size < 2:
                    continue

                usable = samples.size - (samples.size % 2)
                samples = samples[:usable]
                stereo = samples.reshape(-1, 2)

                left = stereo[:, 0]
                right = stereo[:, 1]

                l_rms = float(np.sqrt(np.mean(left * left)))
                r_rms = float(np.sqrt(np.mean(right * right)))

                l_peak = float(np.max(np.abs(left)))
                r_peak = float(np.max(np.abs(right)))

                # VU-like display: mostly RMS, with a little peak response.
                l_value = l_rms * 1.8 + l_peak * 0.25
                r_value = r_rms * 1.8 + r_peak * 0.25

                l_value = max(0.0, min(1.0, l_value))
                r_value = max(0.0, min(1.0, r_value))

                with self.lock:
                    self.left_level = self.left_level * 0.70 + l_value * 0.30
                    self.right_level = self.right_level * 0.70 + r_value * 0.30

            except Exception:
                continue

        self.running = False

    def get_levels(self):
        with self.lock:
            return self.left_level, self.right_level

    def is_active(self):
        return self.running and self.process is not None
