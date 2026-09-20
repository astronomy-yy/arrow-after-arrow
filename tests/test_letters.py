"""字母玩法与开始页四个入口的测试。

对应需求：「开始界面四个按钮（规则介绍 / 基础玩法 / 字母玩法 / 随机关卡），
标题一箭又一箭是艺术字，字母玩法 26 关分别是 26 个字母形状」。

分成四块：

1. 字模与遮罩（game/letters.py）：26 个字母都在、点阵尺寸对、栅格化后
   格子数守恒、留白对、八连通、能塞进棋盘；
2. 26 关关卡数据（game/level_letters.py）：id / letter / 造型对得上，
   每关都可解、有阻挡、铺得满，难度按字母顺序爬升；
3. 界面流转：开始页四个入口各自进对的状态、规则页返回、字母选关点得开；
4. 规则页文案与快捷键表：有 U/H/A/G 等功能说明，**不再有按 N 开随机关卡**。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame      # noqa: E402
import pytest      # noqa: E402

import main        # noqa: E402
from game import generator, letters, theme    # noqa: E402
from game.board import Board                  # noqa: E402
from game.level_letters import LEVELS as LETTER_LEVELS   # noqa: E402
from game.shapes import cells_of, is_connected, level_cells  # noqa: E402
from game.solver import solve                 # noqa: E402
from game.states import GameState             # noqa: E402


# --------------------------------------------------------------------------
# 1. 字模与遮罩
# --------------------------------------------------------------------------

def test_all_26_letters_have_a_pattern():
    assert len(letters.LETTER_PATTERNS) == 26
    assert letters.LETTERS == tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert letters.is_letter("A") and letters.is_letter("z")
    assert not letters.is_letter("1") and not letters.is_letter(None)


@pytest.mark.parametrize("letter", list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
def test_pattern_is_a_5x7_bitmap(letter):
    rows = letters.pattern(letter)
    assert len(rows) == letters.PATTERN_ROWS
    for line in rows:
        assert len(line) == letters.PATTERN_COLS
        assert set(line) <= {"#", "."}
    assert len(letters.on_pixels(letter)) >= 8, letter
    assert letters.pattern(letter.lower()) == rows


@pytest.mark.parametrize("letter", list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
def test_letter_mask_is_connected_and_fits(letter):
    """每个字母的遮罩都是**一整块**（八连通），而且真的落在棋盘里。"""
    rows, cols = letters.board_size()
    cells = letters.letter_cells(rows, cols, letter)
    assert cells, letter
    assert is_connected(cells, diagonal=True), letter
    assert all(0 <= r < rows and 0 <= c < cols for (r, c) in cells)
    # 每格都该在字模展开出来的位置上，格子数 = 笔画像素数 × scale²
    scale = letters.DEFAULT_SCALE
    assert len(cells) == len(letters.on_pixels(letter)) * scale * scale


@pytest.mark.parametrize("letter", ["A", "I", "M", "W", "Z"])
def test_letter_mask_keeps_a_margin(letter):
    """四周留白：最外圈不许有笔画，不然线段会贴着棋盘边缘。"""
    rows, cols = letters.board_size()
    cells = letters.letter_cells(rows, cols, letter)
    assert not any(r == 0 or r == rows - 1 for (r, c) in cells)
    assert not any(c == 0 or c == cols - 1 for (r, c) in cells)


def test_board_size_is_rows_then_cols():
    """board_size 的返回顺序是 (行, 列) —— 这里踩过坑，钉死它。"""
    rows, cols = letters.board_size(2, 1)
    assert (rows, cols) == (16, 12)
    rows, cols = letters.board_size(3, 0)
    assert (rows, cols) == (21, 15)


def test_default_board_size_is_23x17():
    """默认棋盘密度钉在这里：scale=3、margin=1 → 23 行 × 17 列。

    棋盘整体加密过一轮（16×12 → 23×17，格子数 192 → 391）。把数字写死是
    为了下次动 scale 时必须是有意的：它同时影响 26 关的生成脚本与关卡数据。
    """
    assert letters.DEFAULT_SCALE == 3
    assert letters.board_size() == (23, 17)
    assert letters.board_size()[0] * letters.board_size()[1] == 391


def test_cells_of_accepts_letter_shape():
    rows, cols = letters.board_size()
    mask = cells_of(rows, cols, "letter", "B")
    assert mask == letters.letter_cells(rows, cols, "B")
    # 缺字母时退化成整块矩形，不崩
    assert len(cells_of(rows, cols, "letter")) == rows * cols


def test_is_connected_diagonal_option():
    """对角相接的两个格：四连通判否、八连通判是。"""
    cells = {(0, 0), (1, 1)}
    assert not is_connected(cells)
    assert is_connected(cells, diagonal=True)
    assert is_connected({(0, 0)}, diagonal=True) is True
    assert is_connected(set()) is False


def test_level_cells_uses_the_letter():
    rows, cols = letters.board_size()
    level = {"rows": rows, "cols": cols, "shape": "letter", "letter": "C"}
    assert level_cells(level) == letters.letter_cells(rows, cols, "C")
    plain = {"rows": 4, "cols": 5, "shape": "rect"}
    assert len(level_cells(plain)) == 20


# --------------------------------------------------------------------------
# 2. 26 关关卡数据
# --------------------------------------------------------------------------

def test_letter_levels_cover_the_alphabet():
    assert len(LETTER_LEVELS) == 26
    for index, level in enumerate(LETTER_LEVELS):
        assert level["id"] == letters.LETTERS[index]
        assert level["letter"] == letters.LETTERS[index]
        assert level["shape"] == "letter"
        assert level["mistakes"] >= 1
        assert level["time_limit"] > 0
        assert (level["rows"], level["cols"]) == letters.board_size()


@pytest.mark.parametrize("level", LETTER_LEVELS, ids=lambda x: x["letter"])
def test_letter_level_is_solvable_and_blocked(level):
    """每关都要：能通关、有阻挡、铺得够满、箭数不至于三下点完。"""
    stats = generator.board_stats(level)
    assert stats["arrows"] >= 5, level["letter"]
    assert generator.fill_ratio(level) >= 0.9, level["letter"]
    assert stats["free_ratio"] > 0, level["letter"]
    assert stats["blocked_ratio"] >= 0.35, level["letter"]

    # solution 走一遍：每一步都真的飞得出去
    board = Board(level)
    by_id = {arrow.id: arrow for arrow in board.arrows}
    for arrow_id in level["solution"]:
        arrow = by_id[arrow_id]
        assert board.can_fly_arrow(arrow), (level["letter"], arrow_id)
        board.remove_arrow(arrow)
    assert board.remaining == 0

    # 求解器（拓扑排序）也能独立解出来
    assert solve(Board(level)) is not None, level["letter"]


def test_letter_difficulty_ramps_up():
    """A 一带开局能直接飞的箭多，Z 一带明显更少。"""
    def free_ratio(levels):
        return sum(generator.board_stats(level)["free_ratio"]
                   for level in levels) / len(levels)

    head = free_ratio(LETTER_LEVELS[:6])
    tail = free_ratio(LETTER_LEVELS[-6:])
    assert head > tail + 0.05, (head, tail)


def test_letter_levels_do_not_touch_the_basic_progress_keys():
    """字母关的 id 是字符串，不会和基础关卡的 1~12 撞进同一个存档键。"""
    ids = [level["id"] for level in LETTER_LEVELS]
    assert all(isinstance(level_id, str) for level_id in ids)
    assert not set(ids) & {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}


# --------------------------------------------------------------------------
# 3. 界面流转
# --------------------------------------------------------------------------

@pytest.fixture
def game(tmp_path):
    instance = main.Game(save_path=str(tmp_path / "save.json"))
    theme.set_theme("night")
    instance._update_view()
    yield instance
    theme.set_theme("night")
    pygame.quit()


def _click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_start_screen_has_five_entries(game):
    assert game.state == GameState.START
    labels = [b.text for b in game.start_buttons]
    assert labels == ["规则介绍", "入门玩法", "基础玩法", "字母玩法", "随机关卡"]
    for button in game.start_buttons:
        assert button.icon is not None


def test_tutorial_button_opens_a_level_select_screen(game):
    """「入门玩法」给的是一页选关，不是直接把人丢进第 1 关。"""
    game.state = GameState.START
    game.tutorial_button.handle_event(_click(game.tutorial_button.rect.center))
    assert game.state == GameState.TUTORIAL_SELECT
    assert game.track == "tutorial"
    assert len(game.tutorial_levels) == 3

    # 三关都能点，关号按顺序是 1 / 2 / 3
    rects = game._tutorial_rects()
    assert len(rects) == 3
    for index, rect in enumerate(rects):
        game.state = GameState.TUTORIAL_SELECT
        game._dispatch_event(_click(rect.center))
        assert game.state == GameState.PLAYING
        assert game.level_number == index + 1, (index, game.level_number)


def test_tutorial_levels_are_numbered_one_two_three(game):
    """入门关显示 1/2/3；存档用的 id 必须跟基础关、字母关都不撞。"""
    game.open_tutorial_select()
    shown = [game._level_display_number(i) for i in range(3)]
    assert shown == [1, 2, 3], shown

    ids = [level["id"] for level in main.TUTORIAL_LEVELS]
    others = {level["id"] for level in main.LEVELS} | \
        {level["id"] for level in LETTER_LEVELS}
    assert not (set(ids) & others), (ids, sorted(others))


def click_cell(game, row, col):
    """点棋盘上一格：按下 + 抬起成对发（只发按下不会触发点击）。"""
    pos = game._grid_center(row, col)
    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        game._dispatch_event(
            pygame.event.Event(kind, {"pos": pos, "button": 1}))


def settle(game, limit=3000):
    """推进主循环，直到飞出 / 弹回动画都播完。"""
    steps = 0
    while (game.flying or game.blocked) and steps < limit:
        game._update(1.0 / 60.0)
        steps += 1
    assert steps < limit, "动画没有在合理步数内结束"


def test_tutorial_playthrough_runs_1_2_3_and_returns_to_its_select(game):
    """入门玩法整条链路：选关页 → 第 1 关 → 通关 → 下一关 → 靶心回选关页。"""
    game.state = GameState.START
    game.tutorial_button.handle_event(_click(game.tutorial_button.rect.center))
    assert game.state == GameState.TUTORIAL_SELECT

    # 点第一张卡进第 1 关，关号是 1
    first = game._tutorial_rects()[0]
    game._dispatch_event(_click(first.center))
    assert game.state == GameState.PLAYING
    assert game.level_number == 1

    # 按 solution 点完应当通关；进度只落在入门关自己身上
    level = game.tutorial_levels[0]
    for arrow_id in level["solution"]:
        arrow = next(a for a in game.board.arrows if a.id == arrow_id)
        click_cell(game, *arrow.head)
        settle(game)
    game._update(1.0 / 60.0)
    assert game.state == GameState.LEVEL_CLEAR
    assert game.save.is_cleared("T1") is True
    assert game.save.is_cleared(1) is False      # 不能串到基础第 1 关

    # 下一关 -> 关号 2（按列表下标排，不是 101/102）
    game.next_level()
    assert game.level_number == 2
    assert game.state == GameState.PLAYING

    # 靶心回的是入门选关页 —— 不是开始页，也不是基础选关页
    game.leave_level()
    assert game.state == GameState.TUTORIAL_SELECT

    # Esc 从选关页回开始页
    game._handle_key(pygame.K_ESCAPE)
    assert game.state == GameState.START


def test_tutorial_levels_have_plenty_of_arrows():
    """入门关是拿来练手的，箭太少点两下就没了 —— 每关至少 8 支。"""
    assert len(main.TUTORIAL_LEVELS) == 3
    for level in main.TUTORIAL_LEVELS:
        assert len(level["arrows"]) >= 8, (level["id"], len(level["arrows"]))
        # 全是单格箭，而且顺序解真的走得通
        assert all(len(arrow["cells"]) == 1 for arrow in level["arrows"])
        assert generator.verify_solution(level) is True


def test_rules_button_opens_and_returns(game):
    game.state = GameState.START
    game.rules_button.handle_event(_click(game.rules_button.rect.center))
    assert game.state == GameState.RULES

    # 规则页的返回按钮
    game.rules_home_button.handle_event(_click(
        game.rules_home_button.rect.center))
    assert game.state == GameState.START

    # Esc 也能返回
    game.open_rules()
    assert game.state == GameState.RULES
    game._handle_key(pygame.K_ESCAPE)
    assert game.state == GameState.START


def test_basic_button_opens_the_12_level_page(game):
    game.basic_button.handle_event(_click(game.basic_button.rect.center))
    assert game.state == GameState.BASIC_SELECT
    assert game.track == "basic"
    assert game.levels is game.basic_levels
    assert len(game.levels) == 12
    assert len(game._level_rects()) == 12


def test_letter_button_opens_the_26_letter_page(game):
    game.letter_button.handle_event(_click(game.letter_button.rect.center))
    assert game.state == GameState.LETTER_SELECT
    assert game.track == "letter"
    assert game.levels is game.letter_levels
    rects = game._letter_rects()
    assert len(rects) == 26
    # 格子之间不重叠，而且都在画面里
    for i, rect in enumerate(rects):
        assert rect.left >= 0 and rect.right <= 640
        assert rect.top >= 0 and rect.bottom <= 1140
        for other in rects[i + 1:]:
            assert not rect.colliderect(other)


def test_letter_grid_click_opens_that_letter(game):
    game.open_letter_select()
    rects = game._letter_rects()
    for index in (0, 7, 25):
        game.open_letter_select()
        game._dispatch_event(_click(rects[index].center))
        assert game.state == GameState.PLAYING
        expected = game.letter_levels[index]["letter"]
        assert game.current_level["letter"] == expected
        assert game.board.total >= 5
    assert [level["letter"] for level in game.letter_levels[:3]] == ["A", "B",
                                                                     "C"]


def test_letter_clear_is_recorded_in_save(game):
    game.open_letter_select()
    game.select_level(0)
    assert game.current_level["id"] == "A"
    game._finish_level()
    assert game.save.is_cleared("A")
    assert game.save.stars_of("A") >= 1
    assert game.state in (GameState.LEVEL_CLEAR, GameState.ALL_CLEAR)


def test_random_button_starts_a_random_level(game):
    game.random_button.handle_event(_click(game.random_button.rect.center))
    assert game.state == GameState.PLAYING
    assert game.current_level.get("random") is True
    assert game.current_level not in game.basic_levels
    assert game.board.total >= 3


def test_random_level_is_not_written_to_save(game):
    """随机关卡是现场生成的，通关也不该占存档里的关卡 id。"""
    game.play_random()
    level_id = game.current_level["id"]
    game._finish_level()
    assert level_id not in game.save.data["cleared"]


def test_n_key_is_no_longer_bound(game):
    """随机关卡挪到开始页的按钮上了，N 键不该再换关。"""
    game.start_game()
    before = game.current_level
    game._handle_key(pygame.K_n)
    assert game.current_level is before
    assert game.state == GameState.PLAYING
    assert game.current_level is game.basic_levels[0]


def test_menu_jumps_to_the_matching_select_page(game):
    game.open_letter_select()
    game.select_level(0)
    game.open_menu()
    game.open_select()
    assert game.state == GameState.LETTER_SELECT

    game.open_basic_select()
    game.select_level(0)
    game.open_menu()
    game.open_select()
    assert game.state == GameState.BASIC_SELECT


def test_top_bar_target_button_returns_to_the_matching_select_page(game):
    """顶栏那枚靶心（圆圈）按钮：点一下要回到**当前玩法**的选关页。

    回归用例。这枚按钮原来接的是 ``open_level_select`` —— 一个在类定义时就
    绑死到 ``open_basic_select`` 的别名，于是玩字母关时点它也会掉进基础选关页。
    这里走完整链路（点击 → HUD → IconButton → 回调），不只测那个方法。
    """
    button = game.hud.select_button

    game.open_letter_select()
    game.select_level(letters.LETTERS.index("M"))
    assert game.state == GameState.PLAYING
    game._dispatch_event(_click(button.rect.center))
    assert game.state == GameState.LETTER_SELECT
    assert game.track == "letter"
    assert game.levels is game.letter_levels

    game.open_basic_select()
    game.select_level(2)
    game._dispatch_event(_click(button.rect.center))
    assert game.state == GameState.BASIC_SELECT
    assert game.track == "basic"
    assert game.levels is game.basic_levels


def test_top_bar_target_button_from_a_random_level_goes_home(game):
    """随机关卡是从开始页进的，靶心按钮就该回开始页。

    回归用例。之前这里是「按 track 分派」：随机关卡借用了 basic 这条线，
    于是被当成基础关塞进基础选关页 —— 玩家点圆圈想回开始页，却掉进一个
    自己从没进过的界面。现在按「来路」分派，三条线各回各的出发地。
    """
    game.play_random()
    assert game.state == GameState.PLAYING
    assert game.play_origin == GameState.START
    game._dispatch_event(_click(game.hud.select_button.rect.center))
    assert game.state == GameState.START


def test_a_random_level_does_not_leak_its_origin_to_the_next_basic_level(game):
    """玩过随机关之后再从基础选关页进关，靶心要回基础选关页而不是开始页。"""
    game.play_random()
    game._dispatch_event(_click(game.hud.select_button.rect.center))
    assert game.state == GameState.START

    game.open_basic_select()
    game.select_level(2)
    assert game.play_origin == GameState.BASIC_SELECT
    game._dispatch_event(_click(game.hud.select_button.rect.center))
    assert game.state == GameState.BASIC_SELECT


def test_leaving_a_level_returns_to_where_the_player_came_from(game):
    """三条进门路线各自回对的屏：基础 → 基础选关，字母 → 字母选关，随机 → 开始页。"""
    game.open_basic_select()
    game.select_level(0)
    game.leave_level()
    assert game.state == GameState.BASIC_SELECT

    game.open_letter_select()
    game.select_level(0)
    game.leave_level()
    assert game.state == GameState.LETTER_SELECT

    game.play_random()
    game.leave_level()
    assert game.state == GameState.START


def test_the_basic_only_alias_is_gone(game):
    """``open_level_select`` 这个别名本身就是那个 bug 的来源，不该再存在。

    它是在类定义时求值的，永远指向 open_basic_select；只要有人再拿它去接
    按钮，就会重新长出「玩字母关却跳基础选关」的毛病。
    """
    assert not hasattr(main.Game, "open_level_select")


# --------------------------------------------------------------------------
# 4. 规则页内容
# --------------------------------------------------------------------------

def test_shortcut_table_covers_the_keys_and_drops_n():
    keys = [item[0] for row in main.KEY_HINTS for item in row if item]
    assert {"U", "H", "A", "G", "Esc", "滚轮", "拖动", "方向键", "0"} \
        <= set(keys)
    assert "N" not in {key.upper() for key in keys}


def test_rules_page_renders_in_both_themes(game):
    game.open_rules()
    for name in ("night", "day"):
        theme.set_theme(name)
        game._draw()
        colors = {game.canvas.get_at((x, y))[:3]
                  for x in range(0, 640, 24) for y in range(0, 1140, 24)}
        assert len(colors) > 6, name


def test_letter_level_renders_a_big_letter_shape(game):
    """字母关的盘面：笔画格上确实画了东西，四角是空的。"""
    game.open_letter_select()
    game.select_level(letters.LETTERS.index("O"))
    game.state = GameState.PLAYING
    game._draw()
    mask = level_cells(game.current_level)
    painted = 0
    for (r, c) in mask:
        rect = game._cell_rect(r, c)
        colors = {game.canvas.get_at((rect.centerx + dx, rect.centery + dy))[:3]
                  for dx in (-6, 0, 6) for dy in (-6, 0, 6)}
        if len(colors) > 1:
            painted += 1
    assert painted >= len(mask) * 0.5, (painted, len(mask))
