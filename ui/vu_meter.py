# ui/vu_meter.py

import math

from PySide6.QtCore import Qt, Property, QRectF, QSize, QPointF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QFont,
    QLinearGradient,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from ui.vu_motion import db_from_level, make_wide_d1_geometry


def _mix(a, b, t):
    return int(a + (b - a) * t)


def _mix_color(c1, c2, t, alpha=255):
    return QColor(
        _mix(c1[0], c2[0], t),
        _mix(c1[1], c2[1], t),
        _mix(c1[2], c2[2], t),
        alpha,
    )


def _font(size, bold=True):
    f = QFont("Arial", size)
    if bold:
        f.setBold(True)
    return f


class StereoVUMeter(QWidget):
    """
    Sony PCM 风格双声道 VU 表。

    - 普通窗口：两个独立圆形/半圆形表头，对应用户给出的第一张参考图。
    - 全屏窗口：一个横向黑色底座，内部左右两个长条表窗，对应用户给出的第二张参考图。
    """

    def __init__(self):
        super().__init__()
        self.left_level = 0.0
        self.right_level = 0.0
        self.deck_style = "D1"
        self._theme_mix = 1.0

        self.setMinimumSize(520, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(700, 260)

    def set_deck_style(self, style_name: str):
        self.deck_style = style_name
        self.update()

    def get_theme_mix(self):
        return self._theme_mix

    def set_theme_mix(self, value):
        self._theme_mix = max(0.0, min(1.0, float(value)))
        self.update()

    themeMix = Property(float, get_theme_mix, set_theme_mix)

    def set_levels(self, left: float, right: float):
        self.left_level = max(0.0, min(1.0, float(left)))
        self.right_level = max(0.0, min(1.0, float(right)))
        self.update()

    def set_level(self, level: float):
        self.set_levels(level, level)

    def _colors(self):
        # themeMix 与 LCDPanel 保持同一套 LIGHT 动画逻辑：
        # 0.0 = 偏暖橙色背光，1.0 = 偏浅绿/奶油背光。
        t = self._theme_mix
        return {
            "black_top": _mix_color((7, 7, 7), (18, 21, 18), t),
            "black_bottom": _mix_color((19, 19, 19), (5, 8, 6), t),
            "black_edge": QColor(0, 0, 0),
            # VU 表背光颜色与 LCDPanel 的 D1 屏幕开关灯颜色保持一致。
            "cream_top": _mix_color((255, 174, 55), (226, 238, 220), t),
            "cream_mid": _mix_color((246, 140, 40), (196, 216, 194), t),
            "cream_bottom": _mix_color((210, 75, 8), (164, 184, 166), t),
            "scale": QColor(7, 7, 7),
            "red": QColor(174, 23, 30),
            "white": QColor(250, 250, 250),
            "dot": QColor(132, 128, 115, 190),
            "shadow": QColor(0, 0, 0, 70),
            "glass": QColor(255, 255, 255, 22),
        }

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        c = self._colors()

        # 普通竖向窗口：圆形平底 VU；窗口被拉成横向超过 4:3 或全屏时：切换为一体式长条 VU。
        win = self.window()
        if win is not None:
            ww = max(1, win.width())
            wh = max(1, win.height())
            # 用户拖宽窗口时，布局高度可能被 LCD/按钮最小高度撑住，
            # 因此同时参考顶层窗口比例和 VU 区域自身是否被明显拉宽。
            wide_window = (ww / wh) > (4.0 / 3.0)
            wide_vu_area = (ww > 780) and ((w / max(1, h)) > 2.25)
            use_wide_meter = win.isFullScreen() or wide_window or wide_vu_area
        else:
            use_wide_meter = (w / max(1, h)) > 2.25

        if use_wide_meter:
            self._paint_fullscreen(painter, w, h, c)
        else:
            self._paint_windowed(painter, w, h, c)

    # =========================
    # 普通窗口：两个圆形 Sony 表头
    # =========================

    def _paint_windowed(self, painter, w, h, c):
        # v26：窗口化表按“圆形表头 + 底部平切”的结构重做。
        # 关键点：单个表头的绘制框必须接近正圆，不能再用横向拉伸的椭圆。
        margin_x = max(18, int(w * 0.035))
        gap = max(24, int(w * 0.055))
        slot_w = (w - margin_x * 2 - gap) / 2
        # 让圆直径由宽高共同约束；如果容器高度不足，优先保证圆形而不是填满横向。
        diameter = min(slot_w, h * 0.92)
        meter_h = diameter * 0.935
        y = max(3, (h - meter_h) * 0.42)

        left_x = margin_x + (slot_w - diameter) / 2
        right_x = margin_x + slot_w + gap + (slot_w - diameter) / 2
        left = QRectF(left_x, y, diameter, meter_h)
        right = QRectF(right_x, y, diameter, meter_h)

        self._draw_round_meter(painter, left, "LEFT", self.left_level, c)
        self._draw_round_meter(painter, right, "RIGHT", self.right_level, c)

    def _circle_chord_path(self, cx, top, r, bottom_y, steps=160):
        """上圆、底部平切的路径。bottom_y 是平底所在 y。"""
        dy = max(-r + 1, min(r - 1, bottom_y - (top + r)))
        dx = math.sqrt(max(1.0, r * r - dy * dy))
        left_x = cx - dx
        right_x = cx + dx
        theta_r = math.atan2(dy, dx)
        theta_l_upper = -math.pi - theta_r
        path = QPainterPath()
        path.moveTo(left_x, bottom_y)
        path.lineTo(right_x, bottom_y)
        # 从右底点沿上圆弧走到左底点，必须走过顶部而不是下半圆。
        for i in range(steps + 1):
            a = theta_r + (theta_l_upper - theta_r) * (i / steps)
            x = cx + math.cos(a) * r
            y = top + r + math.sin(a) * r
            path.lineTo(x, y)
        path.closeSubpath()
        return path, left_x, right_x

    def _draw_round_meter(self, painter, rect: QRectF, title: str, level: float, c):
        # rect.width() 是圆直径；rect.height() 是被平切后的可见高度。
        d = rect.width()
        r = d / 2.0
        cx = rect.left() + r
        top = rect.top()
        bottom = rect.top() + d * 0.930
        ow = d
        oh = bottom - top
        ol = rect.left()
        or_ = rect.right()
        ot = top
        ob = bottom

        # 外壳：真正的圆被底部水平切掉，底边两端自然由圆弧过渡。
        outer_path, flat_l, flat_r = self._circle_chord_path(cx, top, r, bottom)

        outer_grad = QLinearGradient(0, top, 0, bottom)
        outer_grad.setColorAt(0.00, c["black_top"])
        outer_grad.setColorAt(0.45, QColor(8, 9, 8))
        outer_grad.setColorAt(1.00, c["black_bottom"])
        painter.setBrush(QBrush(outer_grad))
        painter.setPen(QPen(c["black_edge"], max(3, int(d * 0.012))))
        painter.drawPath(outer_path)

        # 外壳内侧暗边，增强程序整体的黑色金属质感。
        inner_shell, _, _ = self._circle_chord_path(cx, top + d * 0.018, r * 0.958, bottom - d * 0.020)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(38, 40, 38, 150), max(1, int(d * 0.004))))
        painter.drawPath(inner_shell)

        # 米黄色屏幕：同样按圆形内窗构造，然后由黑色下遮罩压住，避免普通圆角矩形感。
        pad = d * 0.045
        panel_cx = cx
        panel_r = r - pad
        panel_top = top + d * 0.044
        panel_bottom = top + d * 0.642
        panel_path, _, _ = self._circle_chord_path(panel_cx, panel_top, panel_r, panel_bottom)

        # 更自然的背光渐变：线性暖底 + 中央柔和亮斑，避免开灯后上下分层突兀。
        panel_grad = QLinearGradient(0, panel_top, 0, panel_bottom)
        # 与 LCD 屏幕同色系：关灯为橙色，开灯为灰绿色；中间柔和过渡。
        panel_grad.setColorAt(0.00, c["cream_top"])
        panel_grad.setColorAt(0.46, c["cream_mid"])
        panel_grad.setColorAt(1.00, c["cream_bottom"])
        painter.save()
        painter.setClipPath(outer_path)
        painter.setBrush(QBrush(panel_grad))
        painter.setPen(QPen(QColor(2, 2, 2), max(2, int(d * 0.008))))
        painter.drawPath(panel_path)

        glow = QRadialGradient(QPointF(cx, panel_top + d * 0.255), d * 0.55)
        glow.setColorAt(0.0, QColor(255, 255, 240, int(54 + 42 * self._theme_mix)))
        glow.setColorAt(0.55, QColor(255, 246, 210, int(18 + 20 * self._theme_mix)))
        glow.setColorAt(1.0, QColor(255, 240, 210, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawPath(panel_path)
        painter.restore()

        # 黑色下遮罩：参考图的关键轮廓是“中间上拱、左右下沉、底部平切”。
        cover = QPainterPath()
        cover_left = ol + d * 0.012
        cover_right = or_ - d * 0.012
        shoulder_y = top + d * 0.658
        crown_y = top + d * 0.515
        cover.moveTo(cover_left, bottom)
        cover.lineTo(cover_left, shoulder_y)
        cover.cubicTo(cx - d * 0.360, top + d * 0.650, cx - d * 0.250, crown_y, cx, crown_y)
        cover.cubicTo(cx + d * 0.250, crown_y, cx + d * 0.360, top + d * 0.650, cover_right, shoulder_y)
        cover.lineTo(cover_right, bottom)
        cover.closeSubpath()
        painter.save()
        painter.setClipPath(outer_path)
        painter.setBrush(QBrush(outer_grad))
        painter.setPen(Qt.NoPen)
        painter.drawPath(cover)
        painter.restore()

        # 已按要求删除窗口化电表顶部的白色椭圆高光。

        # 刻度：整体上移，数字保持正向，避免裁切。
        arc_cx = cx
        arc_cy = top + d * 0.662
        rx_arc = d * 0.392
        ry_arc = d * 0.335
        angle_min = 209
        angle_max = 331
        red_start = 0.690

        def pt_on(ratio, scale=1.0):
            a = math.radians(angle_min + (angle_max - angle_min) * ratio)
            return QPointF(arc_cx + math.cos(a) * rx_arc * scale, arc_cy + math.sin(a) * ry_arc * scale)

        def arc_path(r1, r2, scale=1.0):
            p = QPainterPath()
            first = True
            steps = 130
            for i in range(int(r1 * steps), int(r2 * steps) + 1):
                q = pt_on(i / steps, scale)
                if first:
                    p.moveTo(q)
                    first = False
                else:
                    p.lineTo(q)
            return p

        painter.setPen(QPen(c["scale"], max(6, int(d * 0.021)), Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(arc_path(0.035, red_start, 1.0))
        painter.setPen(QPen(c["red"], max(6, int(d * 0.021)), Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(arc_path(red_start, 0.965, 1.0))
        end = pt_on(0.965, 1.0)
        painter.drawLine(int(end.x()), int(end.y()), int(end.x() + d * 0.090), int(end.y()))

        major = [
            ("", 0.035, 1.300),
            ("20", 0.195, 1.300),
            ("16", 0.410, 1.295),
            ("14", 0.555, 1.290),
            ("12", 0.725, 1.275),
            ("10", 0.880, 1.270),
        ]
        major_ratios = [m[1] for m in major]

        for label, ratio, _scale in major:
            p1 = pt_on(ratio, 0.805)
            p2 = pt_on(ratio, 1.115)
            painter.setPen(QPen(c["red"] if ratio >= red_start else c["scale"], max(5, int(d * 0.016))))
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

        for ratio in [0.30, 0.48, 0.64, 0.80]:
            if min(abs(ratio - r0) for r0 in major_ratios) < 0.04:
                continue
            p1 = pt_on(ratio, 0.920)
            p2 = pt_on(ratio, 1.055)
            painter.setPen(QPen(c["red"] if ratio >= red_start else c["scale"], max(2, int(d * 0.006))))
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

        painter.setFont(_font(max(15, int(d * 0.057))))
        for label, ratio, scale in major:
            if not label:
                continue
            pos = pt_on(ratio, scale)
            painter.setPen(c["red"] if ratio >= red_start else c["scale"])
            painter.drawText(QRectF(pos.x() - d * 0.090, pos.y() - d * 0.050, d * 0.180, d * 0.100), Qt.AlignCenter, label)

        # 指针：转轴固定在屏幕正下方、被黑色遮罩隐藏的位置。
        # 只把指针可见部分裁剪在米黄色屏幕内，避免看起来像一根斜线直接放在表外。
        ratio = 0.145 + max(0.0, min(1.0, level)) * 0.620
        a = math.radians(angle_min + (angle_max - angle_min) * ratio)
        pivot = QPointF(cx, top + d * 0.905)
        tip = QPointF(arc_cx + math.cos(a) * rx_arc * 1.155, arc_cy + math.sin(a) * ry_arc * 1.155)
        painter.save()
        painter.setClipPath(panel_path)
        painter.setPen(QPen(c["shadow"], max(5, int(d * 0.012)), Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(pivot.x() + 2), int(pivot.y() + 2), int(tip.x() + 2), int(tip.y() + 2))
        painter.setPen(QPen(QColor(8, 8, 8), max(3, int(d * 0.008)), Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(pivot.x()), int(pivot.y()), int(tip.x()), int(tip.y()))
        painter.restore()

        # 右下小圆点；按要求保持无 SONY 标识。
        dot_r = max(5, int(d * 0.022))
        painter.setBrush(c["dot"])
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx + d * 0.385, top + d * 0.604), dot_r, dot_r)

        painter.setFont(_font(max(18, int(d * 0.066))))
        painter.setPen(c["white"])
        painter.drawText(QRectF(ol, top + d * 0.705, ow, d * 0.150), Qt.AlignCenter, title)

    # =========================
    # 全屏：一体式双窗口长条 VU 表
    # =========================

    def _paint_fullscreen(self, painter, w, h, c):
        # v34：全屏/横向模式的外观回到 v27 的一体式长条 VU 表，
        # 但把整体高度抬到接近窗口模式 VU 区域的视觉高度，
        # 避免在横向窗口中显得过薄、过空。
        outer_h = min(h * 0.74, w * 0.220)
        # 宽屏 / 全屏模式下，让 VU 外框实际宽度与下方 LCD 屏幕对齐。
        # LCDPanel 自身在控件内是 4px 边距绘制，因此这里也使用 4px 内缩。
        outer = QRectF(4, (h - outer_h) / 2, w - 8, outer_h)
        outer_grad = QLinearGradient(0, outer.top(), 0, outer.bottom())
        outer_grad.setColorAt(0.0, QColor(20, 20, 20))
        outer_grad.setColorAt(0.55, QColor(7, 7, 7))
        outer_grad.setColorAt(1.0, QColor(18, 18, 18))
        painter.setBrush(QBrush(outer_grad))
        painter.setPen(QPen(QColor(0, 0, 0), max(4, int(outer.height() * 0.014))))
        painter.drawRoundedRect(outer, outer.height() * 0.085, outer.height() * 0.085)

        inset = outer.adjusted(12, 12, -12, -12)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(42, 42, 42), max(1, int(outer.height() * 0.005))))
        painter.drawRoundedRect(inset, outer.height() * 0.065, outer.height() * 0.065)

        # v7：原参考图中两个屏幕之间的黑色分隔更宽，v6 的两块浅色屏幕
        # 横向过长、中心缝偏窄。边距和中缝分开控制。
        # v36：让浅色屏幕更贴近黑色 VU 外框，减少四周空黑边。
        side_gap = outer.width() * 0.024
        center_gap = outer.width() * 0.015
        panel_top = outer.top() + outer.height() * 0.090
        panel_h = outer.height() * 0.630
        panel_w = (outer.width() - side_gap * 2 - center_gap) / 2
        left_panel = QRectF(outer.left() + side_gap, panel_top, panel_w, panel_h)
        right_panel = QRectF(left_panel.right() + center_gap, panel_top, panel_w, panel_h)

        # 中间分隔
        painter.setPen(QPen(QColor(16, 16, 16), 3))
        painter.drawLine(int(outer.center().x()), int(outer.top() + outer.height() * 0.04), int(outer.center().x()), int(outer.bottom() - outer.height() * 0.04))

        self._draw_wide_panel(painter, left_panel, "LEFT", self.left_level, c)
        self._draw_wide_panel(painter, right_panel, "RIGHT", self.right_level, c)

    def _draw_wide_panel(self, painter, panel: QRectF, title: str, level: float, c):
        panel_grad = QLinearGradient(0, panel.top(), 0, panel.bottom())
        panel_grad.setColorAt(0.0, c["cream_top"])
        panel_grad.setColorAt(0.46, c["cream_mid"])
        panel_grad.setColorAt(1.0, c["cream_bottom"])
        painter.setBrush(QBrush(panel_grad))
        painter.setPen(QPen(QColor(3, 3, 3), max(2, int(panel.height() * 0.025))))
        # 全屏参考图的内屏是横向长矩形，只保留很小的圆角，不能画成胶囊形。
        screen_radius = max(16, min(48, int(panel.height() * 0.145)))
        painter.drawRoundedRect(panel, screen_radius, screen_radius)

        # 按要求删除全屏 VU 屏幕上的白色不规则/高光图形，
        # 只保留与 LCD 一致的背光渐变。

        painter.save()
        painter.setClipRect(panel.adjusted(4, 4, -4, -4))
        geom = make_wide_d1_geometry(panel)
        red_start = 0.70

        painter.setPen(QPen(c["scale"], max(4, int(panel.height() * 0.020)), Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(geom.arc_path(0.02, red_start, scale=1.0))
        painter.setPen(QPen(c["red"], max(4, int(panel.height() * 0.020)), Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(geom.arc_path(red_start, 0.98, scale=1.0))
        end = geom.point_by_ratio(0.98, 1.0)
        painter.drawLine(int(end.x()), int(end.y()), int(end.x() + panel.width() * 0.07), int(end.y()))

        # 全屏数字保持水平正向；整体放在表窗纵向中部偏上，
        # 与主刻度线拉开距离，不再贴顶也不挤在刻度线上。
        major = [
            ("", 0.04, 1.285),
            ("20", 0.22, 1.285),
            ("16", 0.43, 1.275),
            ("14", 0.58, 1.270),
            ("12", 0.74, 1.260),
            ("10", 0.90, 1.250),
        ]

        # 主刻度不再贯穿弧线：只从弧线外侧向上伸出，
        # 线宽比普通刻度粗，但不再像 v34 那样过重。
        for label, ratio, _ in major:
            # v36：主刻度短一点，不顶到上方数字；仍比普通刻度稍粗。
            p1, p2 = geom.tick_points(ratio, 1.012, 1.105)
            painter.setPen(QPen(c["red"] if ratio >= red_start else c["scale"], max(3, int(panel.height() * 0.017)), Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

        for i in range(21):
            ratio = i / 20
            if any(abs(ratio - m[1]) < 0.025 for m in major):
                continue
            # 普通刻度只在弧线外侧轻轻伸出，模仿参考图，不贯穿弧线。
            p1, p2 = geom.tick_points(ratio, 1.006, 1.055)
            painter.setPen(QPen(c["red"] if ratio >= red_start else c["scale"], max(1, int(panel.height() * 0.006)), Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(int(p1.x()), int(p1.y()), int(p2.x()), int(p2.y()))

        painter.setFont(_font(max(12, int(panel.height() * 0.118))))
        for label, ratio, scale in major:
            if not label:
                continue
            p = geom.point_by_ratio(ratio, scale)
            painter.setPen(c["red"] if ratio >= red_start else c["scale"])
            painter.drawText(QRectF(p.x() - 36, p.y() - 16, 72, 32), Qt.AlignCenter, label)

        inner, mid, outer = geom.radial_needle_points(level, inner_scale=0.38, mid_scale=0.76, outer_scale=1.12)
        painter.setPen(QPen(c["shadow"], 5))
        painter.drawLine(int(inner.x() + 2), int(inner.y() + 2), int(outer.x() + 2), int(outer.y() + 2))
        painter.setPen(QPen(QColor(10, 10, 10), 3))
        painter.drawLine(int(inner.x()), int(inner.y()), int(outer.x()), int(outer.y()))
        painter.setPen(QPen(QColor(10, 10, 10), 5))
        painter.drawLine(int(mid.x()), int(mid.y()), int(outer.x()), int(outer.y()))
        painter.restore()

        # 右下圆点（按要求去掉 SONY 标识）
        painter.setBrush(c["dot"])
        painter.setPen(Qt.NoPen)
        r = max(5, int(panel.height() * 0.055))
        painter.drawEllipse(QPointF(panel.right() - panel.width() * 0.07, panel.bottom() - panel.height() * 0.20), r, r)

        # LEFT / RIGHT 标识上移，避免全屏/宽屏模式中太靠下
        label_rect = QRectF(panel.left(), panel.bottom() + panel.height() * 0.045, panel.width(), panel.height() * 0.26)
        painter.setFont(_font(max(16, int(panel.height() * 0.145))))
        painter.setPen(c["white"])
        painter.drawText(label_rect, Qt.AlignCenter, title)


# 保留单声道类名，避免其他旧代码导入时报错。
class VUMeter(StereoVUMeter):
    def __init__(self, title="LEFT"):
        super().__init__()
        self.title = title

    def sizeHint(self):
        return QSize(330, 255)

    def set_level(self, level: float):
        if self.title.upper() == "RIGHT":
            self.set_levels(0.0, level)
        else:
            self.set_levels(level, 0.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = self._colors()
        if self.window() is not None and self.window().isFullScreen():
            self._paint_fullscreen(painter, self.width(), self.height(), c)
        else:
            rect = QRectF(0, 0, self.width(), self.height())
            level = self.right_level if self.title.upper() == "RIGHT" else self.left_level
            self._draw_round_meter(painter, rect, self.title, level, c)
