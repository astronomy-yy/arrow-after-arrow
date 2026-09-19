"""方向枚举、方向映射与箭头造型绘制。"""

import functools
from enum import Enum

import pygame

# 空格标记
EMPTY = "."


class Direction(Enum):
    """四个飞行方向，枚举值与关卡网格中的字符保持一致。"""

    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"


CHAR_TO_DIRECTION = {
    "U": Direction.UP,
    "D": Direction.DOWN,
    "L": Direction.LEFT,
    "R": Direction.RIGHT,
}

DIRECTION_DELTA = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


def _build_arrow_set(size, color):
    """画一支朝右的箭（箭杆 + 箭头 + V 形尾羽），再旋转出四个方向。"""
    canvas = max(int(size * 1.7), 8)
    surf = pygame.Surface((canvas, canvas), pygame.SRCALPHA)
    cx = cy = canvas / 2
    L = size

    # 箭杆
    shaft = pygame.Rect(0, 0, int(L * 0.62), max(int(L * 0.15), 2))
    shaft.center = (cx - L * 0.05, cy)
    pygame.draw.rect(surf, color, shaft, border_radius=shaft.height // 2)

    # 箭头（三角形，尖端朝右）
    head = [
        (cx + L * 0.52, cy),
        (cx + L * 0.10, cy - L * 0.30),
        (cx + L * 0.10, cy + L * 0.30),
    ]
    pygame.draw.polygon(surf, color, head)

    # 尾羽（开口朝左的 V 形五边形）
    feather = [
        (cx - L * 0.34, cy - L * 0.08),
        (cx - L * 0.60, cy - L * 0.30),
        (cx - L * 0.40, cy),
        (cx - L * 0.60, cy + L * 0.30),
        (cx - L * 0.34, cy + L * 0.08),
    ]
    pygame.draw.polygon(surf, color, feather)

    return {
        Direction.RIGHT: surf,
        Direction.UP: pygame.transform.rotate(surf, 90),
        Direction.LEFT: pygame.transform.rotate(surf, 180),
        Direction.DOWN: pygame.transform.rotate(surf, 270),
    }


@functools.lru_cache(maxsize=None)
def _arrow_set(size, color):
    """按 (尺寸, 颜色) 缓存旋转好的四方向箭头图像。"""
    return _build_arrow_set(size, color)


def draw_arrow(surface, direction, center, size, color):
    """在 center 处绘制指定方向的箭。"""
    img = _arrow_set(int(size), color)[direction]
    surface.blit(img, img.get_rect(center=center))
