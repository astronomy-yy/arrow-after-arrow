"""线段与箭头的画法测试。

对应需求：「箭头和线再美化一下」。这次改的全是「看起来」的东西，所以
测法也全部落在像素上 —— 渲染到一张纯色底上，再量真实轮廓：

1. 线宽处处相等（回归「每个拐点、每个端头都鼓出一小块」）；
2. 收口圆点必须和 pygame 画粗线用同一套像素规则；
3. 箭头是一枚「飞镖」：底边比线身宽、倒钩前掠、尾凹正好收在折线末端；
4. 外描边只在外围加一圈，不盖住线身，力度跟主题走；
5. 静止线段与刚起飞的线段逐像素一致（同一套画法，起飞瞬间不跳）。
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                     # noqa: E402
import pytest                                     # noqa: E402

from game import theme                            # noqa: E402
from game.animations import draw_flowing, flow_points   # noqa: E402
from game.arrow import (                          # noqa: E402
    HEAD_LENGTH_RATIO,
    HEAD_SPAN_RATIO,
    HEAD_SWEEP_RATIO,
    RIM_RATIO,
    Direction,
    arrow_head_points,
    arrow_head_sprite,
    blit_disc,
    disc_sprite,
    draw_segment,
    head_box,
    rim_color,
    rim_width,
    segment_width,
    stroke_polyline,
    stroke_span,
)
from game.settings import (                       # noqa: E402
    MAX_SEGMENT_WIDTH,
    MIN_SEGMENT_WIDTH,
    SEGMENT_WIDTH_RATIO,
)
from game.states import GameState                 # noqa: E402

BG = (12, 14, 22)
INK = (247, 205, 74)
WIDTHS = (5, 8, 12, 15)          # 覆盖奇数宽与偶数宽两种像素规则


# ---------------- 量轮廓的小工具 ----------------

def blank(w=240, h=160):
    surface = pygame.Surface((w, h))
    surface.fill(BG)
    return surface


def filled(surface, x, y):
    return surface.get_at((x, y))[:3] != BG


def rows_of(surface, x):
    """某一列上被涂到的行列表。"""
    return [y for y in range(surface.get_height()) if filled(surface, x, y)]


def cols_of(surface, y):
    """某一行上被涂到的列列表。"""
    return [x for x in range(surface.get_width()) if filled(surface, x, y)]


def run_through(surface, x, y):
    """(x, y) 所在竖直连续带的长度（= 水平线段在那一列的粗细）。"""
    if not filled(surface, x, y):
        return 0
    top = bottom = y
    while top > 0 and filled(surface, x, top - 1):
        top -= 1
    limit = surface.get_height() - 1
    while bottom < limit and filled(surface, x, bottom + 1):
        bottom += 1
    return bottom - top + 1


def band(surface, x):
    """某一列上被涂到的行区间（左闭右开），没涂到就是 None。"""
    rows = rows_of(surface, x)
    return (rows[0], rows[-1] + 1) if rows else None


def extent(surface, x, top, bottom):
    """某一列上被涂到的行数（量箭头在某个位置的张角）。"""
    return sum(1 for y in range(top, bottom) if filled(surface, x, y))


def stroke_band(center, width):
    """宽 width 的笔画落在 center 上时应覆盖的行区间（左闭右开）。"""
    start = stroke_span(center, width)
    return (start, start + width)


def axis(center, width):
    """轴线所在的那一行 / 那一列（偶数宽会多压半格，见 stroke_span）。"""
    return center + (width - 1) // 2


# ---------------- 1. 线宽处处相等 ----------------

@pytest.mark.parametrize("width", WIDTHS)
def test_straight_run_has_one_constant_band(width):
    """一条直线段，从头到尾每一列的行区间都必须完全一样。

    这是「线宽处处相等」最直接的写法：只要有一列胖了一像素，区间就变了。
    """
    surface = blank()
    stroke_polyline(surface, [(50, 70), (170, 70)], INK, width)
    assert {band(surface, x) for x in range(50, 171)} == \
        {stroke_band(70, width)}


@pytest.mark.parametrize("width", WIDTHS)
def test_corner_join_is_exactly_the_union_of_the_two_arms(width):
    """拐点处只该是两条臂的并集，不能因为补了个圆点就多出一圈。"""
    half = (width - 1) // 2
    surface = blank()
    stroke_polyline(surface, [(60, 30), (60, 90), (160, 90)], INK, width)

    union = (30 - half, 90 - half + width)
    assert band(surface, 60) == union, "拐角那条竖线上多出或少了一圈"

    stem = range(60 - half, 60 - half + width)
    for x in range(60, 161):
        if x in stem:
            continue              # 这几列竖臂也铺过来，量的是并集
        assert band(surface, x) == stroke_band(90, width), \
            "x=%d 处横臂被撑粗了" % x


@pytest.mark.parametrize("width", WIDTHS)
def test_nothing_exceeds_the_union_of_the_arms(width):
    """整幅扫一遍：涂到的像素不能超出「两条臂的并集」一寸。

    这是「线上挂小疙瘩」的总回归 —— 收口圆点曾经比线宽多 1 像素，
    拐点与端头各鼓出一小块，这条用例一量就露馅。
    """
    half = (width - 1) // 2
    surface = blank()
    stroke_polyline(surface, [(60, 30), (60, 90), (160, 90)], INK, width)

    rows_union = (30 - half, 90 - half + width)
    cols_union = (60 - half, 160 - half + width)

    cols = [x for x in range(surface.get_width()) if rows_of(surface, x)]
    assert (cols[0], cols[-1] + 1) == cols_union
    for x in cols:
        ys = rows_of(surface, x)
        assert rows_union[0] <= ys[0] and ys[-1] + 1 <= rows_union[1], \
            "x=%d 处鼓出去了" % x

    rows = [y for y in range(surface.get_height()) if cols_of(surface, y)]
    assert rows[0] == rows_union[0] and rows[-1] + 1 == rows_union[1]


@pytest.mark.parametrize("width", WIDTHS)
def test_round_cap_extends_exactly_half_a_width(width):
    """圆头只长出半个线宽，两端对称，且圆头本身也只有线宽那么粗。"""
    surface = blank()
    stroke_polyline(surface, [(60, 70), (160, 70)], INK, width)

    left = stroke_span(60, width)
    right = stroke_span(160, width) + width - 1
    cols = [x for x in range(surface.get_width())
            if any(filled(surface, x, y)
                   for y in range(surface.get_height()))]
    assert (min(cols), max(cols)) == (left, right)
    assert max(cols) - min(cols) + 1 == 100 + width
    for x in cols:
        assert max(rows_of(surface, x)) - min(rows_of(surface, x)) + 1 \
            <= width, x


@pytest.mark.parametrize("width", WIDTHS)
def test_disc_covers_the_same_pixels_as_the_line(width):
    """同一位置上，圆点涂到的像素和同宽的线段完全一样。

    pygame 画粗线并不是「以中心点左右各半个宽」：宽 12 画在 y=100 上
    实际涂的是 95~106 行。圆点贴图必须按同一条规则摆，否则接缝处会错开
    1 像素 —— 那正是「拐点鼓包」的真正来源。
    """
    line = blank()
    stroke_polyline(line, [(60, 70), (160, 70)], INK, width)

    disc = blank()
    blit_disc(disc, (110, 70), width / 2.0, INK)

    sprite = disc_sprite(width / 2.0, INK)
    assert sprite.get_width() == sprite.get_height() == width
    assert band(disc, 110) == stroke_band(70, width)
    assert band(line, 110) == stroke_band(70, width)

    cols = [x for x in range(disc.get_width()) if rows_of(disc, x)]
    assert (cols[0], cols[-1] + 1) == (stroke_span(110, width),
                                       stroke_span(110, width) + width)
    # 竖直方向必须落在和线段完全相同的行上
    assert band(disc, 110) == band(line, 110)


def test_stroke_span_matches_pygame_rule():
    """宽 span 的笔画在 center 处覆盖 pixels[center - (span-1)//2 ...]。"""
    for span in (5, 12, 15):
        assert stroke_span(100, span) == 100 - (span - 1) // 2
    assert stroke_span(100, 15) == 93
    assert stroke_span(100, 12) == 95


# ---------------- 2. 箭头几何 ----------------

def test_head_is_a_dart_not_a_triangle():
    """箭头的尾凹落在折线末端，倒钩前掠到它前面去。

    量每一列的张角：尾根处几乎为 0（凹口的收口点），前掠处最宽（两个
    倒钩），再往尖端收细。等腰三角做不到「尾根处最窄」这一点。
    """
    width = 15
    surface = blank(260, 160)
    anchor = (100, 80)
    points = arrow_head_points(Direction.RIGHT, anchor, width)
    pygame.draw.polygon(surface, INK, [(int(x), int(y)) for x, y in points])

    at_root = extent(surface, anchor[0], 40, 120)
    sweep = int(round(width * HEAD_SWEEP_RATIO))
    at_barb = extent(surface, anchor[0] + sweep, 40, 120)
    at_tip = extent(surface, anchor[0] + int(width * HEAD_LENGTH_RATIO) - 1,
                    40, 120)

    assert at_root <= 2, "尾根处应该是凹口的收口点，不该是整条底边"
    assert at_barb == pytest.approx(width * HEAD_SPAN_RATIO, abs=2)
    assert at_barb > at_root + width, "倒钩必须明显比尾根宽"
    assert at_tip < at_barb


def test_head_points_wrap_around_the_shape():
    """四个顶点按「尖 -> 倒钩 -> 尾凹 -> 倒钩」绕一圈。"""
    width = 12
    points = arrow_head_points(Direction.UP, (50, 50), width)
    assert len(points) == 4 and len(set(points)) == 4
    assert points[0][1] == min(p[1] for p in points), "尖端在方向最前面"
    assert points[2] == (50, 50), "尾凹必须正好落在折线末端"
    assert points[1][1] < 50 and points[3][1] < 50, "两个倒钩要前掠"


def test_head_ratios_follow_the_settings():
    """底边宽、长度都得按设置里的比例来。"""
    width = 10
    tip, barb_a, _, barb_b = arrow_head_points(Direction.RIGHT, (0, 0), width)
    assert math.dist(barb_a, barb_b) == pytest.approx(
        width * HEAD_SPAN_RATIO, abs=0.01)
    assert tip[0] == pytest.approx(width * HEAD_LENGTH_RATIO, abs=0.01)


def test_head_box_contains_the_head():
    for direction in Direction:
        x0, y0, w, h = head_box(direction, 14)
        for x, y in arrow_head_points(direction, (0, 0), 14):
            assert x0 <= x <= x0 + w
            assert y0 <= y <= y0 + h


def test_head_box_grows_with_width():
    small = head_box(Direction.RIGHT, 6)
    big = head_box(Direction.RIGHT, 18)
    assert big[2] > small[2] and big[3] > small[3]


def test_head_sprite_matches_its_box():
    for direction in Direction:
        sprite = arrow_head_sprite(direction, 14, INK)
        assert sprite.get_size() == head_box(direction, 14)[2:]
        alphas = {sprite.get_at((x, y))[3]
                  for x in range(sprite.get_width())
                  for y in range(sprite.get_height())}
        assert 255 in alphas, "贴图里得有实心的部分"


def test_head_sprite_has_antialiased_edges():
    """斜边要有半透明过渡像素：pygame 的 draw.polygon 本身不带抗锯齿。"""
    sprite = arrow_head_sprite(Direction.UP, 16, INK)
    alphas = {sprite.get_at((x, y))[3]
              for x in range(sprite.get_width())
              for y in range(sprite.get_height())}
    assert 0 in alphas, "图形外面必须是全透明"
    assert 255 in alphas, "图形里面必须是不透明"
    assert any(0 < a < 255 for a in alphas), "斜边没有半透明像素 = 硬锯齿"


def test_head_sprite_is_cached_and_keyed():
    assert (arrow_head_sprite(Direction.UP, 12, INK)
            is arrow_head_sprite(Direction.UP, 12, INK))
    assert (arrow_head_sprite(Direction.UP, 12, INK)
            is not arrow_head_sprite(Direction.UP, 13, INK))
    assert (arrow_head_sprite(Direction.UP, 12, INK)
            is not arrow_head_sprite(Direction.DOWN, 12, INK))


def test_head_sprite_pad_grows_the_shape():
    """描边用的是「撑大一圈的同款箭头」，撑大后贴图也要跟着变大。"""
    plain = arrow_head_sprite(Direction.RIGHT, 12, INK)
    padded = arrow_head_sprite(Direction.RIGHT, 12, INK, pad=2)
    assert padded.get_width() > plain.get_width()
    assert padded.get_height() > plain.get_height()


# ---------------- 3. 外描边 ----------------

@pytest.mark.parametrize("width", (8, 12, 15))
def test_outline_is_exactly_one_ring(width):
    """带描边时整条线只比线身粗 2×描边宽，而且里外分两层颜色。"""
    rim = rim_width(width)
    surface = blank()
    draw_segment(surface, [(60, 70), (160, 70)], Direction.RIGHT, INK, width)

    row = axis(70, width)
    outer = band(surface, 110)
    assert outer == stroke_band(70, width + rim * 2)
    assert outer[1] - outer[0] == width + rim * 2

    assert surface.get_at((110, outer[0]))[:3] == rim_color(INK)
    assert surface.get_at((110, outer[1] - 1))[:3] == rim_color(INK)
    assert surface.get_at((110, row))[:3] == INK
    # 线身仍然是原来的宽度，描边只在它外面
    inner = [y for y in range(outer[0], outer[1])
             if surface.get_at((110, y))[:3] == INK]
    assert len(inner) == width


def test_outline_can_be_turned_off():
    width = 12
    surface = blank()
    draw_segment(surface, [(60, 70), (160, 70)], Direction.RIGHT, INK, width,
                 outline=False)
    row = axis(70, width)
    assert band(surface, 110) == stroke_band(70, width)
    assert surface.get_at((110, row))[:3] == INK
    assert not filled(surface, 110, stroke_band(70, width)[0] - 1)


def test_rim_width_follows_the_line():
    assert rim_width(4) == 1
    assert rim_width(15) >= rim_width(6)
    assert rim_width(30) > rim_width(15)
    assert rim_width(6) == max(1, round(6 * RIM_RATIO))


def test_rim_is_darker_but_keeps_the_hue():
    """描边是「同色压暗」，不是往黑里掺 —— 掺黑会把蓝紫压成脏灰。"""
    for name in ("night", "day"):
        theme.set_theme(name)
        rim = rim_color(INK)
        assert all(r < c for r, c in zip(rim, INK)), (name, rim)
        # 各通道等比缩小：最亮与最暗通道的差距比例不该被改变
        before = (INK[0] - INK[2]) / INK[0]
        after = (rim[0] - rim[2]) / rim[0]
        assert after == pytest.approx(before, abs=0.02), name
    theme.set_theme("night")


def test_rim_shade_differs_by_theme():
    """深色底描边压得狠，浅色底压得轻，否则日间主题会整片发黑。"""
    theme.set_theme("night")
    night = rim_color(INK)
    theme.set_theme("day")
    day = rim_color(INK)
    theme.set_theme("night")
    assert sum(night) < sum(day)


# ---------------- 4. 线宽本身 ----------------

def test_segment_width_tracks_the_cell_and_clamps():
    assert segment_width(60) == MAX_SEGMENT_WIDTH
    assert segment_width(12) == MIN_SEGMENT_WIDTH
    assert segment_width(40) == int(40 * SEGMENT_WIDTH_RATIO)
    assert MIN_SEGMENT_WIDTH <= segment_width(1) <= MAX_SEGMENT_WIDTH


# ---------------- 5. 静止与飞行同一套画法 ----------------

def test_flight_starts_pixel_identical_to_the_static_arrow():
    """offset=0 时飞出的那一帧，必须和盘面上那一支一模一样。

    两处要是走了不同的画法，起飞瞬间就会「换个样子」闪一下。
    """
    width = 12
    centers = [(50, 40), (50, 90), (140, 90), (140, 130)]
    route = list(centers) + [(140, 170), (140, 210)]      # 滑出路径

    static = blank(200, 240)
    draw_segment(static, centers, Direction.DOWN, INK, width)

    flying = blank(200, 240)
    draw_flowing(flying, route, len(centers), 0.0, Direction.DOWN, INK, width)

    assert flow_points(route, len(centers), 0.0) == centers
    for x in range(200):
        for y in range(240):
            assert static.get_at((x, y)) == flying.get_at((x, y)), (x, y)


# ---------------- 6. 端到端 ----------------

@pytest.fixture
def game(tmp_path):
    from main import Game
    instance = Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    yield instance
    theme.set_theme("night")
    pygame.quit()


def test_board_arrow_uses_the_new_stroke_style(game):
    """用棋盘上真实的线宽画一支箭，量出来得是「线身 + 一圈描边」。"""
    game.start_game()
    game._load_level(game.levels[0])
    width = segment_width(game.cell_size)
    rim = rim_width(width)
    arrow = game.board.arrows[0]

    surface = blank()
    draw_segment(surface, [(60, 70), (160, 70)], arrow.direction,
                 arrow.color, width)

    row = axis(70, width)
    outer = band(surface, 110)
    assert outer == stroke_band(70, width + rim * 2)
    assert surface.get_at((110, row))[:3] == arrow.color
    assert surface.get_at((110, outer[0]))[:3] == rim_color(arrow.color)


def test_arrow_head_fits_inside_a_cell(game):
    """箭头不能长过一格的间距，否则会盖到下一格的线段上（看着像穿模）。"""
    game.start_game()
    for level in game.levels:
        game._load_level(level)
        pitch = game.cell_size + game.cell_gap
        width = segment_width(game.cell_size)
        assert width * (HEAD_LENGTH_RATIO + HEAD_SWEEP_RATIO) < pitch, \
            level.get("name")
        assert width * HEAD_SPAN_RATIO < pitch, level.get("name")


def test_every_level_draws_in_both_themes(game):
    """12 关 × 日夜两套主题整盘渲染一遍，都得画得出东西、不报错。"""
    game.start_game()
    for level in game.levels:
        game._load_level(level)
        game.state = GameState.PLAYING
        for name in ("night", "day"):
            theme.set_theme(name)
            game._update_view()
            game._draw()
            colors = {game.canvas.get_at((x, y))[:3]
                      for x in range(0, 640, 16)
                      for y in range(170, 1010, 16)}
            assert len(colors) > 3, (level.get("name"), name, colors)
    theme.set_theme("night")


def test_flying_frame_draws_the_head_at_the_front(game):
    """飞出中的每一帧也要有箭头，而且箭头始终在最前面。"""
    game.start_game()
    game._load_level(game.levels[0])
    game.state = GameState.PLAYING
    width = segment_width(game.cell_size)
    arrow = max(game.board.arrows, key=lambda a: len(a.cells))
    route, _ = game._build_route(arrow)
    checked = 0

    for step in (0.0, 1.7, 3.4):
        surface = blank(640, 1140)
        draw_flowing(surface, route, len(arrow.cells), step,
                     arrow.direction, arrow.color, width)
        tip_x, tip_y = flow_points(route, len(arrow.cells), step)[-1]
        ix, iy = int(round(tip_x)), int(round(tip_y))
        if not (4 <= ix < 636 and 4 <= iy < 1136):
            continue                 # 尖端已经飞出画布，这一帧不量
        checked += 1
        assert any(filled(surface, ix + dx, iy + dy)
                   for dx in range(-3, 4) for dy in range(-3, 4)), \
            "offset=%.1f 时尖端附近没有画出箭头" % step
    assert checked >= 1
