# ui/lcd_panel.py

import math

from PySide6.QtCore import Qt, Property, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget

from core.metadata import TrackInfo


def _mix(a, b, t):
    return int(a + (b - a) * t)


def _mix_color(c1, c2, t, alpha=255):
    return QColor(
        _mix(c1[0], c2[0], t),
        _mix(c1[1], c2[1], t),
        _mix(c1[2], c2[2], t),
        alpha
    )


class LCDPanel(QWidget):
    """
    主 LCD 屏。
    playback 模式：显示歌曲信息。
    folder_select 模式：显示二级文件夹条纹列表。
    main_menu 模式：右键 MENU 后显示 STYLE。
    style_select 模式：选择 D1 / D50 风格。
    """

    def __init__(self):
        super().__init__()

        self.track = TrackInfo()
        self.elapsed = "00:00"
        self.total = "00:00"
        self.left = 0.0
        self.right = 0.0
        self.play_state = "STOP"
        self.level_mode = "SIM"
        self.playlist_pos = "0/0"

        self.screen_mode = "playback"

        self.folder_items = []
        self.folder_selected_index = 0
        self.folder_pos = "0/0"

        self.main_menu_selected_index = 0

        self.style_selected_index = 0
        self.current_style = "D1"

        self.deck_style = "D1"

        # 默认白绿色
        self._theme_mix = 1.0

        self.setMinimumHeight(220)

    def set_deck_style(self, style_name: str):
        self.deck_style = style_name
        self.update()

    def get_theme_mix(self):
        return self._theme_mix

    def set_theme_mix(self, value):
        self._theme_mix = max(0.0, min(1.0, float(value)))
        self.update()

    themeMix = Property(float, get_theme_mix, set_theme_mix)

    def set_playback_mode(self):
        self.screen_mode = "playback"
        self.update()

    def set_folder_select_mode(self, items, selected_index, folder_pos):
        self.screen_mode = "folder_select"
        self.folder_items = items
        self.folder_selected_index = selected_index
        self.folder_pos = folder_pos
        self.update()

    def set_main_menu_mode(self, selected_index=0):
        self.screen_mode = "main_menu"
        self.main_menu_selected_index = selected_index
        self.update()

    def set_style_select_mode(self, selected_index=0, current_style="D1"):
        self.screen_mode = "style_select"
        self.style_selected_index = selected_index
        self.current_style = current_style
        self.update()

    def update_state(
        self,
        track,
        elapsed,
        total,
        left,
        right,
        play_state,
        level_mode,
        playlist_pos="0/0"
    ):
        self.track = track
        self.elapsed = elapsed
        self.total = total
        self.left = left
        self.right = right
        self.play_state = play_state
        self.level_mode = level_mode
        self.playlist_pos = playlist_pos

        if self.screen_mode not in {
            "folder_select",
            "main_menu",
            "style_select",
        }:
            self.screen_mode = "playback"

        self.update()

    def _colors(self):
        t = self._theme_mix

        if self.deck_style == "D50":
            return {
                "top": _mix_color((225, 142, 44), (198, 224, 190), t),
                "bottom": _mix_color((150, 70, 20), (126, 166, 130), t),
                "text": _mix_color((35, 15, 0), (12, 42, 24), t),
                "border": _mix_color((45, 20, 0), (52, 90, 60), t),
                "stripe_a": _mix_color((70, 30, 0), (176, 208, 170), t, 100),
                "stripe_b": _mix_color((35, 15, 0), (146, 182, 146), t, 75),
                "select": _mix_color((30, 10, 0), (64, 118, 72), t, 120),
                "bar_idle": _mix_color((40, 18, 0), (92, 120, 94), t, 90),
                "bar_active": _mix_color((55, 25, 0), (44, 104, 54), t),
                "bar_hot": _mix_color((120, 20, 0), (18, 74, 30), t),
            }

        return {
            "top": _mix_color((255, 174, 55), (226, 238, 220), t),
            "bottom": _mix_color((210, 75, 8), (164, 184, 166), t),
            "text": _mix_color((35, 15, 0), (24, 44, 30), t),
            "border": _mix_color((25, 12, 0), (76, 96, 78), t),
            "stripe_a": _mix_color((70, 30, 0), (195, 214, 190), t, 100),
            "stripe_b": _mix_color((35, 15, 0), (174, 198, 172), t, 75),
            "select": _mix_color((30, 10, 0), (82, 116, 88), t, 115),
            "bar_idle": _mix_color((40, 18, 0), (100, 120, 102), t, 90),
            "bar_active": _mix_color((55, 25, 0), (54, 86, 58), t),
            "bar_hot": _mix_color((120, 20, 0), (28, 60, 34), t),
        }

    def draw_bar(self, painter, x, y, w, h, level, label):
        c = self._colors()

        painter.setPen(c["text"])
        painter.setFont(QFont("Menlo", 13, QFont.Bold))
        painter.drawText(QRect(x, y, 20, h), Qt.AlignVCenter | Qt.AlignLeft, label)

        bar_x = x + 24
        bar_w = w - 24
        blocks = 24
        gap = 3
        block_w = (bar_w - gap * (blocks - 1)) / blocks

        # dB 映射，提高中低电平灵敏度
        db = 20 * math.log10(max(level, 0.0001))
        db = max(-60.0, min(0.0, db))
        ratio = (db + 60.0) / 60.0
        active = int(ratio * blocks)

        for i in range(blocks):
            bx = int(bar_x + i * (block_w + gap))

            color = c["bar_idle"]

            if i < active:
                color = c["bar_hot"] if i > 20 else c["bar_active"]

            painter.fillRect(bx, y, int(block_w), h, color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        c = self._colors()

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, c["top"])
        grad.setColorAt(1, c["bottom"])

        painter.setBrush(QBrush(grad))

        radius = 10 if self.deck_style == "D50" else 18
        painter.setPen(QPen(c["border"], 3))
        painter.drawRoundedRect(4, 4, w - 8, h - 8, radius, radius)

        if self.screen_mode == "folder_select":
            self._paint_folder_select(painter, w, h, c)
        elif self.screen_mode == "main_menu":
            self._paint_main_menu(painter, w, h, c)
        elif self.screen_mode == "style_select":
            self._paint_style_select(painter, w, h, c)
        else:
            self._paint_playback(painter, w, h, c)

    def _paint_playback(self, painter, w, h, c):
        painter.setPen(c["text"])

        if self.deck_style == "D50":
            pad_x = 28

            painter.setFont(QFont("Menlo", 14, QFont.Bold))
            title = self.track.file_name[:42]
            painter.drawText(pad_x, 28, w - pad_x * 2, 28, Qt.AlignLeft, title)

            painter.setFont(QFont("Menlo", 11, QFont.Bold))
            painter.drawText(w - 120, 30, 90, 22, Qt.AlignRight, self.playlist_pos)

            painter.setFont(QFont("Menlo", 34, QFont.Bold))
            painter.drawText(pad_x, 70, 260, 52, Qt.AlignLeft, self.elapsed)

            painter.setFont(QFont("Menlo", 14, QFont.Bold))
            painter.drawText(w - 150, 92, 115, 28, Qt.AlignRight, self.total)

            self.draw_bar(painter, pad_x, 136, w - pad_x * 2, 18, self.left, "L")
            self.draw_bar(painter, pad_x, 168, w - pad_x * 2, 18, self.right, "R")

            painter.setFont(QFont("Menlo", 12, QFont.Bold))
            line = (
                f"{self.track.codec}   "
                f"{self.track.sample_rate}   "
                f"{self.track.bit_depth}   "
                f"{self.track.channels}"
            )
            painter.drawText(pad_x, h - 58, w - pad_x * 2, 18, Qt.AlignLeft, line)

            painter.setFont(QFont("Menlo", 9, QFont.Bold))
            bottom_text = f"PCM-D50 STYLE  |  NO VU METER  |  LEVEL: {self.level_mode}"
            painter.drawText(pad_x, h - 34, w - pad_x * 2, 18, Qt.AlignLeft, bottom_text)
            return

        painter.setFont(QFont("Menlo", 16, QFont.Bold))
        title = self.track.file_name[:31]
        painter.drawText(20, 28, w - 40, 28, Qt.AlignLeft, title)

        painter.setFont(QFont("Menlo", 12, QFont.Bold))
        painter.drawText(w - 105, 30, 85, 24, Qt.AlignRight, self.playlist_pos)

        painter.setFont(QFont("Menlo", 15, QFont.Bold))
        painter.drawText(
            w - 95,
            56,
            75,
            24,
            Qt.AlignRight,
            "▶" if self.play_state == "PLAY" else "■"
        )

        # v37：进一步修复 00:00 与数字电平条的重叠。
        # 采用明确的垂直分区：标题区 / 时间区 / 电平区 / 信息区。
        # 时间字号略收小，并把 L/R 电平条固定放到时间数字下方。
        compact = h < 190

        elapsed_font = 30 if compact else 33
        elapsed_y = 60 if compact else 66
        elapsed_h = 44 if compact else 48
        painter.setFont(QFont("Menlo", elapsed_font, QFont.Bold))
        painter.drawText(20, elapsed_y, 220, elapsed_h, Qt.AlignLeft | Qt.AlignVCenter, self.elapsed)

        painter.setFont(QFont("Menlo", 15, QFont.Bold))
        total_y = elapsed_y + 20 if compact else elapsed_y + 22
        painter.drawText(w - 130, total_y, 100, 28, Qt.AlignRight, self.total)

        bar_h = 11 if compact else 12
        bar_gap = 8 if compact else 10
        elapsed_bottom = elapsed_y + elapsed_h
        left_bar_y = elapsed_bottom + (12 if compact else 16)

        # 如果屏幕很高，电平条可稍微下移；但绝不允许上碰时间区。
        preferred_left = int(h * (0.60 if compact else 0.615))
        left_bar_y = max(left_bar_y, preferred_left)
        right_bar_y = left_bar_y + bar_h + bar_gap
        info_y = right_bar_y + bar_h + (8 if compact else 10)
        bottom_y = h - 22

        # 底部空间不足时，只压缩信息区到底部，但不再把电平条上推到时间区。
        if info_y + 18 > bottom_y - 2:
            info_y = max(right_bar_y + bar_h + 6, bottom_y - 19)

        self.draw_bar(painter, 20, int(left_bar_y), w - 40, bar_h, self.left, "L")
        self.draw_bar(painter, 20, int(right_bar_y), w - 40, bar_h, self.right, "R")

        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        line = (
            f"{self.track.codec}   "
            f"{self.track.sample_rate}   "
            f"{self.track.bit_depth}   "
            f"{self.track.channels}"
        )
        painter.drawText(20, int(info_y), w - 40, 16, Qt.AlignLeft, line)

        painter.setFont(QFont("Menlo", 8, QFont.Bold))
        bottom_text = f"DSD/ISO TRY  |  VLC PLAYBACK  |  LEVEL: {self.level_mode}"
        painter.drawText(20, int(bottom_y), w - 40, 16, Qt.AlignLeft, bottom_text)

    def _paint_main_menu(self, painter, w, h, c):
        painter.setPen(c["text"])

        painter.setFont(QFont("Menlo", 15, QFont.Bold))
        painter.drawText(26, 30, w - 52, 28, Qt.AlignLeft, "MENU")

        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        painter.drawText(26, 58, w - 52, 22, Qt.AlignLeft, "PLAY ENTER   ESC BACK")

        items = [
            {
                "name": "STYLE",
                "right": "01",
            }
        ]

        self._paint_striped_list(
            painter=painter,
            w=w,
            h=h,
            c=c,
            items=items,
            selected_index=self.main_menu_selected_index,
            footer="SYSTEM MENU"
        )

    def _paint_style_select(self, painter, w, h, c):
        painter.setPen(c["text"])

        painter.setFont(QFont("Menlo", 15, QFont.Bold))
        painter.drawText(26, 30, w - 52, 28, Qt.AlignLeft, "STYLE")

        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        painter.drawText(26, 58, w - 52, 22, Qt.AlignLeft, "FR/FF MOVE   PLAY LOAD   ESC BACK")

        items = [
            {
                "name": "PCM-D1 STYLE",
                "right": "ON" if self.current_style == "D1" else "",
            },
            {
                "name": "PCM-D50 STYLE",
                "right": "ON" if self.current_style == "D50" else "",
            },
        ]

        self._paint_striped_list(
            painter=painter,
            w=w,
            h=h,
            c=c,
            items=items,
            selected_index=self.style_selected_index,
            footer="STYLE SELECT"
        )

    def _paint_folder_select(self, painter, w, h, c):
        painter.setPen(c["text"])

        title = "D50 FOLDER SELECT" if self.deck_style == "D50" else "MENU FOLDER SELECT"

        painter.setFont(QFont("Menlo", 15, QFont.Bold))
        painter.drawText(26, 30, w - 52, 28, Qt.AlignLeft, title)

        painter.setFont(QFont("Menlo", 11, QFont.Bold))
        painter.drawText(w - 115, 32, 85, 24, Qt.AlignRight, self.folder_pos)

        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        painter.drawText(26, 58, w - 52, 22, Qt.AlignLeft, "FR/FF MOVE   MENU OR PLAY LOAD")

        if not self.folder_items:
            painter.setFont(QFont("Menlo", 18, QFont.Bold))
            painter.drawText(26, 115, w - 52, 40, Qt.AlignCenter, "NO AUDIO FOLDER")
            return

        items = []
        for item in self.folder_items:
            indent = "  " * min(item.get("depth", 0), 2)
            name = item.get("name", "UNKNOWN")
            count = item.get("count", 0)
            items.append({
                "name": f"{indent}{name}",
                "right": f"{count:02d}",
            })

        self._paint_striped_list(
            painter=painter,
            w=w,
            h=h,
            c=c,
            items=items,
            selected_index=self.folder_selected_index,
            footer="STRIPED 2-LEVEL FOLDER VIEW"
        )

    def _paint_striped_list(self, painter, w, h, c, items, selected_index, footer):
        """
        通用条形列表。
        已修复：
        1. 文件夹行不会和底部 footer 重叠。
        2. 最多显示 5 行，给底部说明文字留空间。
        3. 底部说明文字统一往内收。
        """

        if not items:
            painter.setFont(QFont("Menlo", 18, QFont.Bold))
            painter.drawText(26, 115, w - 52, 40, Qt.AlignCenter, "EMPTY")
            return

        list_x = 26
        list_w = w - 52

        # 列表起点略微上移
        y = 86

        # 行高略微缩小，避免挤到底部
        row_h = 23

        # 底部说明文字区域
        footer_y = h - 30

        # 给 footer 留出空间，最多显示 5 行
        max_visible_by_height = max(1, int((footer_y - y - 10) / row_h))
        visible_count = min(5, max_visible_by_height)

        selected = selected_index

        start = max(0, selected - visible_count // 2)
        end = min(len(items), start + visible_count)

        if end - start < visible_count:
            start = max(0, end - visible_count)

        painter.setFont(QFont("Menlo", 11, QFont.Bold))

        for visual_index, item_index in enumerate(range(start, end)):
            item = items[item_index]

            row_y = y + visual_index * row_h
            row_rect = QRect(list_x, row_y, list_w, row_h - 3)

            stripe_color = c["stripe_a"] if visual_index % 2 == 0 else c["stripe_b"]
            painter.fillRect(row_rect, stripe_color)

            if item_index == selected:
                painter.fillRect(row_rect, c["select"])

            marker = ">" if item_index == selected else " "
            name = item.get("name", "UNKNOWN")
            right = item.get("right", "")

            marker_rect = QRect(list_x + 10, row_y, 22, row_h - 3)
            name_rect = QRect(list_x + 46, row_y, list_w - 150, row_h - 3)
            right_rect = QRect(list_x + list_w - 100, row_y, 80, row_h - 3)

            painter.setPen(c["text"])
            painter.drawText(marker_rect, Qt.AlignVCenter | Qt.AlignLeft, marker)
            painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name[:36])
            painter.drawText(right_rect, Qt.AlignVCenter | Qt.AlignRight, right)

        painter.setFont(QFont("Menlo", 10, QFont.Bold))
        painter.setPen(c["text"])
        painter.drawText(26, footer_y, w - 52, 18, Qt.AlignLeft, footer)