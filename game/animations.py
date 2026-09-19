"""线段箭“沿自身轨迹滑出”与碰撞弹回动画。"""

import math

import pygame

from game.arrow import draw_arrow_head
from game.settings import (
    CELL_SIZE,
    COLOR_DANGER,
    COLOR_TRAIL,
    SEGMENT_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

FLY_SPEED = 16.0        # 沿线流动速度，单位：节（格）/秒
BLOCK_DURATION = 0.55   # 碰撞弹回时长
TOAST_DURATION = 0.9    # “被挡住了！”提示时长
TRAIL_LIFE = 0.55       # 残影格点停留时间
PUSH_STEPS = 0.6        # 被挡时沿轨迹前冲的节数
HEAD_SIZE = int(SEGMENT_WIDTH * 1.9)


def point_at(route, s):
    """route 是相邻等距（一格）的像素点列表，返回弧长参数 s（单位：格）处位置。"""
    if s <= 0:
        return route[0]
    last = len(route) - 1
    if s >= last:
        return route[-1]
    i = int(s)
    f = s - i
    x1, y1 = route[i]
    x2, y2 = route[i + 1]
    return (x1 + (x2 - x1) * f, y1 + (y2 - y1) * f)


def draw_flowing(surface, route, n_cells, offset, direction, color,
                 width=SEGMENT_WIDTH):
    """把 n_cells 个节沿 route 向前推进 offset 格后画出（圆角折线 + 箭头）。"""
    points = [point_at(route, i + offset) for i in range(n_cells)]
    if len(points) >= 2:
        pygame.draw.lines(surface, color, False, points, width)
    for p in points:
        pygame.draw.circle(surface, color, (int(p[0]), int(p[1])), width // 2)
    draw_arrow_head(surface, direction, points[-1], HEAD_SIZE, color)


class FlyingSegment:
    """蛇形式滑出：各节沿“自身折线 + 箭头延长线”流动，全部离屏后销毁。"""

    def __init__(self, route, trail_points, n_cells, direction, color):
        self.route = route              # 完整像素路径（尾 -> 头 -> 屏幕外）
        self.trail_points = trail_points  # 棋盘内路径点，用于灰色残影
        self.n = n_cells
        self.direction = direction
        self.color = color
        self.t = 0.0                    # 已推进的格数
        self.dead = False

    def update(self, dt, board_rect=None):
        self.t += dt * FLY_SPEED
        # 尾节最后离开；尾节完全飞出屏幕即结束
        tail_x, tail_y = point_at(self.route, self.t)
        m = SEGMENT_WIDTH * 2
        if (tail_x < -m or tail_x > WINDOW_WIDTH + m or
                tail_y < -m or tail_y > WINDOW_HEIGHT + m):
            self.dead = True

    def draw(self, surface):
        # 灰色残影：尾节离开某个格点后，该点短暂亮起再淡出
        radius = max(2, int(CELL_SIZE * 0.07))
        size = radius * 2 + 4
        for j, pos in enumerate(self.trail_points):
            age = self.t - j
            if 0.0 < age < TRAIL_LIFE:
                alpha = int(150 * (1 - age / TRAIL_LIFE))
                dot = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(dot, (*COLOR_TRAIL, alpha),
                                   (size // 2, size // 2), radius)
                surface.blit(dot, (pos[0] - size // 2, pos[1] - size // 2))

        draw_flowing(surface, self.route, self.n, self.t,
                     self.direction, self.color)


class BlockedFeedback:
    """被挡反馈：整条变红，沿自身轨迹前冲一下，再弹回原位。"""

    def __init__(self, route, n_cells, arrow):
        self.arrow_id = arrow.id
        self.route = route
        self.n = n_cells
        self.direction = arrow.direction
        self.timer = BLOCK_DURATION
        self.dead = False

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.dead = True

    def draw(self, surface):
        progress = 1 - max(self.timer, 0) / BLOCK_DURATION
        offset = PUSH_STEPS * math.sin(math.pi * progress)  # 0 -> 前冲 -> 0
        draw_flowing(surface, self.route, self.n, offset,
                     self.direction, COLOR_DANGER)
