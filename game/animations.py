"""线段箭的位移动画：沿自身轨迹滑出、出界后淡出、被挡时的前冲弹回。

对齐参考录屏的表现：
- 飞出：各节先沿线段自己的折线流动，再顺着箭头方向一路滑出棋盘，
  离开棋盘后逐渐褪成背景色，直到完全看不见；
- 尾迹：尾节离开某个格点后，原地短暂亮起一个灰点再淡掉；
- 被挡：整条线段变红，沿轨迹往前冲一下就弹回原位（之后由主程序
  把它标记成常驻暗红）。
"""

import math

from game.arrow import blit_disc, draw_arrow_head, lighten, stroke_polyline
from game import theme
from game.settings import WRONG_FLASH

FLY_SPEED = 26.0        # 沿线流动速度，单位：节（格）/秒
TRAIL_LIFE = 0.5        # 残影格点停留时间
TRAIL_FADE_IN = 0.09    # 残影淡入时长（不然是「啪」地蹦出来）
PUSH_STEPS = 0.55       # 被挡时沿轨迹前冲的节数
FADE_CELLS = 2.6        # 出界后多少格距离内淡到看不见
TOAST_DURATION = 1.0    # 底部提示文字停留时长


def point_at(route, s):
    """route 是相邻等距（一格）的像素点列表，返回弧长参数 s（单位：格）处位置。"""
    if s <= 0:
        return route[0]
    last = len(route) - 1
    if s >= last:
        return route[-1]
    index = int(s)
    frac = s - index
    x1, y1 = route[index]
    x2, y2 = route[index + 1]
    return (x1 + (x2 - x1) * frac, y1 + (y2 - y1) * frac)


def flow_points(route, n_cells, offset):
    """取 route 上弧长区间 [offset, offset + n_cells - 1] 的那一段折线。

    只按 s = offset, offset+1, offset+2 … 取点的话，落在两个采样点之间的
    拐角会被这两点连成的一条斜弦「削平」：画出来是一个斜角，而且随着
    offset 滑动，这个斜角每前进一格就削平一次、复原一次（FLY_SPEED 下
    每秒 26 次）—— 转弯处一闪一闪的抖动就是这么来的。把区间里的整数
    节点补回来，画出来的才是原折线真正的一段。
    """
    start = max(0.0, offset)
    end = start + max(0, n_cells - 1)

    points = [point_at(route, start)]
    first = int(math.floor(start)) + 1
    last = min(int(math.ceil(end)) - 1, len(route) - 1)
    for index in range(max(1, first), last + 1):
        if start < index < end:
            points.append(route[index])
    points.append(point_at(route, end))
    return points


def fade_color(color, ratio):
    """按比例把线段颜色混向背景色，得到「淡出」效果。"""
    bg = theme.get().bg
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(color[i] + (bg[i] - color[i]) * ratio) for i in range(3))


def trail_alpha(age):
    """残影亮度：快速淡入、再线性淡出（直接给满亮度会「闪」一下）。"""
    if age <= 0.0 or age >= TRAIL_LIFE:
        return 0
    fade_in = min(1.0, age / TRAIL_FADE_IN)
    return int(150 * fade_in * (1.0 - age / TRAIL_LIFE))


def draw_flowing(surface, route, n_cells, offset, direction, color, width):
    """把整条线段沿 route 向前推进 offset 格后画出（圆角折线 + 箭头）。"""
    points = flow_points(route, n_cells, offset)
    stroke_polyline(surface, points, color, width)
    draw_arrow_head(surface, direction, points[-1], int(width * 1.85), color)


class FlyingSegment:
    """飞出动画：各节沿「自身折线 + 箭头延长线」流动，淡出后销毁。"""

    def __init__(self, route, trail_points, n_cells, direction, color, width):
        self.route = route
        self.trail_points = trail_points
        self.n = n_cells
        self.direction = direction
        self.color = color
        self.width = width
        self.t = 0.0
        self.dead = False
        self.escaped = 0.0          # 已经跑到棋盘外的格数

    def update(self, dt, board_rect=None):
        self.t += dt * FLY_SPEED
        tail_x, tail_y = point_at(self.route, self.t)
        if board_rect is not None and not board_rect.collidepoint(tail_x,
                                                                  tail_y):
            self.escaped += dt * FLY_SPEED
        if self.escaped > FADE_CELLS:
            self.dead = True
        margin = self.width * 4
        if (tail_x < -margin or tail_x > theme_bounds()[0] + margin or
                tail_y < -margin or tail_y > theme_bounds()[1] + margin):
            self.dead = True

    def draw(self, surface):
        trail_color = theme.get().trail
        radius = max(2, int(self.width * 0.22))
        for index, pos in enumerate(self.trail_points):
            alpha = trail_alpha(self.t - index)
            if alpha > 0:
                blit_disc(surface, pos, radius, trail_color, alpha)

        color = fade_color(self.color, self.escaped / FADE_CELLS)
        draw_flowing(surface, self.route, self.n, self.t,
                     self.direction, color, self.width)


class BlockedFeedback:
    """被挡反馈：整条变红，沿自身轨迹前冲一下再弹回原位。"""

    def __init__(self, route, n_cells, arrow, width):
        self.arrow_id = arrow.id
        self.route = route
        self.n = n_cells
        self.direction = arrow.direction
        self.width = width
        self.timer = WRONG_FLASH
        self.dead = False

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.dead = True

    def draw(self, surface):
        progress = 1 - max(self.timer, 0) / WRONG_FLASH
        offset = PUSH_STEPS * math.sin(math.pi * progress)   # 前冲 -> 弹回
        draw_flowing(surface, self.route, self.n, offset,
                     self.direction, theme.get().danger, self.width)


class HintPulse:
    """提示高亮：给被提示的那支箭套一层会呼吸的浅色描边。"""

    def __init__(self, arrow, width):
        self.arrow_id = arrow.id
        self.width = width
        self.timer = 2.2

    def update(self, dt):
        self.timer -= dt
        return self.timer > 0

    def stroke_color(self, base):
        phase = (math.sin(self.timer * 6.0) + 1.0) / 2.0
        return lighten(base, int(40 + 70 * phase))


def theme_bounds():
    """当前逻辑画布尺寸（避免 import settings 形成环）。"""
    from game.settings import WINDOW_HEIGHT, WINDOW_WIDTH
    return WINDOW_WIDTH, WINDOW_HEIGHT
