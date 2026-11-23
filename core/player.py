# core/player.py

import vlc


class VLCPlayer:
    """
    播放核心。
    当前使用 libVLC 负责真实音频播放。
    """

    def __init__(self):
        self.instance = vlc.Instance("--no-video")
        self.player = self.instance.media_player_new()
        self.current_path = None

    def load(self, path: str):
        self.current_path = path
        media = self.instance.media_new(path)
        self.player.set_media(media)

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def is_playing(self) -> bool:
        return bool(self.player.is_playing())

    def get_time(self) -> int:
        return self.player.get_time()

    def get_length(self) -> int:
        return self.player.get_length()

    def seek_relative(self, offset_ms: int):
        current = self.get_time()
        length = self.get_length()

        if current < 0:
            current = 0

        target = current + offset_ms

        if length > 0:
            target = max(0, min(length, target))
        else:
            target = max(0, target)

        self.player.set_time(target)