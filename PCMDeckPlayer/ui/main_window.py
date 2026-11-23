# ui/main_window.py

import random
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)

from config import SUPPORTED_EXTENSIONS, APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT
from core.player import VLCPlayer
from core.metadata import TrackInfo
from core.analyzer import FFmpegLevelAnalyzer
from core.utils import format_time
from core.transcoder import get_or_create_playable_path
from core.playlist import Playlist

from ui.vu_meter import StereoVUMeter
from ui.lcd_panel import LCDPanel


class PCMDeckWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.player = VLCPlayer()
        self.analyzer = FFmpegLevelAnalyzer()
        self.playlist = Playlist()

        self.track = TrackInfo()

        self.fake_left = 0.0
        self.fake_right = 0.0
        self.level_mode = "SIM"

        # 屏幕模式
        self.folder_select_mode = False
        self.main_menu_mode = False
        self.style_select_mode = False

        # 风格
        self.deck_style = "D1"
        self.style_selection_index = 0

        # 默认白绿色主题
        self.lcd_is_gray = True
        self.light_animations = []

        # 防止 FF / FR 按一次跳多首
        self.track_switch_locked = False
        self.manual_switch_until = 0.0

        self.was_playing = False
        self.pause_requested = False
        self.stop_requested = False

        self.build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)

        # 提高数字电平表刷新率：
        # 原先约 80ms，现在改为 25ms，约 40fps
        self.timer.start(25)

    def build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #101012;
                color: #eeeeee;
            }
            QPushButton {
                background-color: #252527;
                color: #f2f2f2;
                border: 1px solid #555;
                border-radius: 11px;
                padding: 8px;
                font-family: Menlo;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #36363a;
            }
            QPushButton:pressed {
                background-color: #0d0d0e;
            }
            QLabel {
                color: #eeeeee;
                font-family: Menlo;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(9)

        # =========================
        # 标题栏
        # =========================

        title_row = QHBoxLayout()

        self.title_label = QLabel("PCMDeck")
        self.title_label.setFont(QFont("Menlo", 28, QFont.Bold))

        self.subtitle_label = QLabel("D1 STYLE AUDIO PLAYER")
        self.subtitle_label.setFont(QFont("Menlo", 11, QFont.Bold))
        self.subtitle_label.setStyleSheet("color: #888;")

        title_col = QVBoxLayout()
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)

        self.status_label = QLabel("STOP")
        self.status_label.setFont(QFont("Menlo", 14, QFont.Bold))
        self.status_label.setStyleSheet("color: #ff9a2a;")

        title_row.addLayout(title_col)
        title_row.addStretch()
        title_row.addWidget(self.status_label)

        root.addLayout(title_row)

        # =========================
        # VU 表区域
        # D50 风格会隐藏整个 VU 区
        # =========================

        self.stereo_vu = StereoVUMeter()
        root.addWidget(self.stereo_vu)

        # 兼容原有逻辑中的 left_vu / right_vu 可见性判断
        self.left_vu = self.stereo_vu
        self.right_vu = self.stereo_vu

        # =========================
        # LCD 主屏幕
        # =========================

        self.lcd = LCDPanel()
        root.addWidget(self.lcd)

        # =========================
        # 按钮区
        # =========================

        btn_grid = QVBoxLayout()
        btn_grid.setSpacing(9)

        row1 = QHBoxLayout()
        self.open_btn = QPushButton("OPEN")
        self.play_btn = QPushButton("PLAY / PAUSE")
        self.stop_btn = QPushButton("STOP")
        row1.addWidget(self.open_btn)
        row1.addWidget(self.play_btn)
        row1.addWidget(self.stop_btn)

        row2 = QHBoxLayout()
        self.menu_btn = QPushButton("MENU")
        self.rew_btn = QPushButton("FR / PREV")
        self.ff_btn = QPushButton("FF / NEXT")
        self.light_btn = QPushButton("LIGHT")
        row2.addWidget(self.menu_btn)
        row2.addWidget(self.rew_btn)
        row2.addWidget(self.ff_btn)
        row2.addWidget(self.light_btn)

        btn_grid.addLayout(row1)
        btn_grid.addLayout(row2)

        root.addLayout(btn_grid)

        # 只有底部提示字靠近底端
        root.addStretch(1)

        self.footer = QLabel(
            "ACCESS  ●    MENU: FOLDER SELECT    RIGHT MENU: STYLE    FR/FF: PREV/NEXT"
        )
        self.footer.setFont(QFont("Menlo", 11, QFont.Bold))
        self.footer.setStyleSheet("color: #a46a22;")
        root.addWidget(self.footer)

        for btn in [
            self.open_btn,
            self.play_btn,
            self.stop_btn,
            self.menu_btn,
            self.rew_btn,
            self.ff_btn,
            self.light_btn,
        ]:
            btn.setAutoRepeat(False)

        self.open_btn.clicked.connect(self.open_action)
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.clicked.connect(self.stop)

        # 左键 MENU：文件夹选择 / 当前屏幕确认
        self.menu_btn.clicked.connect(self.menu_action)

        # 右键 MENU：进入屏幕菜单 STYLE
        self.menu_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.menu_btn.customContextMenuRequested.connect(self.enter_main_menu_screen)

        self.rew_btn.clicked.connect(self.fr_action)
        self.ff_btn.clicked.connect(self.ff_action)
        self.light_btn.clicked.connect(self.toggle_lcd_light)

        self.set_deck_style("D1")

    # =========================
    # 电平响应算法
    # =========================

    def _meter_response(self, value: float) -> float:
        """
        提高电平表灵敏度。

        原始电平如果直接线性显示，会显得很钝。
        这里用幂函数增强中低电平响应，让人声、钢琴、鼓点更容易推动电平表。
        """

        v = max(0.0, min(1.0, float(value)))

        # 中低电平增强
        v = pow(v, 0.48)

        # 轻微视觉增益
        v *= 1.08

        return max(0.0, min(1.0, v))

    def _smooth_meter(self, old: float, new: float) -> float:
        """
        真机电平表通常是：
        上升快，下降慢。
        """

        if new > old:
            # 快速上升，增强瞬态
            return old * 0.12 + new * 0.88

        # 缓慢回落，保留拖尾感
        return old * 0.82 + new * 0.18

    def _apply_meter_levels(self, left: float, right: float):
        left = self._meter_response(left)
        right = self._meter_response(right)

        self.fake_left = self._smooth_meter(self.fake_left, left)
        self.fake_right = self._smooth_meter(self.fake_right, right)

    # =========================
    # 屏幕模式
    # =========================

    def clear_screen_modes(self):
        self.folder_select_mode = False
        self.main_menu_mode = False
        self.style_select_mode = False

    def enter_playback_screen(self):
        self.clear_screen_modes()
        self.lcd.set_playback_mode()

    def enter_main_menu_screen(self, pos=None):
        self.clear_screen_modes()
        self.main_menu_mode = True

        self.lcd.set_main_menu_mode(selected_index=0)

        self.status_label.setText("MENU")
        self.status_label.setStyleSheet("color: #ffcc44;")

    def enter_style_select_screen(self):
        self.clear_screen_modes()
        self.style_select_mode = True

        self.style_selection_index = 0 if self.deck_style == "D1" else 1

        self.lcd.set_style_select_mode(
            selected_index=self.style_selection_index,
            current_style=self.deck_style
        )

        self.status_label.setText("STYLE")
        self.status_label.setStyleSheet("color: #ffcc44;")

    def refresh_style_select_screen(self):
        self.lcd.set_style_select_mode(
            selected_index=self.style_selection_index,
            current_style=self.deck_style
        )

    def apply_selected_style(self):
        if self.style_selection_index == 0:
            self.set_deck_style("D1")
        else:
            self.set_deck_style("D50")

        self.enter_playback_screen()

    # =========================
    # 风格设置
    # =========================

    def set_deck_style(self, style_name: str):
        self.deck_style = style_name

        self.lcd.set_deck_style(style_name)

        self.stereo_vu.set_deck_style(style_name)

        if style_name == "D50":
            # D50 风格：没有外部 VU 表，直接隐藏
            self.stereo_vu.setVisible(False)

            self.title_label.setText("PCMD50")
            self.subtitle_label.setText("PCM-D50 STYLE AUDIO PLAYER")

            self.footer.setText(
                "ACCESS  ●    STYLE: PCM-D50    RIGHT MENU: STYLE    FR/FF: PREV/NEXT"
            )

        else:
            # D1 风格：恢复外部 VU 表
            self.stereo_vu.setVisible(True)

            self.title_label.setText("PCMDeck")
            self.subtitle_label.setText("D1 STYLE AUDIO PLAYER")

            self.footer.setText(
                "ACCESS  ●    MENU: FOLDER SELECT    RIGHT MENU: STYLE    FR/FF: PREV/NEXT"
            )

        # D1 / D50 底部小字统一橙色
        self.footer.setStyleSheet("color: #a46a22;")

        self.lcd.update()
        self.stereo_vu.update()

    # =========================
    # 键盘绑定
    # =========================

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Up:
            self.fr_action()
            event.accept()
            return

        if key == Qt.Key_Down:
            self.ff_action()
            event.accept()
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.folder_select_mode:
                self.load_selected_folder_and_play()
                event.accept()
                return

            if self.main_menu_mode:
                self.enter_style_select_screen()
                event.accept()
                return

            if self.style_select_mode:
                self.apply_selected_style()
                event.accept()
                return

        if key == Qt.Key_Space:
            self.toggle_play()
            event.accept()
            return

        if key == Qt.Key_Escape:
            self.enter_playback_screen()
            event.accept()
            return

        super().keyPressEvent(event)

    # =========================
    # OPEN：文件 / 文件夹
    # =========================

    def open_action(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("OPEN")
        dialog.setText("选择打开方式")

        file_btn = dialog.addButton("打开单个文件", QMessageBox.AcceptRole)
        folder_btn = dialog.addButton("打开文件夹", QMessageBox.ActionRole)
        cancel_btn = dialog.addButton("取消", QMessageBox.RejectRole)

        dialog.exec()
        clicked = dialog.clickedButton()

        if clicked == file_btn:
            self.open_file()
        elif clicked == folder_btn:
            self.open_folder_dialog(show_selector=True)
        elif clicked == cancel_btn:
            return

    def open_file(self):
        filters = (
            "Audio Files (*.mp3 *.flac *.wav *.aiff *.aif *.m4a *.aac *.ogg *.opus "
            "*.wma *.ape *.wv *.tta *.alac *.caf *.ac3 *.mp2 *.mp1 *.mka "
            "*.dsf *.dff *.iso);;"
            "All Files (*)"
        )

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio File",
            str(Path.home()),
            filters,
        )

        if not path:
            return

        self.enter_playback_screen()

        self.playlist.load_files([path])
        self.play_current()

    def open_folder_dialog(self, show_selector=True):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Music Folder - Scan Current + 2 Levels",
            str(Path.home()),
        )

        if not folder:
            return

        count = self.playlist.load_root_folder(folder)

        if count <= 0:
            self.status_label.setText("NO AUDIO")
            self.status_label.setStyleSheet("color: #ff3333;")
            return

        self.status_label.setText(f"FOLDER {count}")
        self.status_label.setStyleSheet("color: #ffcc44;")

        if show_selector:
            self.enter_folder_select_mode()
        else:
            self.load_selected_folder_and_play()

    # =========================
    # MENU：左键文件夹选择
    # =========================

    def enter_folder_select_mode(self):
        if not self.playlist.folder_entries:
            self.open_folder_dialog(show_selector=True)
            return

        self.clear_screen_modes()
        self.folder_select_mode = True

        self.lcd.set_folder_select_mode(
            items=self.playlist.folder_items_for_ui(),
            selected_index=self.playlist.folder_selection_index,
            folder_pos=self.playlist.folder_position_text(),
        )

        self.status_label.setText("SELECT")
        self.status_label.setStyleSheet("color: #ffcc44;")

    def refresh_folder_select_screen(self):
        self.lcd.set_folder_select_mode(
            items=self.playlist.folder_items_for_ui(),
            selected_index=self.playlist.folder_selection_index,
            folder_pos=self.playlist.folder_position_text(),
        )

    def load_selected_folder_and_play(self):
        count = self.playlist.load_selected_folder_tracks()

        if count <= 0:
            self.status_label.setText("EMPTY")
            self.status_label.setStyleSheet("color: #ff3333;")
            return

        self.enter_playback_screen()
        self.play_current()

    def menu_action(self):
        if self.main_menu_mode:
            self.enter_style_select_screen()
            return

        if self.style_select_mode:
            self.apply_selected_style()
            return

        if self.folder_select_mode:
            self.load_selected_folder_and_play()
            return

        if not self.playlist.folder_entries:
            self.open_folder_dialog(show_selector=True)
            return

        self.enter_folder_select_mode()

    # =========================
    # 播放当前歌曲
    # =========================

    def play_current(self):
        original_path = self.playlist.current()

        if not original_path:
            return

        ext = Path(original_path).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            self.status_label.setText("TRY FORMAT")
            self.status_label.setStyleSheet("color: #ffcc44;")

        self.status_label.setText("PREPARING")
        self.status_label.setStyleSheet("color: #ffcc44;")
        QApplication.processEvents()

        # 切歌前先停止旧播放和旧分析
        self.player.stop()
        self.analyzer.stop()
        self.was_playing = False

        result = get_or_create_playable_path(original_path)

        if not result.play_path:
            self.status_label.setText(result.message)
            self.status_label.setStyleSheet("color: #ff3333;")

            QMessageBox.warning(
                self,
                "ISO / DSD 无法播放",
                "该 ISO / DSD 文件无法被当前 FFmpeg/VLC 解码。\n\n"
                "如果这是 SACD ISO，普通 FFmpeg 通常无法直接解析。\n"
                "可以先用专门工具提取为 DSF/DFF，再由本播放器转为 32bit WAV 播放。",
            )
            return

        self.player.load(result.play_path)

        original_info = TrackInfo.from_file(original_path)

        if result.converted:
            wav_info = TrackInfo.from_file(result.play_path)

            original_info.codec = f"{original_info.codec}→WAV"
            original_info.sample_rate = wav_info.sample_rate
            original_info.bit_depth = "32 bit"
            original_info.channels = wav_info.channels

            self.level_mode = result.message
        else:
            self.level_mode = result.message

        self.track = original_info

        self.pause_requested = False
        self.stop_requested = False

        self.player.play()
        self.analyzer.start(result.play_path)

    # =========================
    # 播放控制
    # =========================

    def toggle_play(self):
        # 菜单界面下，PLAY 用作确认键
        if self.main_menu_mode:
            self.enter_style_select_screen()
            return

        if self.style_select_mode:
            self.apply_selected_style()
            return

        if self.folder_select_mode:
            self.load_selected_folder_and_play()
            return

        # 没有载入歌曲时，按 PLAY 打开文件
        if self.player.current_path is None:
            self.open_action()
            return

        # 正在播放：按 PLAY / PAUSE 暂停
        if self.player.is_playing():
            self.pause_requested = True
            self.stop_requested = False

            self.player.pause()
            self.analyzer.stop()
            return

        # 没有播放，但已经载入过歌曲：
        # 可能是暂停，也可能是刚刚按过 STOP。
        # 这里必须用 play()，不能用 pause()。
        self.pause_requested = False
        self.stop_requested = False

        self.player.play()

        # STOP 后重新 PLAY，需要重新启动电平分析
        if self.player.current_path:
            self.analyzer.start(self.player.current_path)

    def stop(self):
        self.stop_requested = True
        self.pause_requested = False

        self.player.stop()
        self.analyzer.stop()

        self.fake_left = 0.0
        self.fake_right = 0.0
        self.level_mode = "SIM"

        if self.stereo_vu.isVisible():
            self.stereo_vu.set_levels(0.0, 0.0)

        self.status_label.setText("STOP")
        self.status_label.setStyleSheet("color: #ff9a2a;")

        self.lcd.update_state(
            track=self.track,
            elapsed="00:00",
            total=self.track.duration,
            left=0.0,
            right=0.0,
            play_state="STOP",
            level_mode=self.level_mode,
            playlist_pos=self.playlist.position_text(),
        )

    # =========================
    # FR / FF
    # =========================

    def _begin_manual_track_switch(self):
        if self.track_switch_locked:
            return False

        self.track_switch_locked = True
        self.manual_switch_until = time.monotonic() + 1.0

        QTimer.singleShot(450, self._unlock_track_switch)
        return True

    def _unlock_track_switch(self):
        self.track_switch_locked = False

    def fr_action(self):
        if self.style_select_mode:
            self.style_selection_index -= 1
            self.style_selection_index %= 2
            self.refresh_style_select_screen()
            return

        if self.main_menu_mode:
            return

        if self.folder_select_mode:
            self.playlist.move_folder_selection(-1)
            self.refresh_folder_select_screen()
            return

        if not self._begin_manual_track_switch():
            return

        self.previous_track()

    def ff_action(self):
        if self.style_select_mode:
            self.style_selection_index += 1
            self.style_selection_index %= 2
            self.refresh_style_select_screen()
            return

        if self.main_menu_mode:
            return

        if self.folder_select_mode:
            self.playlist.move_folder_selection(1)
            self.refresh_folder_select_screen()
            return

        if not self._begin_manual_track_switch():
            return

        self.next_track()

    def previous_track(self):
        path = self.playlist.previous_track()

        if not path:
            return

        self.play_current()

    def next_track(self):
        path = self.playlist.next_track()

        if not path:
            return

        self.play_current()

    # =========================
    # LIGHT
    # =========================

    def toggle_lcd_light(self):
        start = self.lcd.themeMix

        self.lcd_is_gray = not self.lcd_is_gray
        end = 1.0 if self.lcd_is_gray else 0.0

        targets = [self.lcd, self.stereo_vu]

        self.light_animations = []

        for target in targets:
            animation = QPropertyAnimation(target, b"themeMix", self)
            animation.setDuration(650)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.setEasingCurve(QEasingCurve.InOutCubic)
            animation.start()

            self.light_animations.append(animation)

    # =========================
    # 定时刷新
    # =========================

    def on_timer(self):
        if self.folder_select_mode or self.main_menu_mode or self.style_select_mode:
            return

        playing = self.player.is_playing()

        if playing:
            if self.analyzer.is_active():
                left, right = self.analyzer.get_levels()

                if left > 0.0001 or right > 0.0001:
                    self._apply_meter_levels(left, right)

                    if self.level_mode not in {
                        "WAV 32",
                        "CACHE WAV 32",
                        "ISO MOUNT WAV 32",
                    }:
                        self.level_mode = "FAST LEVEL"
                else:
                    self._fake_meter()

                    if self.level_mode not in {
                        "WAV 32",
                        "CACHE WAV 32",
                        "ISO MOUNT WAV 32",
                    }:
                        self.level_mode = "SIM WAIT"
            else:
                self._fake_meter()

                if self.level_mode not in {
                    "WAV 32",
                    "CACHE WAV 32",
                    "ISO MOUNT WAV 32",
                }:
                    self.level_mode = "SIM FALLBACK"

            self.status_label.setText("PLAY")
            self.status_label.setStyleSheet("color: #4dff88;")
        else:
            self.fake_left *= 0.84
            self.fake_right *= 0.84

            if self.player.current_path:
                self.status_label.setText("PAUSE / STOP")
            else:
                self.status_label.setText("STOP")

            self.status_label.setStyleSheet("color: #ff9a2a;")

        if self.stereo_vu.isVisible():
            self.stereo_vu.set_levels(self.fake_left, self.fake_right)

        elapsed_ms = self.player.get_time()
        total_ms = self.player.get_length()

        if total_ms <= 0 and self.track.duration != "00:00":
            total_text = self.track.duration
        else:
            total_text = format_time(total_ms)

        self.lcd.update_state(
            track=self.track,
            elapsed=format_time(elapsed_ms),
            total=total_text,
            left=self.fake_left,
            right=self.fake_right,
            play_state="PLAY" if playing else "STOP",
            level_mode=self.level_mode,
            playlist_pos=self.playlist.position_text(),
        )

        if (
            self.was_playing
            and not playing
            and not self.pause_requested
            and not self.stop_requested
            and time.monotonic() > self.manual_switch_until
        ):
            if self.playlist.count() > 1:
                QTimer.singleShot(400, self.next_track)

        self.was_playing = playing

    def _fake_meter(self):
        target_left = random.uniform(0.10, 1.00)
        target_right = random.uniform(0.10, 1.00)

        self.fake_left = self._smooth_meter(self.fake_left, target_left)
        self.fake_right = self._smooth_meter(self.fake_right, target_right)