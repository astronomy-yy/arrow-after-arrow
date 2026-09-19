"""飞出动画与碰撞反馈（阶段 6 基础版，阶段 7 再做美化）。"""

import math

import pygame

from game.arrow import Direction, draw_arrow
from game.settings import (
    CELL_SIZE,
    COLOR_ARROW,
    COLOR_DANGER,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

FLY_SPEED = 640          # 飞出速度，像素/秒
BLOCK_DURATION = 0.55    # 碰撞反馈持续时间，秒
TOAST_DURATION = 0.9     # “被挡住了！”提示持续时间，秒
SHAKE_AMPLITUDE = 8      # 晃动幅度，像素

# 方向 -> 单位位移
_UNIT_MOVE = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class FlyingArrow:
    """沿自身方向直线飞出棋盘的箭头。"""

    def __init__(self, center, direction, size):
        self.x, self.y = center
        self.direction = direction
        self.size = size
        self.dead = False

    def update(self, dt):
        ux, uy = _UNIT_MOVE[self.direction]
        self.x += ux * FLY_SPEED * dt
        self.y += uy * FLY_SPEED * dt
        # 完全飞出窗口后标记结束
        if (self.x < -CELL_SIZE or self.x > WINDOW_WIDTH + CELL_SIZE or
                self.y < -CELL_SIZE or self.y > WINDOW_HEIGHT + CELL_SIZE):
            self.dead = True

    def draw(self, surface):
        draw_arrow(surface, self.direction, (round(self.x), round(self.y)),
                   self.size, COLOR_ARROW)


class BlockedFeedback:
    """被挡箭头的反馈：变红 + 垂直于飞行方向晃动，随后恢复。"""

    def __init__(self, r, c, rect, direction):
        self.r = r
        self.c = c
        self.rect = rect
        self.direction = direction
        self.timer = BLOCK_DURATION
        self.dead = False

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.dead = True

    def draw(self, surface):
        elapsed = 1 - self.timer / BLOCK_DURATION   # 0 -> 1
        damping = 1 - elapsed                        # 晃动幅度逐渐衰减
        wave = math.sin(elapsed * 6 * math.pi)      # 共晃动 3 个来回
        offset = int(SHAKE_AMPLITUDE * damping * wave)

        # 上下方向的箭头左右晃，左右方向的箭头上下晃
        if self.direction in (Direction.UP, Direction.DOWN):
            moved = self.rect.move(offset, 0)
        else:
            moved = self.rect.move(0, offset)

        draw_arrow(surface, self.direction, moved.center,
                   int(CELL_SIZE * 0.6), COLOR_DANGER)
