"""界面观感增强（渐变 / 柔光 / 投影 / 卡片）的测试。

对应需求：「界面、背景、按钮等再美化一下」。美化类改动最容易变成
「看不出退化」的玄学，所以这里全部落在可量的东西上：

1. 渐变真的有渐变（两端等于给定色、中间在两色之间、逐行单调）；
2. 柔光中心亮、边缘透明，半透明像素不许渗黑；
3. 投影越靠外越淡，贴出去之后卡片本体那一块不许被涂脏；
4. 卡片的圆角真的切掉了角、描边在形状内侧、整块可以半透明；
5. 缓存按参数命中，条数有上限（不然拖滑杆会把内存灌满）；
6. 按钮三种状态（常态 / 悬停 / 按下）画出来必须互不相同，按下要下沉；
7. 两套主题的新配色字段齐全，日夜的背景渐变确实不同；
8. 六个界面 × 两套主题整页渲染一遍：不崩、背景不是一块纯色；
9. 菜单面板的最后一项离面板底边留出余量（这是真的踩到过的排版事故）。
"""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                     # noqa: E402
import pytest                                     # noqa: E402

from game import paint, theme                     # noqa: E402
from game.states import GameState                 # noqa: E402
from game.ui import Button, MenuPanel             # noqa: E402

BG = (18, 20, 30)


@pytest.fixture(scope="module", autouse=True)
def boot():
    pygame.init()
    pygame.font.init()
    pygame.display.set_mode((640, 1140))
    yield
    pygame.quit()


def blank(w=200, h=140):
    surface = pygame.Surface((w, h))
    surface.fill(BG)
    return surface


def opaque(surface, x, y):
    """该像素是否被涂过（和纯背景不同）。"""
    return surface.get_at((x, y))[:3] != BG


# ---------------- 1. 竖向渐变 ----------------

def test_vertical_gradient_ends_on_the_two_colors():
    top, bottom = (10, 20, 30), (210, 220, 230)
    image = paint.vertical_gradient((32, 64), top, bottom)
    assert image.get_size() == (32, 64)
    assert image.get_at((0, 0))[:3] == top
    assert image.get_at((31, 63))[:3] == bottom


def test_vertical_gradient_moves_monotonically():
    top, bottom = (0, 0, 0), (255, 255, 255)
    image = paint.vertical_gradient((8, 40), top, bottom)
    values = [image.get_at((4, y))[0] for y in range(40)]
    assert values == sorted(values), values
    assert values[0] < values[len(values) // 2] < values[-1]


def test_vertical_gradient_is_flat_sideways():
    """横向拉满时每一行都是同一个颜色（别把渐变做成了斜的）。"""
    image = paint.vertical_gradient((40, 20), (0, 0, 0), (100, 100, 100))
    for y in range(20):
        row = {image.get_at((x, y))[:3] for x in range(40)}
        assert len(row) == 1, (y, row)


def test_gradient_is_cached():
    size, colors = (16, 24), ((1, 2, 3), (4, 5, 6))
    first = paint.vertical_gradient(size, *colors)
    second = paint.vertical_gradient(size, *colors)
    assert first is second
    other = paint.vertical_gradient(size, (9, 9, 9), (4, 5, 6))
    assert other is not first


def test_edge_fade_goes_from_solid_to_transparent_and_back():
    strip = paint.edge_fade((30, 12), (0, 0, 0), 100)
    assert strip.get_at((0, 0))[3] == 0
    assert strip.get_at((0, 11))[3] == 100
    assert strip.get_at((0, 5))[3] <= strip.get_at((0, 11))[3]
    flipped = paint.edge_fade((30, 12), (0, 0, 0), 100, flip=True)
    assert flipped.get_at((0, 0))[3] == 100
    assert flipped.get_at((0, 11))[3] == 0


# ---------------- 2. 柔光 ----------------

def test_radial_glow_is_brightest_in_the_middle():
    color, alpha = (200, 160, 90), 120
    glow = paint.radial_glow(60, color, alpha)
    center = glow.get_width() // 2
    middle = glow.get_at((center, center))[3]
    ring = glow.get_at((center + 30, center))[3]
    edge = glow.get_at((center, 1))[3]
    # 中心那一像素是「放大后取平均」出来的，允许比目标值略低一点
    assert alpha - 8 <= middle <= alpha, middle
    assert 0 <= edge <= ring <= middle, (edge, ring, middle)


def test_radial_glow_does_not_bleed_black():
    """半透明的像素也必须是柔光自身的颜色，不能混进黑色。"""
    color = (240, 210, 120)
    glow = paint.radial_glow(40, color, 90)
    for x in range(0, glow.get_width(), 3):
        for y in range(0, glow.get_height(), 3):
            pixel = glow.get_at((x, y))
            if pixel[3] > 0:
                assert pixel[:3] == color, (x, y, pixel)


def test_blit_glow_centers_on_the_point():
    surface = blank(120, 120)
    paint.blit_glow(surface, (60, 60), 40, (255, 255, 255), 120)
    assert opaque(surface, 60, 60)
    assert not opaque(surface, 2, 2)


# ---------------- 3. 投影 ----------------

def test_soft_shadow_fades_outward():
    shadow = paint.soft_shadow((60, 40), 12, spread=12, alpha=140, dy=4)
    middle = 12 + 20                       # 本体中线那一行
    alphas = [shadow.get_at((x, middle))[3] for x in range(0, 12)]
    assert alphas == sorted(alphas), alphas
    assert alphas[0] <= 10, alphas[0]
    assert alphas[-1] >= 60, alphas[-1]


def test_soft_shadow_extra_padding_accounts_for_offset():
    """底图要比本体大出四周的模糊量，外加向下偏移的那一截。"""
    shadow = paint.soft_shadow((60, 40), 12, spread=10, dy=8)
    assert shadow.get_size() == (80, 68)


def test_blit_shadow_darkens_around_the_rect():
    """投影是「往四面八方糊出去的一团」，矩形本体那一圈外面必须变暗。

    贴图内部是实心的 —— 调用方随后会在上面画一个不透明的形状把它盖住
    （红心、金币、滑杆钮都是这么用的），所以这里只验四周。
    """
    surface = blank(160, 120)
    rect = pygame.Rect(40, 30, 60, 40)
    paint.blit_shadow(surface, rect, 12, spread=12, alpha=120, dy=6)
    assert opaque(surface, rect.left - 4, rect.centery)
    assert opaque(surface, rect.right + 4, rect.centery)
    assert opaque(surface, rect.centerx, rect.top - 4)
    assert opaque(surface, rect.centerx, rect.bottom + 4)
    assert not opaque(surface, rect.left - 12, rect.top - 12)


def test_card_body_is_not_dirtied_by_its_own_shadow():
    """卡片本体那一块必须是纯填充色，投影不许渗进来。"""
    fill = (100, 160, 240)
    card, offset = paint.card_surface((60, 40), 8, fill,
                                      shadow=(12, 120, (0, 0, 0), 6))
    pad = -offset[0]
    assert card.get_at((pad + 30, pad + 20))[:3] == fill
    # 本体之外、投影之内：是压暗的颜色，不是背景
    outside = card.get_at((2, pad + 20))
    assert outside[3] > 0 and sum(outside[:3]) < sum(fill)


# ---------------- 4. 卡片 ----------------

def test_card_rounds_its_corners_and_keeps_the_body():
    card, offset = paint.card_surface((80, 60), 16, (90, 110, 200),
                                      (40, 50, 120))
    assert offset == (0, 0)
    assert card.get_at((0, 0))[3] == 0            # 圆角被切掉
    assert card.get_at((40, 30))[3] == 255        # 正中是实的


def test_card_gradient_runs_top_to_bottom():
    card, _ = paint.card_surface((60, 80), 6, (200, 200, 200), (20, 20, 20))
    assert card.get_at((30, 5))[0] > card.get_at((30, 75))[0]


def test_card_border_sits_inside_the_shape():
    border = (255, 0, 0)
    card, _ = paint.card_surface((80, 60), 14, (10, 10, 10), (10, 10, 10),
                                 border=border, border_width=2)
    assert card.get_at((40, 1))[:3] == border
    assert card.get_at((40, 30))[:3] == (10, 10, 10)
    assert card.get_at((1, 30))[:3] == border


def test_card_alpha_makes_the_whole_body_translucent():
    card, _ = paint.card_surface((60, 40), 8, (100, 160, 240),
                                 alpha=120)
    assert abs(card.get_at((30, 20))[3] - 120) <= 3


def test_card_shadow_shifts_the_body_by_its_offset():
    card, offset = paint.card_surface((60, 40), 8, (100, 160, 240),
                                      shadow=(12, 120, (0, 0, 0), 6))
    assert offset == (-12, -12)
    assert card.get_size() == (84, 70)
    # 本体落在 offset 处：那里必须是不透明的填充色
    assert card.get_at((12 + 30, 12 + 20))[:3] == (100, 160, 240)


def test_draw_card_lands_on_the_given_rect():
    surface = blank(200, 160)
    rect = pygame.Rect(70, 50, 60, 40)
    paint.draw_card(surface, rect, 8, fill_top=(200, 60, 60),
                    fill_bottom=(200, 60, 60))
    assert surface.get_at(rect.center)[:3] == (200, 60, 60)
    assert not opaque(surface, rect.left - 8, rect.top - 8)


def test_draw_panel_uses_the_theme_card_colors():
    theme.set_theme("night")
    surface = blank(240, 180)
    rect = pygame.Rect(20, 20, 200, 140)
    paint.draw_panel(surface, rect, 18)
    pal = theme.get()
    assert surface.get_at((rect.centerx, rect.centery))[:3] in \
        (pal.card_top, pal.card_bottom) or \
        pal.card_bottom[0] <= surface.get_at((rect.centerx, rect.centery))[0] \
        <= pal.card_top[0]
    assert surface.get_at((rect.centerx, rect.top + 1))[:3] == pal.card_line


# ---------------- 5. 缓存 ----------------

def test_cache_is_bounded():
    for i in range(paint._CACHE_LIMIT + 40):
        paint.vertical_gradient((3, 3 + i % 5), (i % 255, 0, 0),
                                (0, 0, i % 255))
    assert paint.cache_size() <= paint._CACHE_LIMIT


# ---------------- 6. 文字阴影 ----------------

def _rows_used(image):
    """被涂到的行列表。"""
    return [y for y in range(image.get_height())
            for x in range(image.get_width()) if opaque(image, x, y)]


def test_text_shadow_adds_pixels_below_right():
    font = pygame.font.Font(None, 44)
    plain = blank(240, 90)
    shadow = blank(240, 90)
    paint.text_shadow(plain, font, "美", (255, 255, 255), center=(120, 45),
                      alpha=0)
    paint.text_shadow(shadow, font, "美", (255, 255, 255), center=(120, 45),
                      shadow=(255, 0, 0), alpha=160, offset=(2, 3))
    assert max(_rows_used(shadow)) == max(_rows_used(plain)) + 3
    assert min(_rows_used(shadow)) == min(_rows_used(plain))
    # 多出来的那几行里，确实有偏红的投影像素（极淡的过渡像素不算）
    bottom = max(_rows_used(plain))
    reds = [shadow.get_at((x, bottom + 3)) for x in range(240)
            if shadow.get_at((x, bottom + 3))[0] - BG[0] > 20]
    assert reds and all(p[0] > p[2] for p in reds), reds


# ---------------- 7. 按钮三态 ----------------

def _button_image(button, hovered, pressed):
    surface = blank(260, 100)
    button.hovered = hovered
    button.pressed = pressed
    button.draw(surface)
    return surface


def test_button_three_states_look_different():
    font = pygame.font.Font(None, 32)
    button = Button((130, 50), (180, 56), "开始游戏", None, font)
    plain = _button_image(button, False, False)
    hover = _button_image(button, True, False)
    press = _button_image(button, True, True)
    assert pygame.image.tobytes(plain, "RGB") != \
        pygame.image.tobytes(hover, "RGB")
    assert pygame.image.tobytes(hover, "RGB") != \
        pygame.image.tobytes(press, "RGB")


def test_pressed_button_sinks_and_drops_its_shadow():
    font = pygame.font.Font(None, 32)
    button = Button((130, 50), (180, 56), "开始游戏", None, font)
    plain = _button_image(button, False, False)
    press = _button_image(button, True, True)
    top, bottom = button.rect.top, button.rect.bottom
    assert opaque(plain, button.rect.centerx, top + 2)
    # 下沉 2 像素：原顶边那两行在按下后应该已经空了
    assert not opaque(press, button.rect.centerx, top)
    assert opaque(press, button.rect.centerx, top + 4)
    assert bottom > top


def test_ghost_button_is_quieter_than_the_primary_one():
    font = pygame.font.Font(None, 32)
    theme.set_theme("night")
    pal = theme.get()
    primary = _button_image(
        Button((130, 50), (180, 56), "开始游戏", None, font), False, False)
    ghost = _button_image(
        Button((130, 50), (180, 56), "关卡选择", None, font,
               kind="ghost"), False, False)
    at_primary = primary.get_at((130, 50))[:3]
    at_ghost = ghost.get_at((130, 50))[:3]
    assert at_primary == pal.btn_bottom or at_primary[2] > at_ghost[2] + 40
    assert at_ghost[2] < pal.btn_top[2]


# ---------------- 8. 主题字段 ----------------

def test_both_themes_define_every_new_field():
    for name in ("night", "day"):
        pal = theme.set_theme(name)
        for field in ("bg_top", "bg_bottom", "glow", "surface", "surface_line",
                      "board_top", "board_bottom", "board_line", "card_top",
                      "card_bottom", "card_line", "sheen", "btn_top",
                      "btn_bottom", "btn_line", "btn_text", "accent"):
            color = getattr(pal, field)
            assert len(color) == 3, (name, field, color)
            assert all(0 <= c <= 255 for c in color), (name, field, color)
        spread, alpha, color, dy = pal.card_shadow
        assert spread > 0 and 0 < alpha <= 255 and len(color) == 3 and dy >= 0
    theme.set_theme("night")


def test_the_two_themes_really_differ():
    night = theme.set_theme("night")
    day = theme.set_theme("day")
    assert night.bg_top != day.bg_top
    assert night.bg_bottom != day.bg_bottom
    assert sum(night.bg_top) < sum(day.bg_top)          # 夜间更暗
    assert sum(night.btn_bottom) < sum(day.btn_bottom)
    theme.set_theme("night")


# ---------------- 9. 整页渲染 ----------------

@pytest.fixture
def game(tmp_path):
    from main import Game
    instance = Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    yield instance
    theme.set_theme("night")
    pygame.quit()


def _colors_of(game, step=24):
    return {game.canvas.get_at((x, y))[:3]
            for x in range(0, 640, step) for y in range(0, 1140, step)}


@pytest.mark.parametrize("name", ["night", "day"])
def test_every_screen_renders_with_depth(game, name):
    """八个状态 × 两套主题：不崩，而且背景不是一块纯色。"""
    theme.set_theme(name)
    game.start_game()
    for state in (GameState.START, GameState.RULES, GameState.BASIC_SELECT,
                  GameState.LETTER_SELECT, GameState.PLAYING,
                  GameState.LEVEL_CLEAR, GameState.GAME_OVER,
                  GameState.ALL_CLEAR):
        game.state = state
        game._update_view()
        game._draw()
        colors = _colors_of(game)
        assert len(colors) > 6, (name, state, colors)


def test_background_is_a_gradient_in_both_themes(game):
    for name in ("night", "day"):
        theme.set_theme(name)
        game.state = GameState.PLAYING
        game._draw()
        top = game.canvas.get_at((4, 156))[:3]
        bottom = game.canvas.get_at((4, 1018))[:3]
        assert top != bottom, (name, top, bottom)


def test_menu_panel_leaves_room_under_the_last_item(game):
    """菜单项不能顶到面板底边 —— 这是真的踩到过的排版事故。"""
    game.start_game()
    game.open_menu()
    menu = game.menu
    assert menu is not None
    last = menu._item_rect(len(menu.items) - 1)
    assert menu.rect.bottom - last.bottom >= 18, (menu.rect, last)
    assert last.bottom <= menu.rect.bottom

    game.open_settings()
    settings = game.menu
    last = settings._item_rect(len(settings.items) - 1)
    assert settings.rect.bottom - last.bottom >= 18
    assert menu.rect.top >= 0 and menu.rect.bottom <= 1140


def test_menu_panel_hover_highlight_differs(game):
    game.start_game()
    game.open_menu()
    menu = game.menu
    menu.hover_index = -1
    game._draw()
    plain = game.canvas.copy()
    menu.hover_index = 1
    game._draw()
    hover = game.canvas.copy()
    assert pygame.image.tobytes(plain, "RGB") != \
        pygame.image.tobytes(hover, "RGB")


def test_start_screen_layout_keeps_everything_apart(game):
    """开始页排版：标题 → 四个入口按钮 → 进度卡 → 底部提示，互不重叠。"""
    game.state = GameState.START
    game._draw()
    buttons = list(game.start_buttons)
    assert len(buttons) == 4
    for index, button in enumerate(buttons):
        assert button.rect.bottom <= 1140, button.rect
        if index:
            # 上下相邻，且留得出间距
            assert button.rect.top >= buttons[index - 1].rect.bottom + 8, \
                (buttons[index - 1].rect, button.rect)
    stats = pygame.Rect(320 - 214, 846, 428, 196)
    assert buttons[-1].rect.bottom <= stats.top, (buttons[-1].rect, stats)
    assert stats.bottom <= 1140


def test_art_title_is_a_cartoon_sticker_banner(game):
    """标题是拼装出来的卡通贴纸字，而且真的画在按钮上方。

    参照玩家给的截图：奶白字面 + 深色内边 + 浅色外边（三层对比，日夜底色上都清晰），
    前后两个「一」是红 / 蓝胶囊横条，末尾的「箭」换成绿色收尾。
    """
    game.state = GameState.START
    placed = game._draw_start_title((game.canvas.get_width() // 2, 228))
    banner = game._start_title_image()

    # 画在按钮上方，且左右都不顶到屏幕边
    assert placed.bottom < game.start_buttons[0].rect.top - 40, placed
    assert placed.left > 0 and placed.right < game.canvas.get_width(), placed
    # 宽度要占到大半个屏幕（参照图里标题约占 88%）
    assert banner.get_width() > game.canvas.get_width() * 0.7, banner.get_size()

    pixels = [(x, y) for y in range(banner.get_height())
              for x in range(banner.get_width())
              if banner.get_at((x, y))[3] > 200]
    assert len(pixels) > 2000, len(pixels)

    def has(predicate):
        return any(predicate(banner.get_at(pos)) for pos in pixels)

    assert has(lambda c: min(c[:3]) > 230), "缺奶白字面"
    assert has(lambda c: max(c[:3]) < 90), "缺深色内边"
    assert has(lambda c: c[0] > 190 and c[1] < 130 and c[2] < 130), "缺红色横条"
    assert has(lambda c: c[2] > 190 and c[0] < 130 and c[1] < 190), "缺蓝色横条"
    assert has(lambda c: c[1] > 170 and c[0] < 170 and c[2] < 180), "缺绿色收尾"

    ys = [pos[1] for pos in pixels]

    def mean(start, end):
        group = [banner.get_at(pos) for pos in pixels if start <= pos[1] < end]
        return tuple(sum(p[i] for p in group) / len(group) for i in range(3))

    lighter = mean(min(ys), min(ys) + 10)
    darker = mean(max(ys) - 10, max(ys) + 1)
    assert sum(lighter) > sum(darker), (lighter, darker)     # 字面上亮下暗


def big_font(size=40):
    """测试用的粗体字：``game`` fixture 收尾会 ``pygame.quit()``，这里补一次 init。"""
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.SysFont("microsoftyahei,simhei,arial", size, bold=True)


def test_art_bar_is_a_round_ended_capsule():
    """横条是圆头胶囊，不是方块；照样有描边和字面。"""
    bar = paint.art_bar(120, 30, (236, 84, 66), outline=(30, 28, 32),
                        outline_width=5, outline2=(255, 255, 255),
                        outline2_width=3, highlight=(255, 255, 255), lift=2)
    width, height = bar.get_size()
    assert width > 120 and height > 30, bar.get_size()   # 描边撑大一圈

    middle = bar.get_at((width // 2, height // 2))
    assert middle[0] > 190 and middle[1] < 130 and middle[2] < 130, middle

    # 圆头：两端在垂直中间以外应当是空的（方头的话这里会有颜色）
    assert bar.get_at((2, 2))[3] < 60, bar.get_at((2, 2))
    assert bar.get_at((width - 3, height - 3))[3] < 60

    column = [bar.get_at((width // 2, y)) for y in range(height)]
    assert any(max(c[:3]) < 90 and c[3] > 200 for c in column), "缺深色内边"


def test_art_banner_packs_pieces_by_their_ink():
    """拼装按**墨迹**排布：每片四周的描边留白不许变成片间距。"""
    font = big_font(40)
    face = {"top": (255, 252, 240), "bottom": (238, 212, 150)}
    kwargs = dict(outline=(30, 28, 32), outline_width=5,
                  outline2=(255, 255, 255), outline2_width=3)
    pieces = [{"kind": "text", "text": "箭", **face} for _ in range(2)]
    banner = paint.art_banner(font, pieces, gap=6, **kwargs)
    single = paint.art_banner(font, pieces[:1], gap=6, **kwargs)

    # 按墨迹排布：两条正好是「单片墨迹宽 × 2 + gap」。
    # 若改成按整片宽度累加，这里会多出两倍的描边留白（本用例里约 72 px）。
    assert banner.get_width() == single.get_width() * 2 + 6, \
        (banner.get_width(), single.get_width())
    # 画布已经贴着墨迹，不留多余空白
    ink = banner.get_bounding_rect()
    assert ink.width >= banner.get_width() - 4, (ink, banner.get_size())


def test_art_text_second_outline_sits_outside_the_first():
    """双层描边：外层浅色确实在外层，图也比单层的更大。"""
    font = big_font(40)
    base = dict(top=(255, 252, 240), bottom=(238, 212, 150),
                outline=(30, 28, 32), outline_width=5)
    single = paint.art_text(font, "A", **base)
    double = paint.art_text(font, "A", outline2=(255, 255, 255),
                            outline2_width=3, **base)

    assert double.get_width() > single.get_width()
    assert double.get_height() > single.get_height()

    def near_white(surface):
        """纯白像素数：字面最亮处也只到 240，阈值取 248 能把外圈单独挑出来。"""
        return sum(1 for y in range(surface.get_height())
                   for x in range(surface.get_width())
                   if surface.get_at((x, y))[3] > 200
                   and min(surface.get_at((x, y))[:3]) > 248)

    # 外圈 3 px 宽，缩回后只有环心那一列还是纯白，40 号「A」大约 137 个像素
    assert near_white(single) == 0, near_white(single)
    assert near_white(double) >= 100, near_white(double)


def test_art_text_lift_thickens_the_bottom_edge():
    """``lift`` 把描边往下推：底部那圈边明显比顶部厚，字就「浮」起来了。

    用「口」量：取中间一列，比较「字面顶边到墨迹顶边」与「字面底边到墨迹底边」。
    """
    font = big_font(80)
    base = dict(top=(255, 252, 240), bottom=(238, 212, 150),
                outline=(30, 28, 32), outline_width=8)

    def edges(surface):
        x = surface.get_width() // 2
        column = [surface.get_at((x, y)) for y in range(surface.get_height())]
        solid = [y for y, c in enumerate(column) if c[3] > 140]
        face = [y for y, c in enumerate(column)
                if c[3] > 200 and min(c[:3]) > 200]
        assert solid and face, "中间列上找不到墨迹或字面"
        return face[0] - solid[0], solid[-1] - face[-1]

    flat = edges(paint.art_text(font, "口", **base))
    lifted = edges(paint.art_text(font, "口", lift=6, **base))
    assert lifted[1] > lifted[0], lifted              # 底部比顶部厚
    assert lifted[1] > flat[1], (flat, lifted)        # 比不加 lift 时更厚


def test_redraw_is_not_pathologically_slow(game):
    """美化加了一堆缓存贴图，别把整帧拖垮（阈值放得很宽，只抓明显回退）。"""
    game.start_game()
    game.level_index = 11
    game._load_level(game.levels[11])
    game.state = GameState.PLAYING
    game._draw()
    frames = 20
    start = time.perf_counter()
    for _ in range(frames):
        game._draw()
    per_frame = (time.perf_counter() - start) / frames
    assert per_frame < 0.04, "%.1f ms/帧" % (per_frame * 1000)


def test_menu_panel_still_returns_the_click(game):
    """排版改了之后，点击命中不能跟着坏掉。"""
    calls = []
    panel = MenuPanel((320, 500), (380, 412), "菜单",
                      [("甲", lambda: calls.append("甲")),
                       ("乙", lambda: calls.append("乙"))],
                      (pygame.font.Font(None, 40),
                       pygame.font.Font(None, 30)))
    panel.hover_index = 1
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                               pos=panel._item_rect(1).center)
    assert panel.handle_event(event) is True
    assert calls == ["乙"]
