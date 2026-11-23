# core/playlist.py

from dataclasses import dataclass
from pathlib import Path

from config import SUPPORTED_EXTENSIONS, FOLDER_SCAN_DEPTH


@dataclass
class FolderEntry:
    path: str
    name: str
    depth: int
    count: int


class Playlist:
    def __init__(self):
        self.tracks = []
        self.index = -1

        self.root_folder = None
        self.folder_entries = []
        self.folder_selection_index = 0

    def clear(self):
        self.tracks = []
        self.index = -1
        self.root_folder = None
        self.folder_entries = []
        self.folder_selection_index = 0

    def load_files(self, paths):
        self.tracks = [str(Path(p)) for p in paths]
        self.index = 0 if self.tracks else -1
        return len(self.tracks)

    def _audio_files_directly_in(self, folder: Path):
        files = []

        try:
            for item in folder.iterdir():
                if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(str(item))
        except Exception:
            pass

        files.sort(key=lambda x: x.lower())
        return files

    def load_root_folder(self, folder_path: str, max_depth: int = FOLDER_SCAN_DEPTH):
        """
        扫描当前文件夹 + 两级子文件夹。
        只把“直接包含音频文件”的文件夹加入菜单列表。
        """

        base = Path(folder_path).resolve()

        if not base.exists() or not base.is_dir():
            self.clear()
            return 0

        self.root_folder = str(base)
        self.folder_entries = []
        self.folder_selection_index = 0
        self.tracks = []
        self.index = -1

        candidate_folders = [base]

        for item in base.rglob("*"):
            if not item.is_dir():
                continue

            try:
                depth = len(item.relative_to(base).parts)
            except Exception:
                depth = 999

            if depth <= max_depth:
                candidate_folders.append(item)

        candidate_folders.sort(key=lambda p: str(p).lower())

        for folder in candidate_folders:
            files = self._audio_files_directly_in(folder)

            if not files:
                continue

            try:
                depth = len(folder.relative_to(base).parts)
            except Exception:
                depth = 0

            if depth == 0:
                name = "[ROOT]"
            else:
                name = " / ".join(folder.relative_to(base).parts)

            self.folder_entries.append(
                FolderEntry(
                    path=str(folder),
                    name=name,
                    depth=depth,
                    count=len(files)
                )
            )

        return len(self.folder_entries)

    def folder_items_for_ui(self):
        items = []

        for entry in self.folder_entries:
            items.append({
                "name": entry.name,
                "depth": entry.depth,
                "count": entry.count,
                "path": entry.path
            })

        return items

    def move_folder_selection(self, delta: int):
        if not self.folder_entries:
            return None

        self.folder_selection_index += delta
        self.folder_selection_index %= len(self.folder_entries)

        return self.folder_entries[self.folder_selection_index]

    def selected_folder(self):
        if not self.folder_entries:
            return None

        self.folder_selection_index = max(
            0,
            min(self.folder_selection_index, len(self.folder_entries) - 1)
        )

        return self.folder_entries[self.folder_selection_index]

    def load_selected_folder_tracks(self):
        entry = self.selected_folder()

        if entry is None:
            return 0

        files = self._audio_files_directly_in(Path(entry.path))

        self.tracks = files
        self.index = 0 if self.tracks else -1

        return len(self.tracks)

    def current(self):
        if 0 <= self.index < len(self.tracks):
            return self.tracks[self.index]
        return None

    def next_track(self):
        if not self.tracks:
            return None

        self.index += 1

        if self.index >= len(self.tracks):
            self.index = 0

        return self.current()

    def previous_track(self):
        if not self.tracks:
            return None

        self.index -= 1

        if self.index < 0:
            self.index = len(self.tracks) - 1

        return self.current()

    def count(self):
        return len(self.tracks)

    def position_text(self):
        if not self.tracks or self.index < 0:
            return "0/0"

        return f"{self.index + 1}/{len(self.tracks)}"

    def folder_position_text(self):
        if not self.folder_entries:
            return "0/0"

        return f"{self.folder_selection_index + 1}/{len(self.folder_entries)}"