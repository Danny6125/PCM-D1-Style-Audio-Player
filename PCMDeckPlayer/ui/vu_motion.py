# ui/vu_motion.py

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def db_from_level(level: float) -> float:
    return 20 * math.log10(max(level, 0.0001))


@dataclass
class EllipseArcGeometry:
    cx: float
    cy: float
    rx: float
    ry: float
    angle_min: float
    angle_max: float

    @property
    def sweep(self) -> float:
        return self.angle_max - self.angle_min

    def angle_from_ratio(self, ratio: float) -> float:
        ratio = clamp(ratio)
        return self.angle_min + self.sweep * ratio

    def point(self, angle_deg: float, scale: float = 1.0) -> QPointF:
        angle = math.radians(angle_deg)

        x = self.cx + math.cos(angle) * self.rx * scale
        y = self.cy + math.sin(angle) * self.ry * scale

        return QPointF(x, y)

    def point_by_ratio(self, ratio: float, scale: float = 1.0) -> QPointF:
        return self.point(self.angle_from_ratio(ratio), scale)

    def arc_path(self, start_ratio: float, end_ratio: float, scale: float = 1.0, step: int = 2):
        start_angle = self.angle_from_ratio(start_ratio)
        end_angle = self.angle_from_ratio(end_ratio)

        path = QPainterPath()
        first = True

        for deg in range(int(start_angle), int(end_angle) + 1, step):
            p = self.point(deg, scale)

            if first:
                path.moveTo(p)
                first = False
            else:
                path.lineTo(p)

        return path

    def tick_points(self, ratio: float, inner_scale: float, outer_scale: float):
        angle = self.angle_from_ratio(ratio)

        return (
            self.point(angle, inner_scale),
            self.point(angle, outer_scale),
        )

    def needle_ratio_from_level(self, level: float) -> float:
        level = clamp(level)
        return 0.08 + level * 0.82

    def radial_needle_points(
        self,
        level: float,
        inner_scale: float = 0.58,
        mid_scale: float = 0.84,
        outer_scale: float = 1.06,
    ):
        """
        指针沿刻度盘同一扇面移动。
        不是从一个远处固定轴心扫出。
        """

        ratio = self.needle_ratio_from_level(level)
        angle = self.angle_from_ratio(ratio)

        inner = self.point(angle, inner_scale)
        mid = self.point(angle, mid_scale)
        outer = self.point(angle, outer_scale)

        return inner, mid, outer


def make_compact_d1_geometry(width: int, height: int) -> EllipseArcGeometry:
    """
    普通窗口 D1 VU 表几何。

    回归之前的矩形表盘风格：
    - 黑色圆角外框
    - 内部扇形刻度
    - 比原来纵向稍长
    """

    cx = width * 0.50
    cy = height * 0.80

    rx = min(width * 0.40, 360)
    ry = min(height * 0.55, 115)

    return EllipseArcGeometry(
        cx=cx,
        cy=cy,
        rx=rx,
        ry=ry,
        angle_min=205,
        angle_max=335,
    )


def make_wide_d1_geometry(meter_rect: QRectF) -> EllipseArcGeometry:
    """
    全屏宽屏 D1 VU 表几何。

    回归之前的横向长条表窗：
    - 浅色长条表盘
    - 刻度在表窗内部
    - 指针与刻度共用同一套弧线
    """

    cx = meter_rect.left() + meter_rect.width() * 0.50

    # 中心点在表窗下方，用来形成横向浅弧
    # v36：刻度弧线再稍微下放，与上方数字拉开距离。
    cy = meter_rect.top() + meter_rect.height() * 1.125

    rx = meter_rect.width() * 0.455
    ry = meter_rect.height() * 0.760

    return EllipseArcGeometry(
        cx=cx,
        cy=cy,
        rx=rx,
        ry=ry,
        angle_min=216,
        angle_max=324,
    )