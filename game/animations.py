"""飞出与碰撞动画（阶段 7：加速发射、淡出、格子红闪、晃动）。"""

import math

import pygame

from game.arrow import Direction, _arrow_set, draw_arrow
from game.settings import CELL_SIZE, COLOR_ARROW, COLOR_DANGER

FLY_START_SPEED = 300.0   # 飞出初速度，像素/秒
FLY_SPEED = 760.0         # 飞出最大速度
FLY_ACCEL = 3000.0        # 发射加速度
FADE_TIME = 0.18          # 离开棋盘后的淡出时长，秒
BLOCK_DURATION = 0.55     # 碰撞反馈持续时间，秒
TOAST_DURATION = 0.9      # “被挡住了！”提示时长，秒
SHAKE_AMPLITUDE = 8       # 晃动幅度，像素

_UNIT_MOVE = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}


class FlyingArrow:
    """沿自身方向加速飞出、离盘后淡出的箭。"""

    def __init__(self, center, direction, size, color=COLOR_ARROW):
        self.x, self.y = center
        self.direction = direction
        self.size = size
        self.age = 0.0
        self.speed = FLY_START_SPEED
        self.alpha = 255
        self.fading = False
        self.dead = False
        # 持有自己的图像副本，淡出时只修改自己，不影响缓存
        self.image = _arrow_set(size, color)[direction].copy()

    def update(self, dt, board_rect):
        self.age += dt
        self.speed = min(FLY_SPEED, FLY_START_SPEED + FLY_ACCEL * self.age)

        ux, uy = _UNIT_MOVE[self.direction]
        self.x += ux * self.speed * dt
        self.y += uy * self.speed * dt

        # 中心离开棋盘区域后开始淡出
        if not board_rect.collidepoint(self.x, self.y):
            self.fading = True
        if self.fading:
            self.alpha = max(0, self.alpha - int(255 * dt / FADE_TIME))
        if self.alpha <= 0:
            self.dead = True

    def draw(self, surface):
        self.image.set_alpha(self.alpha)
        rect = self.image.get_rect(center=(round(self.x), round(self.y)))
        surface.blit(self.image, rect)


class BlockedFeedback:
    """被挡反馈：格子红底闪烁 + 红箭垂直晃动。"""

    def __init__(self, r, c, rect, direction, size):
        self.r = r
        self.c = c
        self.rect = rect
        self.direction = direction
        self.size = size
        self.timer = BLOCK_DURATION
        self.dead = False
        self._flash = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.dead = True

    def draw(self, surface):
        elapsed = 1 - self.timer / BLOCK_DURATION   # 0 -> 1
        damping = 1 - elapsed                        # 晃动与红底逐渐衰减
        wave = math.sin(elapsed * 6 * math.pi)      # 共 3 个来回
        offset = int(SHAKE_AMPLITUDE * damping * wave)

        if self.direction in (Direction.UP, Direction.DOWN):
            moved = self.rect.move(offset, 0)
        else:
            moved = self.rect.move(0, offset)

        # 格子红底
        self._flash.fill((0, 0, 0, 0))
        pygame.draw.rect(
            self._flash, (*COLOR_DANGER, int(110 * damping)),
            self._flash.get_rect(), border_radius=8
        )
        surface.blit(self._flash, self.rect.topleft)

        # 红色晃动的箭
        draw_arrow(surface, self.direction, moved.center,
                   self.size, COLOR_DANGER)
