"""方向枚举、方向映射与线段箭绘制。

一支线段箭 = 一条粗折线 + 末端一个实心三角箭头。折线都是横平竖直的，
所以直段的边本来就是锐利的整数像素边界；真正需要抗锯齿的只有两处：

1. 折线的拐角与端头（用预渲染的抗锯齿圆点收口）；
2. 箭头三角的两条斜边（用预渲染的抗锯齿三角贴图）。

除此之外还描一圈比线身更深的**外描边**：深色底上线段的边缘本来就靠
明度差「切」出来，加一圈深色描边之后边缘更利落，两条线挨在一起时也
多一层分隔，盘面不至于糊成一片。
"""

import math
from enum import Enum

import pygame

from game import theme
from game.settings import (
    HEAD_LENGTH_RATIO,
    HEAD_SPAN_RATIO,
    HEAD_SWEEP_RATIO,
    MAX_SEGMENT_WIDTH,
    MIN_SEGMENT_WIDTH,
    RIM_RATIO,
    RIM_SHADE,
    SEGMENT_WIDTH_RATIO,
)

# 空格标记
EMPTY = "."


class Direction(Enum):
    """四个飞行方向，枚举值与关卡数据字符一致。"""

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


def segment_width(cell_size):
    """按格子大小算线宽，保证缩放时线宽与格子的比例稳定。"""
    width = int(cell_size * SEGMENT_WIDTH_RATIO)
    return max(MIN_SEGMENT_WIDTH, min(MAX_SEGMENT_WIDTH, width))


def rim_width(width):
    """外描边宽度：跟着线宽走。线粗了描边也粗一档，比例才不会走样。"""
    return max(1, int(round(width * RIM_RATIO)))


def _dir_xy(direction):
    """方向 -> 屏幕 (x, y) 单位增量（行列增量换到 x/y）。"""
    dr, dc = DIRECTION_DELTA[Direction(direction)]
    return float(dc), float(dr)


# ---------------- 颜色 ----------------

def lighten(color, amount=55):
    """提亮一个颜色，用于悬停 / 提示高亮。"""
    return tuple(min(255, channel + amount) for channel in color[:3])


def darken(color, ratio=RIM_SHADE):
    """压暗一个颜色，用于外描边。"""
    return tuple(int(channel * ratio) for channel in color[:3])


def rim_color(color):
    """外描边色：线身压暗一档，色相不变。

    用「乘一个系数」而不是「减一个常数」，浅色和深色才会压暗得一样匀；
    减常数会把深色（比如蓝、紫）直接压成黑，描边就脏了。压暗的力度按
    主题给：深色底要压狠一点边缘才切得出来，浅色底压狠了整片线段发黑。
    """
    return darken(color, theme.get().rim_shade)


# ---------------- 抗锯齿小贴图 ----------------

SPRITE_SCALE = 4            # 小图形的超采样倍数（4 倍 = 16 个子像素）
HEAD_PAD = 2                # 箭头贴图四周多留的空白，免得斜边被切掉
_SPRITE_CACHE = {}
_SPRITE_CACHE_LIMIT = 512


def _cached_sprite(key, build):
    """按 key 缓存贴图：图形只跟「形状 + 尺寸 + 颜色」有关，缓存后每帧只是 blit。"""
    sprite = _SPRITE_CACHE.get(key)
    if sprite is None:
        if len(_SPRITE_CACHE) >= _SPRITE_CACHE_LIMIT:
            _SPRITE_CACHE.clear()
        sprite = _SPRITE_CACHE[key] = build()
    return sprite


def disc_sprite(radius, color):
    """抗锯齿实心圆，直径 = 2 × radius。

    直径必须和 pygame 画的线宽**逐像素对齐**：宽 w 的线段实占 w 个像素，
    收口圆点也得占同样多。先前按 pygame 画圆的老规矩取 2r+1，直径比线宽
    多出 1 像素，于是每个拐点、每个端头都会鼓出一小块 —— 放大看就是线上
    挂了一串小疙瘩。
    """
    radius = max(0.5, float(radius))
    span = max(1, int(round(radius * 2)))
    color = tuple(color[:3])

    def build():
        scale = SPRITE_SCALE
        big = pygame.Surface((span * scale, span * scale), pygame.SRCALPHA)
        # 透明处也填成同一个颜色：缩小时取平均才不会往边上渗黑
        big.fill((*color, 0))
        center = span * scale / 2.0
        pygame.draw.circle(big, (*color, 255), (center, center),
                           max(1, int(round(radius * scale))))
        return pygame.transform.smoothscale(big, (span, span))

    return _cached_sprite(("disc", span, color), build)


def stroke_span(center, span):
    """宽 span 的笔画落在 center 处时，覆盖像素区间的起点。

    pygame 画粗线时不是「以 center 为中心左右各半个宽」：宽 12 画在 y=100
    上的实际是 95~106 行。要跟它严丝合缝地接上，圆点和箭头贴图都得按
    同一条规则摆，差 1 像素就会在接缝处露出台阶。
    """
    return int(round(center)) - (span - 1) // 2


def blit_disc(surface, center, radius, color, alpha=None):
    """贴一个抗锯齿圆点（圆头 / 圆角拐点 / 残影 / 辅助线都用它）。"""
    sprite = disc_sprite(radius, color)
    sprite.set_alpha(255 if alpha is None else max(0, min(255, int(alpha))))
    span = sprite.get_width()
    surface.blit(sprite, (stroke_span(center[0], span),
                          stroke_span(center[1], span)))


# ---------------- 箭头 ----------------

def arrow_head_points(direction, anchor, width, pad=0.0):
    """箭头的四个顶点：尖端、两个倒钩、尾凹。

    anchor 是折线末端（线段最后一格的中心），也就是箭头的尾根：
    两个倒钩**前掠**到它前面去，尾凹收口正好落在它身上。这样画出来是
    一枚「飞镖」而不是一个等腰三角 —— 后缘微微向内兜住线身，箭头看着
    更利落，线身那个圆头也刚好填进凹口里，不会在箭头屁股后面露出一截。

    pad 把整个箭头往外撑一圈（描边用的就是「撑大一圈的同款箭头」）。
    """
    px, py = anchor
    fx, fy = _dir_xy(direction)
    perp = (-fy, fx)                          # 垂直方向
    span = width * HEAD_SPAN_RATIO / 2.0 + pad    # 底边半宽
    sweep = width * HEAD_SWEEP_RATIO + pad        # 倒钩前掠
    length = width * HEAD_LENGTH_RATIO + pad      # 尾根到尖端

    return [
        (px + fx * length, py + fy * length),
        (px + fx * sweep + perp[0] * span, py + fy * sweep + perp[1] * span),
        (px, py),
        (px + fx * sweep - perp[0] * span, py + fy * sweep - perp[1] * span),
    ]


def head_box(direction, width, pad=0.0):
    """箭头相对尾根的整数包围盒 (x0, y0, w, h)，已含四周留白。"""
    fx, fy = _dir_xy(direction)
    perp = (-fy, fx)
    span = width * HEAD_SPAN_RATIO / 2.0 + pad
    sweep = width * HEAD_SWEEP_RATIO + pad
    length = width * HEAD_LENGTH_RATIO + pad

    xs = [0.0, fx * length, fx * sweep + perp[0] * span,
          fx * sweep - perp[0] * span]
    ys = [0.0, fy * length, fy * sweep + perp[1] * span,
          fy * sweep - perp[1] * span]
    x0 = int(math.floor(min(xs))) - HEAD_PAD
    y0 = int(math.floor(min(ys))) - HEAD_PAD
    w = int(math.ceil(max(xs))) + HEAD_PAD - x0
    h = int(math.ceil(max(ys))) + HEAD_PAD - y0
    return x0, y0, w, h


def arrow_head_sprite(direction, width, color, pad=0.0):
    """抗锯齿箭头贴图；贴图内的坐标按 head_box() 对齐尾根。"""
    width = max(1.0, float(width))
    color = tuple(color[:3])
    direction = Direction(direction)
    x0, y0, w, h = head_box(direction, width, pad)

    def build():
        scale = SPRITE_SCALE
        big = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
        big.fill((*color, 0))
        points = [(x - x0, y - y0) for x, y in
                  arrow_head_points(direction, (0.0, 0.0), width, pad)]
        pygame.draw.polygon(big, (*color, 255),
                            [(x * scale, y * scale) for x, y in points])
        return pygame.transform.smoothscale(big, (w, h))

    return _cached_sprite(("head", direction, round(width, 3), round(pad, 3),
                           color), build)


def draw_arrow_head(surface, direction, anchor, width, color, pad=0.0):
    """在折线末端贴一个箭头，尾凹正对折线末端。"""
    sprite = arrow_head_sprite(direction, width, color, pad)
    x0, y0, _, _ = head_box(direction, width, pad)
    surface.blit(sprite, (int(round(anchor[0])) + x0,
                          int(round(anchor[1])) + y0))


# ---------------- 折线 ----------------

def joint_indices(points):
    """折线里「需要补圆点」的节点下标：两端 + 真正拐弯的地方。

    直线段上的中间节点不用补：圆点只是把拐角磨圆、把端头收圆，直线上
    本来就没有角可磨，补了反而多一层半透明叠加。
    """
    indices = [0]
    for index in range(1, len(points) - 1):
        ax = points[index][0] - points[index - 1][0]
        ay = points[index][1] - points[index - 1][1]
        bx = points[index + 1][0] - points[index][0]
        by = points[index + 1][1] - points[index][1]
        if ax * by != ay * bx:               # 叉积非零：这里拐弯了
            indices.append(index)
    if len(points) > 1:
        indices.append(len(points) - 1)
    return indices


def stroke_polyline(surface, points, color, width):
    """画一条粗折线：直段逐段画实心矩形，拐点与两端用圆点收口。

    线段都是横平竖直的，直段的边本来就锐利；圆点只负责把拐角磨圆、
    把端头收成圆头 —— 顺带因为带抗锯齿，拐角不会有一圈锯齿。圆点直径
    与线宽严格相等，所以接缝处不会鼓出来。
    """
    width = int(width)
    for p1, p2 in zip(points, points[1:]):
        pygame.draw.line(surface, color, p1, p2, width)
    for index in joint_indices(points):
        blit_disc(surface, points[index], width / 2.0, color)


def draw_arrow(surface, centers, direction, color, width, pad=0.0):
    """一笔画完一支箭：折线 + 箭头（不加描边）。"""
    if not centers:
        return
    width = int(width)
    stroke_polyline(surface, centers, color, width)
    draw_arrow_head(surface, direction, centers[-1], width, color, pad)


def draw_segment(surface, centers, direction, color, width=None,
                 cell_size=None, outline=True):
    """画一支线段箭：外描边 + 线身 + 箭头。

    centers：按「尾端 -> 箭头端」顺序的像素坐标列表。
    outline=False 时只画线身（悬停 / 提示的那圈光晕用它，光晕再描边就脏了）。
    """
    if width is None:
        width = segment_width(cell_size or 34)
    width = int(width)
    if not centers:
        return
    if outline:
        rim = rim_width(width)
        # 描边不是「把整支箭放大」：那样箭头会比线身多粗出好几倍。
        # 线身加宽 2×rim、箭头往外撑 rim，两边才是同样厚的一圈。
        draw_arrow(surface, centers, direction, rim_color(color),
                   width + rim * 2, pad=rim)
    draw_arrow(surface, centers, direction, color, width)
