"""用 pygame 现画的矢量图标，不依赖任何图片素材。

对齐参考图里的那套 HUD 图标：齿轮、日/月、手柄、省略号、靶心、
时钟、红心、金币、井号（辅助线）、放大/缩小镜、撤销箭头、星星。
"""

import math

import pygame


def _alpha_circle(surface, color, center, radius, alpha):
    """带透明度的圆点（残影、光晕用）。"""
    size = radius * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*color[:3], alpha), (size // 2, size // 2),
                       radius)
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


# --------------------------------------------------------------------------
# 顶栏图标
# --------------------------------------------------------------------------

def gear(surface, center, size, color, thickness=2):
    """齿轮：中间一个圆 + 一圈方齿。"""
    cx, cy = center
    outer = size / 2
    inner = outer * 0.62
    teeth = 8
    for i in range(teeth):
        angle = math.pi * 2 * i / teeth
        tooth = pygame.Rect(0, 0, max(3, int(size * 0.18)),
                            max(3, int(size * 0.24)))
        px = cx + math.cos(angle) * outer * 0.86
        py = cy + math.sin(angle) * outer * 0.86
        tooth.center = (int(px), int(py))
        pygame.draw.rect(surface, color, tooth, border_radius=1)
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(outer * 0.82),
                       thickness)
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(inner * 0.5))


def moon(surface, center, size, color, bg=(255, 255, 255)):
    """弯月：画一个实心圆，再用底色挖掉一块。"""
    cx, cy = center
    radius = size / 2
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius))
    pygame.draw.circle(surface, bg,
                       (int(cx + radius * 0.5), int(cy - radius * 0.32)),
                       int(radius * 0.92))


def sun(surface, center, size, color):
    """太阳：圆盘 + 八条光芒。"""
    cx, cy = center
    radius = size * 0.28
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius))
    for i in range(8):
        angle = math.pi * 2 * i / 8
        x1 = cx + math.cos(angle) * radius * 1.45
        y1 = cy + math.sin(angle) * radius * 1.45
        x2 = cx + math.cos(angle) * radius * 2.0
        y2 = cy + math.sin(angle) * radius * 2.0
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), 2)


def controller(surface, center, size, color):
    """手柄：圆角机身 + 左侧十字键 + 右侧两颗按键。"""
    cx, cy = center
    body = pygame.Rect(0, 0, size, size * 0.60)
    body.center = (int(cx), int(cy))
    pygame.draw.rect(surface, color, body, 2, border_radius=int(size * 0.22))

    # 左侧十字键
    arm = size * 0.16
    bar = max(2, int(size * 0.06))
    px = cx - size * 0.26
    pygame.draw.rect(surface, color, pygame.Rect(
        int(px - arm / 2), int(cy - bar / 2), int(arm), bar))
    pygame.draw.rect(surface, color, pygame.Rect(
        int(px - bar / 2), int(cy - arm / 2), bar, int(arm)))

    # 右侧两颗按键
    radius = max(2, int(size * 0.075))
    pygame.draw.circle(surface, color,
                       (int(cx + size * 0.20), int(cy - size * 0.08)),
                       radius, 2)
    pygame.draw.circle(surface, color,
                       (int(cx + size * 0.33), int(cy + size * 0.09)),
                       radius, 2)


def dots(surface, center, size, color):
    """省略号。"""
    cx, cy = center
    gap = size * 0.3
    for i in (-1, 0, 1):
        pygame.draw.circle(surface, color,
                           (int(cx + i * gap), int(cy)), max(2, int(size * 0.1)))


def target(surface, center, size, color):
    """靶心：一大一小两个同心圆 + 圆心点。"""
    cx, cy = center
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(size / 2), 2)
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(size * 0.22))


def clock(surface, center, size, color):
    """时钟：外圈 + 时针分针。"""
    cx, cy = center
    radius = size / 2
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius), 2)
    pygame.draw.line(surface, color, (cx, cy), (cx, cy - radius * 0.55), 2)
    pygame.draw.line(surface, color, (cx, cy), (cx + radius * 0.45, cy), 2)


def heart(surface, center, size, color):
    """红心：两个圆 + 一个三角。"""
    x, y = center
    radius = size / 4
    pygame.draw.circle(surface, color, (int(x - radius), int(y - radius / 2)),
                       int(radius))
    pygame.draw.circle(surface, color, (int(x + radius), int(y - radius / 2)),
                       int(radius))
    pygame.draw.polygon(surface, color, [
        (int(x - 2 * radius), int(y - radius / 2.5)),
        (int(x + 2 * radius), int(y - radius / 2.5)),
        (int(x), int(y + 2 * radius)),
    ])


def coin(surface, center, radius, color, face=(255, 248, 226)):
    """金币：金色圆 + 内圈 + 一颗星。"""
    cx, cy = center
    pygame.draw.circle(surface, tuple(max(0, c - 45) for c in color),
                       (int(cx), int(cy)), int(radius))
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius * 0.86))
    star(surface, (cx, cy), radius * 1.05, face)


def star(surface, center, size, color):
    """五角星。"""
    cx, cy = center
    outer = size / 2
    inner = outer * 0.46
    points = []
    for i in range(10):
        angle = -math.pi / 2 + math.pi * i / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius,
                       cy + math.sin(angle) * radius))
    pygame.draw.polygon(surface, color, points)


def hash_sign(surface, center, size, color, thickness=3):
    """井号：辅助线开关的图标。"""
    cx, cy = center
    half = size / 2
    offset = size * 0.22
    for delta in (-offset, offset):
        pygame.draw.line(surface, color, (cx - half, cy + delta),
                         (cx + half, cy + delta), thickness)
        pygame.draw.line(surface, color, (cx + delta, cy - half),
                         (cx + delta, cy + half), thickness)


def magnifier(surface, center, size, color, plus=None, thickness=2):
    """放大镜；plus=True 画加号，False 画减号，None 不画。"""
    cx, cy = center
    radius = size * 0.34
    pygame.draw.circle(surface, color, (int(cx - size * 0.08),
                                        int(cy - size * 0.08)),
                       int(radius), thickness)
    pygame.draw.line(surface, color,
                     (cx + radius * 0.62, cy + radius * 0.62),
                     (cx + size * 0.46, cy + size * 0.46), thickness + 1)
    if plus is None:
        return
    arm = radius * 0.55
    hx, hy = cx - size * 0.08, cy - size * 0.08
    pygame.draw.line(surface, color, (hx - arm, hy), (hx + arm, hy),
                     thickness)
    if plus:
        pygame.draw.line(surface, color, (hx, hy - arm), (hx, hy + arm),
                         thickness)


def plus_badge(surface, center, radius, color, bg):
    """右上角的「+」小角标。"""
    cx, cy = center
    pygame.draw.circle(surface, bg, (int(cx), int(cy)), int(radius + 2))
    pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius))
    arm = radius * 0.5
    pygame.draw.line(surface, bg, (cx - arm, cy), (cx + arm, cy), 2)
    pygame.draw.line(surface, bg, (cx, cy - arm), (cx, cy + arm), 2)


def undo(surface, center, size, color, thickness=2):
    """撤销：一段圆弧加一个箭头。"""
    cx, cy = center
    radius = size * 0.34
    rect = pygame.Rect(0, 0, int(radius * 2), int(radius * 2))
    rect.center = (int(cx), int(cy) + int(size * 0.06))
    pygame.draw.arc(surface, color, rect, math.pi * 0.15, math.pi * 1.05,
                    thickness)
    tip = (cx - radius * 0.86, cy - radius * 0.05)
    pygame.draw.polygon(surface, color, [
        (tip[0] - size * 0.08, tip[1] - size * 0.02),
        (tip[0] + size * 0.10, tip[1] - size * 0.12),
        (tip[0] + size * 0.10, tip[1] + size * 0.14),
    ])


def arrow_left(surface, center, size, color, thickness=3):
    """左箭头：返回上一级用。"""
    cx, cy = center
    half = size * 0.34
    pygame.draw.line(surface, color, (cx - half, cy), (cx + half, cy),
                     thickness)
    pygame.draw.polygon(surface, color, [
        (cx - half - size * 0.06, cy),
        (cx - half + size * 0.20, cy - size * 0.22),
        (cx - half + size * 0.20, cy + size * 0.22),
    ])


def bulb(surface, center, size, color, thickness=2):
    """灯泡：提示按钮的备选图标。"""
    cx, cy = center
    radius = size * 0.3
    pygame.draw.circle(surface, color, (int(cx), int(cy - size * 0.06)),
                       int(radius), thickness)
    pygame.draw.line(surface, color, (cx - radius * 0.5, cy + radius * 1.0),
                     (cx + radius * 0.5, cy + radius * 1.0), thickness)
    pygame.draw.line(surface, color, (cx - radius * 0.36, cy + radius * 1.35),
                     (cx + radius * 0.36, cy + radius * 1.35), thickness)


# --------------------------------------------------------------------------
# 开始页四个入口的图标
# --------------------------------------------------------------------------

def book(surface, center, size, color, thickness=2):
    """打开的书：书脊 + 两页外框，各带一道横线（规则介绍）。"""
    cx, cy = center
    half = size * 0.34
    top = cy - size * 0.26
    bottom = cy + size * 0.26
    pygame.draw.line(surface, color, (cx, top), (cx, bottom), thickness)
    for sign in (-1, 1):
        x = cx + sign * half
        pygame.draw.line(surface, color, (cx, top),
                         (x, top + size * 0.13), thickness)
        pygame.draw.line(surface, color, (x, top + size * 0.13), (x, bottom),
                         thickness)
        pygame.draw.line(surface, color, (x, bottom),
                         (cx, bottom - size * 0.07), thickness)
        line = max(1, thickness - 1)
        y = cy + size * 0.02
        pygame.draw.line(surface, color, (cx + sign * size * 0.10, y),
                         (cx + sign * half * 0.72, y), line)


def play(surface, center, size, color, thickness=2):
    """圆里一个三角（基础玩法）。"""
    cx, cy = center
    radius = size * 0.36
    if thickness > 1:
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius),
                           thickness)
    pygame.draw.polygon(surface, color, [
        (cx - radius * 0.26, cy - radius * 0.44),
        (cx + radius * 0.48, cy),
        (cx - radius * 0.26, cy + radius * 0.44),
    ])


def letter_a(surface, center, size, color, thickness=2):
    """两条斜线加一横，就是一个字母 A（字母玩法）。"""
    cx, cy = center
    half = size * 0.32
    top = cy - size * 0.30
    bottom = cy + size * 0.30
    pygame.draw.line(surface, color, (cx - half, bottom), (cx, top), thickness)
    pygame.draw.line(surface, color, (cx + half, bottom), (cx, top), thickness)
    cross = cy + size * 0.07
    pygame.draw.line(surface, color, (cx - half * 0.60, cross),
                     (cx + half * 0.60, cross), thickness)


def dice(surface, center, size, color, thickness=2):
    """圆角方块加三个点（随机关卡）。"""
    cx, cy = center
    half = size * 0.32
    rect = pygame.Rect(0, 0, int(half * 2), int(half * 2))
    rect.center = (int(cx), int(cy))
    pygame.draw.rect(surface, color, rect, thickness,
                     border_radius=int(size * 0.10))
    dot = max(1, int(size * 0.055))
    for (dx, dy) in ((-1, -1), (0, 0), (1, 1)):
        pygame.draw.circle(surface, color,
                           (int(cx + dx * half * 0.44),
                            int(cy + dy * half * 0.44)), dot)
