"""飞行线段的平滑度测试。

对应缺陷：「线飞出去的时候不够平滑，特别是转弯处」。

原因是飞出动画的采样方式：整条线是「让各节沿自己那条折线往前流」，但采样
只取 s = offset, offset+1, offset+2 …（每格一个点）。拐角落在两个采样点中间
时，这两点之间会被连成一条**斜弦**，直角被削成斜角；而 offset 是连续增长
的，于是这个斜角每前进一格就「削平 → 复原」一次 —— FLY_SPEED 下一秒钟削
26 次，看起来就是转弯处一闪一闪的抖动。

这里锁住四件事：
1. `flow_points()` 画出来的一定是原折线的一段（长度守恒、拐点不丢）；
2. 补圆点只补在真拐弯的地方（直线段上补圆点会挂一串小疙瘩）；
3. 圆点与箭头是预渲染的抗锯齿小图，且按「形状+尺寸+颜色」缓存；
4. 位移是匀速的、与帧率无关，且单帧步进有上限（卡帧也不会瞬移）。
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                     # noqa: E402
import pytest                                     # noqa: E402

from game import theme                            # noqa: E402
from game.animations import (                     # noqa: E402
    FLY_SPEED,
    TRAIL_LIFE,
    FlyingSegment,
    flow_points,
    point_at,
    trail_alpha,
)
from game.arrow import (                          # noqa: E402
    Direction,
    arrow_head_sprite,
    disc_sprite,
    joint_indices,
    stroke_polyline,
)
from game.settings import WINDOW_HEIGHT, WINDOW_WIDTH   # noqa: E402
from main import FPS, MAX_FRAME_DT, Game                # noqa: E402

PITCH = 40.0        # 格子间距（像素）


@pytest.fixture
def game(tmp_path):
    instance = Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    yield instance
    pygame.quit()


def route_of(cells, pitch=PITCH):
    """把「格坐标」折线转成等距像素折线（模拟 _build_route 的产物）。"""
    return [(c * pitch + 20.0, r * pitch + 20.0) for (r, c) in cells]


def with_ray(cells, extra=10, pitch=PITCH):
    """折线 + 沿最后一个方向延长出去的滑出路径（和 _build_route 一样）。"""
    route = route_of(cells, pitch)
    return extend(route, extra)


def extend(route, extra):
    """把折线沿最后一段的方向再延长 extra 格（真正的滑出路径是条射线）。"""
    dx = route[-1][0] - route[-2][0]
    dy = route[-1][1] - route[-2][1]
    tail = route[-1]
    return route + [(tail[0] + dx * step, tail[1] + dy * step)
                    for step in range(1, extra + 1)]


def visible_length(points, rect):
    """折线「落在矩形里」的那部分长度（矩形外的被夹掉）。"""
    total = 0.0
    for p1, p2 in zip(points, points[1:]):
        clipped = rect.clipline(p1, p2)
        if clipped:
            total += math.dist(clipped[0], clipped[1])
    return total


# 一条带拐角的折线：→ ↓ ← ……，足够覆盖各种采样相位
ZIGZAG = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 3), (2, 4)]
BENT = [(0, 0), (0, 1), (0, 2), (0, 3)]          # 只有一格弯的短箭
CORNER_INDEX = 2                                  # ZIGZAG 里的第一个拐点


def polyline_length(points):
    return sum(math.dist(p1, p2) for p1, p2 in zip(points, points[1:]))


def phase_samples(count=24, span=3.0, start=0.0):
    return [start + span * i / count for i in range(count)]


# ---------------- 1. 折线取段：不能切角 ----------------

def test_flow_keeps_corner_vertex():
    """拐角落在区间里时，它必须出现在折线顶点上（而不是被斜弦切掉）。"""
    route = with_ray(ZIGZAG)
    corner = route_of(ZIGZAG)[CORNER_INDEX]
    for offset in phase_samples():
        points = flow_points(route, len(ZIGZAG), offset)
        if offset < CORNER_INDEX < offset + len(ZIGZAG) - 1:
            assert corner in points, "offset=%.2f 时拐点被切掉了" % offset


def test_flow_length_is_conserved():
    """任何相位下，这段折线的长度都该等于「节数 - 1」格的弧长。

    被切角时长度会变短（弦比两腰短），所以这是一条能抓住切角的硬指标。
    """
    route = with_ray(ZIGZAG)
    expected = (len(ZIGZAG) - 1) * PITCH
    for offset in phase_samples(count=48):
        points = flow_points(route, len(ZIGZAG), offset)
        assert polyline_length(points) == pytest.approx(expected), \
            "offset=%.3f 时线被拉短了（拐角被斜弦切掉）" % offset


def test_real_routes_keep_on_screen_geometry_exact(game):
    """正式关卡：画布上看得见的那一段，必须和「理论路径」逐段重合。

    理论路径 = 滑出路径再往箭头方向无限延长（真正的滑出就是条射线）。
    路径尽头那一小段被夹住没关系 —— 夹住的部分在画布外，看不见。
    """
    game.start_game()
    canvas = pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
    checked = 0
    for level in game.levels:
        game._load_level(level)
        for arrow in game.board.arrows:
            route, _ = game._build_route(arrow)
            exact = extend(route, 80)
            n_cells = len(arrow.cells)
            for step in range(0, 60):
                offset = step * 0.37
                real = flow_points(route, n_cells, offset)
                ideal = flow_points(exact, n_cells, offset)
                assert visible_length(real, canvas) == pytest.approx(
                    visible_length(ideal, canvas), abs=3.0), \
                    "%s 的箭 offset=%.2f 时画布里那一段和理论路径不重合" % (
                        level.get("name"), offset)
                checked += 1
    assert checked > 1000


def test_flow_starts_and_ends_on_the_route():
    route = with_ray(ZIGZAG)
    span = len(ZIGZAG) - 1
    for offset in phase_samples(count=12):
        points = flow_points(route, len(ZIGZAG), offset)
        assert points[0] == pytest.approx(point_at(route, offset))
        assert points[-1] == pytest.approx(point_at(route, offset + span))
        assert len(points) <= len(route) + 2      # 不重复堆点


def test_flow_at_launch_matches_the_static_arrow():
    """offset=0 时画出来的必须正好是线段原来的那几个格心。

    这样「盘面上的线段」和「刚开始飞的线段」严丝合缝，起飞的瞬间不会跳。
    """
    route = with_ray(BENT)
    points = flow_points(route, len(BENT), 0.0)
    assert [tuple(p) for p in points] == route_of(BENT)


def test_flow_points_are_axis_aligned():
    """直段必须横平竖直：斜的只可能是被切出来的角，正常不该出现。"""
    route = with_ray(ZIGZAG)
    for offset in phase_samples(count=20, span=2.5):
        points = flow_points(route, len(ZIGZAG), offset)
        for p1, p2 in zip(points, points[1:]):
            assert p1[0] == p2[0] or p1[1] == p2[1], (offset, p1, p2)


def test_flow_survives_offsets_past_the_route():
    """整条线滑出路径尽头之后不能崩，也不该画出一坨重复点。"""
    route = route_of(BENT)
    for offset in (len(route) - 1, len(route) + 5, 40.0):
        points = flow_points(route, len(route), offset)
        assert points[0] == route[-1] and points[-1] == route[-1]


# ---------------- 2. 圆点只补在拐弯处 ----------------

def test_joint_indices_on_straight_line():
    points = [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)]
    assert joint_indices(points) == [0, 4], "直线段上不该补圆点"


def test_joint_indices_marks_corners():
    points = [(0, 0), (10, 0), (20, 0), (20, 10), (20, 20)]
    assert joint_indices(points) == [0, 2, 4]


def test_joint_indices_handles_degenerate_input():
    assert joint_indices([(1, 2)]) == [0]
    assert joint_indices([(1, 2), (1, 2)]) == [0, 1]


def test_stroke_does_not_widen_the_straight_part():
    """直线段中间不能鼓包：补圆点会让线在节点处胖出 1~2 像素。"""
    width = 10
    surface = pygame.Surface((200, 60))
    surface.fill((0, 0, 0))
    route = route_of(BENT, pitch=50)
    surface.fill((0, 0, 0))
    stroke_polyline(surface, route, (255, 255, 255), width)

    def thickness(x):
        rows = [y for y in range(60)
                if surface.get_at((x, y))[:3] != (0, 0, 0)]
        return (max(rows) - min(rows) + 1) if rows else 0

    mid = int(route[1][0] + PITCH / 2)      # 第一个与第二个节点之间
    assert thickness(mid) == pytest.approx(width, abs=1), \
        "直线段中段被撑粗了"
    assert thickness(int(route[1][0])) <= width + 1


# ---------------- 3. 抗锯齿小贴图 ----------------

def test_disc_sprite_has_antialiased_rim():
    sprite = disc_sprite(6, (255, 0, 0))
    span = sprite.get_width()
    assert span == 13, "直径要跟 pygame 画的整数圆一致（2r+1）"
    center = sprite.get_at((span // 2, span // 2))
    assert center[:3] == (255, 0, 0)
    assert center[3] == 255

    alphas = {sprite.get_at((x, y))[3]
              for x in range(span) for y in range(span)}
    assert any(0 < a < 255 for a in alphas), "边缘没有半透明像素 = 硬锯齿"
    assert 0 in alphas, "圆外面的角上必须是全透明"

    # 全透明的地方也不能渗黑：缩小取平均时会把黑边带进半透明像素
    for x in range(span):
        for y in range(span):
            if sprite.get_at((x, y))[3] == 0:
                assert sprite.get_at((x, y))[:3] == (255, 0, 0)


def test_disc_sprite_is_cached():
    assert disc_sprite(5, (10, 20, 30)) is disc_sprite(5, (10, 20, 30))
    assert disc_sprite(5, (10, 20, 30)) is not disc_sprite(6, (10, 20, 30))


def test_arrow_head_sprite_covers_the_triangle():
    for direction in Direction:
        sprite = arrow_head_sprite(direction, 18, (0, 255, 0))
        assert sprite.get_width() == sprite.get_height()
        assert sprite.get_width() > 18
        assert sprite.get_at((sprite.get_width() // 2,
                              sprite.get_height() // 2))[3] == 255


def test_arrow_head_sprite_scales_with_size():
    small = arrow_head_sprite(Direction.UP, 8, (1, 2, 3)).get_width()
    big = arrow_head_sprite(Direction.UP, 40, (1, 2, 3)).get_width()
    assert big > small * 3


# ---------------- 4. 位移平滑：匀速、与帧率无关、有上限 ----------------

def make_flying(pitch=PITCH):
    route = route_of(BENT, pitch)
    return FlyingSegment(route, list(route[:2]), len(route),
                         Direction.RIGHT, (255, 0, 0), 8)


def test_flight_is_constant_speed():
    flying = make_flying()
    step = 1.0 / FPS
    for _ in range(30):
        before = flying.t
        flying.update(step)
        assert flying.t - before == pytest.approx(FLY_SPEED * step)


def test_flight_is_frame_rate_independent():
    """60 帧一步 与 120 帧两步，走到的位置必须一样（否则会一顿一顿）。"""
    fast, slow = make_flying(), make_flying()
    for _ in range(10):
        fast.update(1.0 / FPS)
    for _ in range(20):
        slow.update(1.0 / (FPS * 2))
    assert fast.t == pytest.approx(slow.t, abs=1e-9)


def test_flight_never_jumps_more_than_a_step():
    """任何一帧的位移都不该超过「速度 × 单帧上限」。"""
    flying = make_flying()
    limit = FLY_SPEED * MAX_FRAME_DT
    previous = flying.t
    for dt in (1 / FPS, 1 / FPS, 0.2, 1 / FPS, 0.5):
        flying.update(min(dt, MAX_FRAME_DT))
        assert flying.t - previous <= limit + 1e-9
        previous = flying.t


def test_frame_dt_is_clamped(game):
    """clock 报出 500 毫秒（切窗口回来）时，步进要夹到上限。"""

    class SlowClock:
        def tick(self, fps=0):
            return 500

    game.clock = SlowClock()
    assert game._frame_dt() == pytest.approx(MAX_FRAME_DT)
    assert MAX_FRAME_DT * FLY_SPEED < 3.0, "上限别放太松，一格一格跳就白夹了"


def test_trail_fades_in_and_out():
    assert trail_alpha(0.0) == 0
    assert trail_alpha(-0.1) == 0
    assert trail_alpha(TRAIL_LIFE) == 0
    assert trail_alpha(TRAIL_LIFE * 2) == 0
    peak = max(trail_alpha(a / 100.0 * TRAIL_LIFE) for a in range(1, 100))
    assert peak > 60
    assert trail_alpha(0.02) < peak, "要淡入，不能「啪」地蹦到最亮"


def test_launch_and_draw_do_not_crash(game):
    """端到端：真的点一支能飞的箭，把动画画完。"""
    game.start_game()
    arrow = game.board.flyable_arrows()[0]
    game._launch(arrow)
    assert game.flying
    for _ in range(40):
        game._update(1.0 / FPS)
        game._draw()
    assert not game.flying or game.flying[0].t > 0
    assert 0 <= game.board_x <= WINDOW_WIDTH
    assert 0 <= game.board_y <= WINDOW_HEIGHT


def test_blocked_feedback_keeps_the_bend(game):
    """被挡时的前冲同样是「沿折线滑动」，也不能切角。"""
    game.start_game()
    blocked = next(a for a in game.board.arrows
                   if not game.board.can_fly_arrow(a))
    game._block(blocked)
    assert game.blocked
    route, _ = game._build_route(blocked)
    for _ in range(24):
        game._update(1.0 / FPS)
        game._draw()
    assert route[0] in flow_points(route, len(blocked.cells), 0.0)
