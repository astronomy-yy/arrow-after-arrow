"""一箭又一箭（Arrow After Arrow）游戏入口。

玩法与界面照着参考图 / 录屏复刻：
- 棋盘上摆满彩色线段箭，点击后整条线段沿自身轨迹滑出、再顺箭头方向飞出；
- 被别的线段挡住则变红扣心；
- 顶栏：设置、日夜拨杆、关卡号、红心、倒计时，右侧手柄 / 菜单 / 关卡选择；
- 底栏：金币提示、缩放滑杆、辅助线开关。

扩展功能：AI 求解、提示、撤销、倒计时星级、关卡选择、随机关卡、存档、音效。
快捷键：U 撤销 / H 提示 / A 自动求解 / G 辅助线 / N 随机关卡 / Esc 菜单与返回。
"""

import sys

import pygame

from game import audio, icons, theme
from game.animations import (
    TOAST_DURATION,
    BlockedFeedback,
    FlyingSegment,
    HintPulse,
)
from game.arrow import DIRECTION_DELTA, draw_segment, lighten, segment_width
from game.board import Board
from game.generator import random_level as make_random_level
from game.hud import Hud
from game.level import LEVELS
from game.settings import (
    BOARD_MARGIN_X,
    BOARD_MARGIN_Y,
    BOTTOM_BAR_HEIGHT,
    CELL_GAP,
    COIN_REWARD_CLEAR,
    COIN_START,
    DEFAULT_WINDOW_H,
    DEFAULT_WINDOW_W,
    FONT_NAME,
    FPS,
    HINT_COST,
    MAX_CELL_SIZE,
    MIN_WINDOW_H,
    MIN_WINDOW_W,
    SCREEN_RESERVE_H,
    SCREEN_RESERVE_W,
    SKIP_COST,
    TITLE,
    TOP_BAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    WRONG_COLOR,
    ZOOM_IN_CENTER,
    ZOOM_OUT_CENTER,
)
from game.shapes import cells_of
from game.solver import solve
from game.states import GameState
from game.storage import Save
from game.ui import Button, IconButton, MenuPanel

MOUSE_EVENTS = (
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
)

ZOOM_MIN, ZOOM_MAX = 0.65, 1.35
AUTO_STEP_INTERVAL = 0.30       # AI 自动求解时每隔多久点一支箭
STAR_TABLE = {0: 3, 1: 2, 2: 2}


def desktop_size():
    """pygame 眼里的桌面尺寸，拿不到时返回 None。

    注意进程不是 DPI 感知的，在缩放 200% 的屏幕上这里拿到的是**逻辑**尺寸
    （比如 2880x1800 的屏只报 1440x900）。无窗口的 dummy 驱动会谎报
    1024x768，所以直接返回 None，让调用方走默认值。
    """
    try:
        if pygame.display.get_driver() == "dummy":
            return None
        sizes = pygame.display.get_desktop_sizes()
    except pygame.error:                      # pragma: no cover - 极端环境
        return None
    if not sizes:
        return None
    width, height = sizes[0]
    if width < 320 or height < 240:           # 明显是假数据
        return None
    return width, height


def usable_window_cap(size):
    """窗口尺寸的上限：桌面尺寸减去标题栏 / 任务栏的余量。"""
    width, height = size
    return max(200, width - SCREEN_RESERVE_W), max(200, height - SCREEN_RESERVE_H)


def fit_to_screen(width, height, size):
    """把期望的窗口尺寸等比收敛到屏幕放得下，只缩小不放大。

    窗口一旦高过桌面，Windows 会把它垂直居中，标题栏跑到屏幕上方、底边跑到
    屏幕下方，用户既抓不到边框缩放、也抓不到标题栏拖动 —— 这正是「窗口无法
    调整大小、也拖不动」的成因。
    """
    cap_w, cap_h = usable_window_cap(size)
    scale = min(1.0, cap_w / width, cap_h / height)
    return max(1, round(width * scale)), max(1, round(height * scale))


class HudInfo:
    """交给 Hud 绘制的一组只读数据。"""

    def __init__(self, game):
        self.level_number = game.level_number
        self.hearts = game.board.mistakes
        self.max_hearts = game.board.max_mistakes
        self.time_left = game.time_left
        self.coins = game.coins
        self.guide = game.guide_on
        self.toast = game.toast_text
        self.toast_ratio = game._toast_ratio()


class Game:
    """游戏主控制器：状态、关卡、动画与主循环。"""

    def __init__(self, save_path=None):
        pygame.init()
        # 窗口必须先收敛到屏幕放得下：最小尺寸也要跟着收敛，
        # 否则「最小尺寸」本身就能把边框顶到屏幕外。
        desktop = desktop_size()
        if desktop is None:
            self.min_window = (MIN_WINDOW_W, MIN_WINDOW_H)
            start_size = (DEFAULT_WINDOW_W, DEFAULT_WINDOW_H)
        else:
            cap_w, cap_h = usable_window_cap(desktop)
            self.min_window = (min(MIN_WINDOW_W, cap_w),
                               min(MIN_WINDOW_H, cap_h))
            start_size = fit_to_screen(DEFAULT_WINDOW_W, DEFAULT_WINDOW_H,
                                       desktop)
        self.screen = pygame.display.set_mode(start_size, pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.canvas = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.view_scale = 1.0
        self.view_rect = pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self._update_view()

        self.font_title = pygame.font.SysFont(FONT_NAME, 54, bold=True)
        self.font_big = pygame.font.SysFont(FONT_NAME, 31, bold=True)
        self.font_num = pygame.font.SysFont(FONT_NAME, 34, bold=True)
        self.font_normal = pygame.font.SysFont(FONT_NAME, 23)
        self.font_small = pygame.font.SysFont(FONT_NAME, 18)

        # ---- 存档与设置 ----
        # save_path 只给截图 / 测试脚本用，正式运行一律走默认存档位置
        self.save = Save(save_path) if save_path else Save()
        theme.set_theme(self.save.data["theme"])
        audio.init()
        self.sound_on = audio.set_enabled(self.save.data["sound"])
        self.guide_on = bool(self.save.data["guide"])
        self.coins = self.save.data.get("coins", COIN_START)

        # ---- 关卡 ----
        self.levels = list(LEVELS)
        self.level_index = 0
        self.level_number = 1
        self.current_level = self.levels[0]
        self.board = Board(self.current_level)
        self.random_counter = len(self.levels)

        # ---- 玩法状态 ----
        self.state = GameState.START
        self.time_left = float(self.current_level.get("time_limit", 240))
        self.hints_used = 0
        self.undos_used = 0
        self.stars = 0
        self.auto_queue = []
        self.auto_timer = 0.0

        # ---- 动画 / 交互 ----
        self.flying = []
        self.blocked = []
        self.hint_pulse = None
        self.hint_arrow_id = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.hover_arrow = None
        self.menu = None
        self.zoom = 1.0

        # 棋盘几何
        self.cell_size = 34
        self.cell_gap = 4
        self.board_x = self.board_y = 0
        self.board_pixel_w = self.board_pixel_h = 0
        self._compute_geometry()

        self._build_widgets()

    # ---------------- 控件 ----------------
    def _build_widgets(self):
        cx = WINDOW_WIDTH // 2
        self.hud = Hud(
            (self.font_num, self.font_normal, self.font_small),
            {
                "settings": self.open_settings,
                "theme": self.on_theme_change,
                "skip": self.skip_level,
                "menu": self.open_menu,
                "select": self.open_level_select,
                "hint": self.use_hint,
                "guide": self.toggle_guide,
                "zoom": self.on_zoom_slider,
                "zoom_out": lambda: self.nudge_zoom(-0.1),
                "zoom_in": lambda: self.nudge_zoom(0.1),
            },
        )

        self.hud.zoom_slider.value = (1.0 - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)

        self.start_button = Button((cx, 720), (240, 66), "开始游戏",
                                   self.start_game, self.font_big)
        self.select_from_start = Button((cx, 810), (240, 54), "关卡选择",
                                        self.open_level_select,
                                        self.font_normal)
        self.next_button = Button((cx - 128, 700), (200, 56), "下一关",
                                  self.next_level, self.font_normal)
        self.retry_button = Button((cx - 128, 700), (216, 56), "重新开始",
                                   self.restart_level, self.font_normal)
        self.home_button = Button((cx + 128, 700), (176, 56), "返回首页",
                                  self.back_home, self.font_normal)
        self.select_home_button = Button((cx, 640), (200, 54), "返回",
                                         self.back_home, self.font_normal)
        self.back_button = IconButton(
            (54, 54), 50, icons.arrow_left, self.back_home, outlined=True,
            radius=14)

    # ---------------- 窗口缩放 ----------------
    def _update_view(self):
        # SDL2 在窗口尺寸变化时会自动换掉 display surface，手上这份引用
        # 可能已经不是最新的，取一次为准。
        self.screen = pygame.display.get_surface() or self.screen
        win_w, win_h = self.screen.get_size()
        self.view_scale = min(win_w / WINDOW_WIDTH, win_h / WINDOW_HEIGHT)
        vw = max(1, int(WINDOW_WIDTH * self.view_scale))
        vh = max(1, int(WINDOW_HEIGHT * self.view_scale))
        self.view_rect = pygame.Rect((win_w - vw) // 2, (win_h - vh) // 2,
                                     vw, vh)

    def _resize(self, w, h):
        """窗口尺寸变了：重算视图。

        真实窗口下 SDL2 会把 display surface 自动换成新尺寸，所以这里通常
        一次 set_mode 都不用调 —— 关键是别在拖拽过程中反复重建窗口，否则会
        打断 Windows 的模态拖拽循环，表现就是「窗口拖不动」。
        不自动换 surface 的环境（dummy 驱动）才需要补一次。
        """
        min_w, min_h = self.min_window
        w, h = max(w, min_w), max(h, min_h)
        if self.screen.get_size() != (w, h):
            self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        self._update_view()

    def _to_world(self, pos):
        return ((pos[0] - self.view_rect.x) / self.view_scale,
                (pos[1] - self.view_rect.y) / self.view_scale)

    # ---------------- 棋盘几何 ----------------
    def _compute_geometry(self):
        avail_w = WINDOW_WIDTH - BOARD_MARGIN_X * 2
        avail_h = (WINDOW_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT
                   - BOARD_MARGIN_Y * 2)
        cols, rows = self.board.cols, self.board.rows
        # 先按「不留缝」估一个格子边长，再按比例抽出缝隙
        cell = min(avail_w / cols, avail_h / rows)
        gap = max(2, round(cell * 0.13))
        cell = min((avail_w - gap * (cols - 1)) / cols,
                   (avail_h - gap * (rows - 1)) / rows)
        cell = min(cell, MAX_CELL_SIZE)
        self.cell_size = max(6, int(cell * self.zoom))
        self.cell_gap = max(1, int(gap * self.zoom))
        self.board_pixel_w = cols * self.cell_size + (cols - 1) * self.cell_gap
        self.board_pixel_h = rows * self.cell_size + (rows - 1) * self.cell_gap
        self.board_x = (WINDOW_WIDTH - self.board_pixel_w) // 2
        self.board_y = TOP_BAR_HEIGHT + max(
            BOARD_MARGIN_Y,
            (WINDOW_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT
             - self.board_pixel_h) // 2)

    def _cell_rect(self, r, c):
        x = self.board_x + c * (self.cell_size + self.cell_gap)
        y = self.board_y + r * (self.cell_size + self.cell_gap)
        return pygame.Rect(x, y, self.cell_size, self.cell_size)

    def _grid_center(self, r, c):
        x = (self.board_x + c * (self.cell_size + self.cell_gap)
             + self.cell_size // 2)
        y = (self.board_y + r * (self.cell_size + self.cell_gap)
             + self.cell_size // 2)
        return x, y

    def _board_rect(self):
        return pygame.Rect(self.board_x - 6, self.board_y - 6,
                           self.board_pixel_w + 12, self.board_pixel_h + 12)

    def _cell_at(self, pos):
        x, y = pos
        if not (self.board_x - 4 <= x <= self.board_x + self.board_pixel_w + 4
                and self.board_y - 4 <= y
                <= self.board_y + self.board_pixel_h + 4):
            return None
        pitch = self.cell_size + self.cell_gap
        c = int((x - self.board_x) // pitch)
        r = int((y - self.board_y) // pitch)
        if 0 <= r < self.board.rows and 0 <= c < self.board.cols:
            if self._cell_rect(r, c).collidepoint(pos):
                return r, c
        return None

    def _mask_cells(self):
        return cells_of(self.board.rows, self.board.cols,
                        self.current_level.get("shape", "rect"))

    # ---------------- 状态切换 ----------------
    def start_game(self):
        self.level_index = 0
        self.level_number = self.levels[0].get("id", 1)
        self._load_level(self.levels[0])
        self.state = GameState.PLAYING

    def next_level(self):
        if self.level_index + 1 < len(self.levels):
            self.level_index += 1
            self.level_number = self.levels[self.level_index].get(
                "id", self.level_index + 1)
            self._load_level(self.levels[self.level_index])
            self.state = GameState.PLAYING
        else:
            self.state = GameState.ALL_CLEAR

    def restart_level(self):
        self.board.reset()
        self._clear_effects()
        self.time_left = float(self.current_level.get("time_limit", 240))
        self.hints_used = 0
        self.undos_used = 0
        self.auto_queue = []
        self._compute_geometry()
        self.state = GameState.PLAYING

    def back_home(self):
        self._clear_effects()
        self.menu = None
        self.save.flush()
        self.state = GameState.START

    def open_level_select(self):
        self.menu = None
        self._clear_effects()
        self.state = GameState.LEVEL_SELECT

    def select_level(self, index):
        self.level_index = index
        self.level_number = self.levels[index].get("id", index + 1)
        self._load_level(self.levels[index])
        self.state = GameState.PLAYING

    def _load_level(self, level):
        self.current_level = level
        self.board = Board(level)
        self._clear_effects()
        self.time_left = float(level.get("time_limit", 240))
        self.hints_used = 0
        self.undos_used = 0
        self.auto_queue = []
        self._compute_geometry()

    def _clear_effects(self):
        self.flying.clear()
        self.blocked.clear()
        self.hint_pulse = None
        self.hint_arrow_id = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.hover_arrow = None

    # ---------------- 存档相关 ----------------
    def open_settings(self):
        self.menu = MenuPanel(
            (WINDOW_WIDTH // 2, 480), (360, 300), "设置",
            [
                ("音效：%s" % ("开" if self.sound_on else "关"), self.toggle_sound),
                ("辅助线：%s" % ("开" if self.guide_on else "关"),
                 self.toggle_guide),
                ("切换日夜主题", self.toggle_theme),
                ("清空游戏进度", self.reset_progress),
            ],
            (self.font_big, self.font_normal),
            on_close=self.close_menu,
        )

    def close_menu(self):
        self.menu = None

    def open_menu(self):
        self.menu = MenuPanel(
            (WINDOW_WIDTH // 2, 500), (380, 380), "菜单",
            [
                ("撤销一步", self.undo, self.board.can_undo),
                ("提示（%d 金币）" % HINT_COST, self.use_hint,
                 self.coins >= HINT_COST and self.board.remaining > 0),
                ("AI 自动求解", self.auto_solve, self.board.remaining > 1),
                ("重新开始本关", self.restart_level),
                ("关卡选择", self.open_level_select),
                ("返回首页", self.back_home),
            ],
            (self.font_big, self.font_normal),
            on_close=self.close_menu,
        )

    def on_theme_change(self):
        """拨杆被点，或按快捷键：切主题并存档。"""
        theme.toggle()
        self.save.data["theme"] = theme.get().name
        self.save.flush()
        self.menu = None

    # 快捷键走同一条路
    toggle_theme = on_theme_change

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        audio.set_enabled(self.sound_on)
        self.save.data["sound"] = self.sound_on
        self.save.flush()
        self.open_settings()

    def toggle_guide(self):
        self.guide_on = not self.guide_on
        self.save.data["guide"] = self.guide_on
        self.save.flush()
        audio.play("click")
        if self.menu is not None and self.menu.title == "设置":
            self.open_settings()

    def reset_progress(self):
        self.save.reset_all()
        self.coins = self.save.data["coins"]
        self.menu = None
        self.toast("进度已清空")

    # ---------------- 缩放 ----------------
    def on_zoom_slider(self, value):
        self.zoom = ZOOM_MIN + value * (ZOOM_MAX - ZOOM_MIN)
        self._compute_geometry()

    def nudge_zoom(self, delta):
        value = (self.zoom - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN) + delta
        value = max(0.0, min(1.0, value))
        self.hud.zoom_slider.value = value
        self.on_zoom_slider(value)
        audio.play("click")

    # ---------------- 玩法 ----------------
    def toast(self, text):
        self.toast_text = text
        self.toast_timer = TOAST_DURATION

    def _toast_ratio(self):
        if self.toast_timer <= 0:
            return 0.0
        fade_in = 0.12
        fade_out = 0.3
        remain = self.toast_timer
        if remain > TOAST_DURATION - fade_in:
            return (TOAST_DURATION - remain) / fade_in
        if remain < fade_out:
            return remain / fade_out
        return 1.0

    def undo(self):
        """撤销一步；成功返回 True。"""
        if not self.board.can_undo:
            self.toast("没有可以撤销的步骤")
            return False
        self.board.undo()
        self.undos_used += 1
        self.auto_queue = []
        self._clear_effects()
        self.menu = None
        audio.play("click")
        self.toast("已撤销一步")
        return True

    def use_hint(self):
        """花金币点亮一支该点的箭；成功返回 True。"""
        if self.menu:
            self.menu = None
        if self.board.remaining == 0:
            return False
        if self.coins < HINT_COST:
            self.toast("金币不够啦")
            audio.play("block")
            return False
        arrow = self.board.flyable_arrows()
        if not arrow:
            order = solve(self.board)
            if not order:
                self.toast("这一步好像卡住了")
                return False
            arrow = [a for a in self.board.arrows if a.id == order[0]]
        self.coins -= HINT_COST
        self.hints_used += 1
        self.save.data["coins"] = self.coins
        self.save.flush()
        self.hint_arrow_id = arrow[0].id
        self.hint_pulse = HintPulse(arrow[0], segment_width(self.cell_size))
        audio.play("hint")
        self.toast("提示：点这支发光的线段")
        return True

    def auto_solve(self):
        """让 AI 排队把这关点完；排得出顺序返回 True。"""
        if self.menu:
            self.menu = None
        order = solve(self.board)
        if not order:
            self.toast("这一步好像卡住了")
            return False
        self.auto_queue = list(order)
        self.auto_timer = 0.0
        self.toast("AI 正在替你通关…")
        return True

    def skip_level(self):
        if self.state != GameState.PLAYING:
            return
        if self.coins < SKIP_COST:
            self.toast("金币不够，跳过需要 %d 枚" % SKIP_COST)
            audio.play("block")
            return
        self.coins -= SKIP_COST
        self.save.data["coins"] = self.coins
        self.save.flush()
        self.toast("已跳过本关")
        self.next_level()

    def new_random_level(self):
        level = make_random_level()
        self.random_counter += 1
        level["id"] = self.random_counter
        self.level_number = self.random_counter
        self._load_level(level)
        self.state = GameState.PLAYING
        self.toast("随机关卡来啦")

    # ---------------- 鼠标交互 ----------------
    def _handle_playing_motion(self, event):
        if event.type != pygame.MOUSEMOTION:
            return
        if self.flying or self.blocked:
            self.hover_arrow = None
            return
        cell = self._cell_at(event.pos)
        self.hover_arrow = self.board.arrow_at(*cell) if cell else None

    def _handle_board_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.flying or self.blocked or self.menu is not None:
            return

        cell = self._cell_at(event.pos)
        if cell is None:
            return
        arrow = self.board.arrow_at(*cell)
        if arrow is None:
            return                      # 点到空白：不罚

        if self.board.can_fly_arrow(arrow):
            self._launch(arrow)
        else:
            self._block(arrow)

    def _launch(self, arrow):
        self.board.snapshot()
        route, trail = self._build_route(arrow)
        width = segment_width(self.cell_size)
        self.flying.append(FlyingSegment(
            route, trail, len(arrow.cells), arrow.direction, arrow.color,
            width))
        self.board.remove_arrow(arrow)
        self.hover_arrow = None
        if self.hint_arrow_id == arrow.id:
            self.hint_arrow_id = None
            self.hint_pulse = None
        audio.play("fly")

    def _block(self, arrow):
        self.board.snapshot()
        self.board.mistakes -= 1
        self.board.mark_wrong(arrow)
        route, _ = self._build_route(arrow)
        self.blocked.append(BlockedFeedback(
            route, len(arrow.cells), arrow, segment_width(self.cell_size)))
        self.toast("被挡住了！")
        self.hover_arrow = None
        audio.play("block")

    def _build_route(self, arrow):
        """构造滑出像素路径：自身格子（尾 -> 头）+ 箭头方向延长线。"""
        dr, dc = DIRECTION_DELTA[arrow.direction]
        route = [self._grid_center(r, c) for (r, c) in arrow.cells]
        trail = list(route)
        rr, cc = arrow.head
        board_rect = self._board_rect()
        for _ in range(60):
            rr += dr
            cc += dc
            point = self._grid_center(rr, cc)
            route.append(point)
            if board_rect.collidepoint(point):
                trail.append(point)
            if (point[0] < -80 or point[0] > WINDOW_WIDTH + 80
                    or point[1] < -80 or point[1] > WINDOW_HEIGHT + 80):
                break
        return route, trail

    # ---------------- 主循环 ----------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                if event.type == pygame.VIDEORESIZE:
                    self._resize(event.w, event.h)
                if event.type in MOUSE_EVENTS:
                    event.dict["pos"] = self._to_world(event.dict["pos"])
                if event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                self._dispatch_event(event)

            self._update(dt)
            self._draw()
            self._present()
            pygame.display.flip()

    def quit(self):
        self.save.data["coins"] = self.coins
        self.save.flush()
        pygame.quit()
        sys.exit()

    def _handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.menu is not None:
                self.menu = None
            elif self.state in (GameState.LEVEL_SELECT,):
                self.back_home()
            elif self.state == GameState.PLAYING:
                self.open_menu()
            else:
                self.back_home()
            return
        if self.state != GameState.PLAYING:
            return
        if key == pygame.K_u:
            self.undo()
        elif key == pygame.K_h:
            self.use_hint()
        elif key == pygame.K_g:
            self.toggle_guide()
        elif key == pygame.K_n:
            self.new_random_level()
        elif key == pygame.K_a:
            self.auto_solve()

    def _dispatch_event(self, event):
        if self.menu is not None:
            self.menu.handle_event(event)
            return
        if self.state == GameState.START:
            self.start_button.handle_event(event)
            self.select_from_start.handle_event(event)
            return
        if self.state == GameState.LEVEL_SELECT:
            self.back_button.handle_event(event)
            for index, rect in enumerate(self._level_rects()):
                if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and rect.collidepoint(event.pos)):
                    self.select_level(index)
            return
        if self.state == GameState.PLAYING:
            self.hud.handle_event(event)
            self._handle_playing_motion(event)
            self._handle_board_click(event)
            return
        if self.state == GameState.LEVEL_CLEAR:
            self.next_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.GAME_OVER:
            self.retry_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.ALL_CLEAR:
            self.select_home_button.handle_event(event)

    # ---------------- 更新 ----------------
    def _update(self, dt):
        board_rect = self._board_rect()

        for flying in self.flying:
            flying.update(dt, board_rect)
        self.flying = [f for f in self.flying if not f.dead]

        for feedback in self.blocked:
            feedback.update(dt)
        self.blocked = [f for f in self.blocked if not f.dead]

        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        if self.hint_pulse is not None and not self.hint_pulse.update(dt):
            self.hint_pulse = None
            self.hint_arrow_id = None

        if self.state != GameState.PLAYING:
            return

        # 倒计时
        if self.board.remaining > 0 and not self.auto_queue:
            self.time_left = max(0.0, self.time_left - dt)

        # AI 自动求解
        if self.auto_queue and not self.flying and not self.blocked:
            self.auto_timer -= dt
            if self.auto_timer <= 0:
                self.auto_timer = AUTO_STEP_INTERVAL
                arrow_id = self.auto_queue.pop(0)
                arrow = next((a for a in self.board.arrows
                              if a.id == arrow_id), None)
                if arrow is None or not self.board.can_fly_arrow(arrow):
                    self.auto_queue = []
                else:
                    self._launch(arrow)
        if self.auto_queue:
            return

        if not self.flying and not self.blocked:
            if self.board.remaining == 0:
                self._finish_level()
            elif self.board.mistakes <= 0:
                audio.play("fail")
                self.state = GameState.GAME_OVER
            elif self.time_left <= 0:
                self.toast("时间到！")
                audio.play("fail")
                self.state = GameState.GAME_OVER

    def _finish_level(self):
        penalty = (self.board.max_mistakes - self.board.mistakes) \
            + self.hints_used + self.undos_used
        self.stars = STAR_TABLE.get(penalty, 1)
        self.coins += COIN_REWARD_CLEAR
        self.save.data["coins"] = self.coins
        # 只有主线关卡才记进度，随机关卡不写进存档
        if self.current_level is self.levels[self.level_index]:
            self.save.mark_clear(self.current_level.get("id",
                                                        self.level_index + 1),
                                 self.stars, self.coins, self.time_left)
        else:
            self.save.flush()
        audio.play("clear")
        if (self.current_level is self.levels[-1]
                and self.level_index == len(self.levels) - 1):
            self.state = GameState.ALL_CLEAR
        else:
            self.state = GameState.LEVEL_CLEAR

    # ---------------- 绘制 ----------------
    def _present(self):
        self.screen.fill(theme.get().bg)
        scaled = pygame.transform.smoothscale(self.canvas, self.view_rect.size)
        self.screen.blit(scaled, self.view_rect.topleft)

    def _draw(self):
        self.canvas.fill(theme.get().bg)
        if self.state == GameState.START:
            self._draw_start()
            return
        if self.state == GameState.LEVEL_SELECT:
            self._draw_level_select()
            return

        self._draw_board()
        self.hud.draw_top(self.canvas, HudInfo(self))
        self.hud.draw_bottom(self.canvas, HudInfo(self))

        if self.state == GameState.LEVEL_CLEAR:
            self._draw_overlay(
                "%s 通关！" % self.current_level.get("name", "本关"),
                self.stars,
                [self.next_button, self.home_button],
                "线段已全部清空，继续下一关")
        elif self.state == GameState.GAME_OVER:
            self._draw_overlay("挑战失败", 0,
                               [self.retry_button, self.home_button],
                               "红心耗尽或时间到，再试一次吧")
        elif self.state == GameState.ALL_CLEAR:
            self._draw_overlay("全部通关！", 3,
                               [self.select_home_button],
                               "你清空了所有关卡")

        if self.menu is not None:
            self.menu.draw(self.canvas)

    def _draw_text(self, text, font, color, center=None, topleft=None):
        img = font.render(text, True, color)
        rect = img.get_rect(center=center) if center is not None \
            else img.get_rect(topleft=topleft)
        self.canvas.blit(img, rect)
        return rect

    def _draw_board(self):
        pal = theme.get()
        # 辅助线点阵
        if self.guide_on:
            radius = max(1, int(self.cell_size * 0.055))
            for (r, c) in self._mask_cells():
                pygame.draw.circle(self.canvas, pal.dot,
                                   self._cell_rect(r, c).center, radius)

        width = segment_width(self.cell_size)
        blocked_ids = {fb.arrow_id for fb in self.blocked}
        for arrow in self.board.arrows:
            if arrow.id in blocked_ids:
                continue
            centers = [self._cell_rect(r, c).center for (r, c) in arrow.cells]

            if arrow.id == self.hint_arrow_id and self.hint_pulse is not None:
                stroke = self.hint_pulse.stroke_color(arrow.color)
                draw_segment(self.canvas, centers, arrow.direction, stroke,
                             int(width * 1.9))
            elif self.hover_arrow is arrow:
                draw_segment(self.canvas, centers, arrow.direction,
                             lighten(arrow.color, 48), int(width * 1.5))

            color = WRONG_COLOR if arrow.id in self.board.wrong_ids \
                else arrow.color
            draw_segment(self.canvas, centers, arrow.direction, color, width)

        for feedback in self.blocked:
            feedback.draw(self.canvas)
        for flying in self.flying:
            flying.draw(self.canvas)

    def _draw_start(self):
        pal = theme.get()
        cx = WINDOW_WIDTH // 2
        self._draw_text("一箭又一箭", self.font_title, pal.text,
                        center=(cx, 260))
        self._draw_text("Arrow After Arrow", self.font_normal, pal.text_dim,
                        center=(cx, 316))

        rules = [
            "点击彩色线段，让它沿自身轨迹从箭头方向滑出",
            "箭头方向上若有其他线段，会被弹回，消耗一颗红心",
            "清空本关全部线段即可通关，红心耗尽或超时则失败",
        ]
        for i, line in enumerate(rules):
            self._draw_text(line, self.font_normal, pal.text_dim,
                            center=(cx, 420 + i * 46))

        cleared = len(self.save.data["cleared"])
        stars = sum(int(v) for v in self.save.data["stars"].values())
        self._draw_text("已通关 %d / %d 关" % (cleared, len(self.levels)),
                        self.font_normal, pal.text_dim, center=(cx, 590))
        icons.star(self.canvas, (cx - 60, 634), 24, pal.text_gold)
        self._draw_text("累计 %d 星" % stars, self.font_normal, pal.text_dim,
                        center=(cx + 10, 634))
        icons.coin(self.canvas, (cx - 60, 674), 13, pal.coin)
        self._draw_text("金币 %d" % self.coins, self.font_normal, pal.text_dim,
                        center=(cx + 10, 674))

        self.start_button.draw(self.canvas)
        self.select_from_start.draw(self.canvas)
        self._draw_text("U 撤销 / H 提示 / A 自动求解 / G 辅助线 / N 随机关卡",
                        self.font_small, pal.text_dim, center=(cx, 900))
        self._draw_text("Esc 菜单与返回 · 拖动窗口边缘可缩放画面",
                        self.font_small, pal.text_dim, center=(cx, 934))

    def _level_rects(self):
        cols = 4
        size = 118
        gap = 22
        total_w = cols * size + (cols - 1) * gap
        x0 = (WINDOW_WIDTH - total_w) // 2
        y0 = 250
        rects = []
        for index in range(len(self.levels)):
            row, col = divmod(index, cols)
            rects.append(pygame.Rect(x0 + col * (size + gap),
                                     y0 + row * (size + gap), size, size))
        return rects

    def _draw_level_select(self):
        pal = theme.get()
        cx = WINDOW_WIDTH // 2
        self._draw_text("选择关卡", self.font_title, pal.text, center=(cx, 120))
        self.back_button.draw(self.canvas)

        for index, rect in enumerate(self._level_rects()):
            level = self.levels[index]
            level_id = level.get("id", index + 1)
            unlocked = index == 0 or self.save.is_cleared(
                self.levels[index - 1].get("id", index))
            pygame.draw.rect(self.canvas, pal.card if unlocked else pal.panel,
                             rect, border_radius=16)
            pygame.draw.rect(self.canvas, pal.outline if unlocked else pal.dot,
                             rect, 2, border_radius=16)
            color = pal.text if unlocked else pal.text_dim
            self._draw_text(str(level_id), self.font_num, color,
                            center=(rect.centerx, rect.centery - 18))
            self._draw_text(level.get("name", "").split(" ")[-1],
                            self.font_small, pal.text_dim,
                            center=(rect.centerx, rect.centery + 14))
            stars = self.save.stars_of(level_id)
            for i in range(3):
                icons.star(self.canvas,
                           (rect.centerx - 22 + i * 22, rect.bottom - 20), 17,
                           pal.text_gold if i < stars else pal.dot)

        self._draw_text("通关上一关即可解锁下一关", self.font_small,
                        pal.text_dim, center=(cx, 900))
        self._draw_text("点右下角「随机关卡」按钮可以玩新生成的关",
                        self.font_small, pal.text_dim, center=(cx, 934))

    def _draw_overlay(self, title, stars, buttons, hint):
        pal = theme.get()
        veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        veil.fill(pal.veil)
        self.canvas.blit(veil, (0, 0))

        panel = pygame.Rect(0, 0, 520, 340)
        panel.center = (WINDOW_WIDTH // 2, 560)
        pygame.draw.rect(self.canvas, pal.card, panel, border_radius=20)
        pygame.draw.rect(self.canvas, pal.outline, panel, 3, border_radius=20)

        self._draw_text(title, self.font_big, pal.text,
                        center=(panel.centerx, panel.top + 64))
        if stars:
            for i in range(3):
                icons.star(self.canvas,
                           (panel.centerx - 56 + i * 56, panel.top + 128), 44,
                           pal.text_gold if i < stars else pal.dot)
        self._draw_text(hint, self.font_normal, pal.text_dim,
                        center=(panel.centerx, panel.top + 196))
        for button in buttons:
            button.draw(self.canvas)


def main():
    Game().run()


if __name__ == "__main__":
    main()
