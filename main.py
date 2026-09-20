"""一箭又一箭（Arrow After Arrow）游戏入口。

玩法与界面照着参考图 / 录屏复刻：
- 棋盘上摆满彩色线段箭，点击后整条线段沿自身轨迹滑出、再顺箭头方向飞出；
- 被别的线段挡住则变红扣心；
- 顶栏：设置、日夜拨杆、关卡号、红心、倒计时，右侧手柄 / 菜单 / 关卡选择；
- 底栏：金币提示、缩放滑杆、辅助线开关。

开始页有四个入口：规则介绍、基础玩法（12 关）、字母玩法（26 个字母各一关）、
随机关卡（随机造型，每次都不一样）。

扩展功能：AI 求解、提示、撤销、倒计时星级、关卡选择、随机关卡、存档、音效。
快捷键：U 撤销 / H 提示 / A 自动求解 / G 辅助线 / Esc 菜单与返回
（随机关卡从开始页进入，不再占用字母键）。
视图操作：放大后按住棋盘拖动（左键拖过 DRAG_THRESHOLD 即判为拖动，不会误点飞
线段）、中键或右键直接拖、滚轮缩放、方向键微调、0 键复位。
"""

import sys

import pygame

from game import audio, icons, letters as letters_module, paint, theme
from game.animations import (
    TOAST_DURATION,
    BlockedFeedback,
    FlyingSegment,
    HintPulse,
)
from game.arrow import (
    DIRECTION_DELTA,
    blit_disc,
    draw_segment,
    lighten,
    segment_width,
)
from game.board import Board
from game.generator import random_level as make_random_level
from game.hud import Hud
from game.level import LEVELS, TUTORIAL_LEVELS
from game.level_letters import LEVELS as LETTER_LEVELS
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
from game.shapes import level_cells
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
ZOOM_STEP = 0.08            # 滚轮 / 方向键一次缩放多少（滑杆值，0~1）
PAN_STEP = 26               # 方向键一次平移多少逻辑像素
DRAG_THRESHOLD = 8          # 按住后位移超过这么多逻辑像素就算「拖棋盘」而不是「点击」
AUTO_STEP_INTERVAL = 0.30       # AI 自动求解时每隔多久点一支箭
MAX_FRAME_DT = 0.05         # 单帧步进上限：卡一下也不让飞行线「瞬移」
STAR_TABLE = {0: 3, 1: 2, 2: 2}

# 规则页「怎么玩」的正文。三句话各自按卡片宽度自动折行 —— 写死坐标的话，
# 句子一长文字就会顶出卡片右边（而且不会有任何报错）。
HOW_TO_PLAY = (
    "点击彩色线段，它会沿着自己的轨迹滑出、再从箭头方向飞出",
    "箭头方向上有别的线段挡着，就会被弹回来，消耗一颗红心",
    "清空本关全部线段即通关；红心耗尽或倒计时归零则失败",
)

# 规则页「进度与设置」面板的正文：说明怎么清空游戏进度。
PROGRESS_HELP = (
    "想清空全部游戏进度：进入任意关卡后，点左上角的齿轮（设置）→"
    "「清空游戏进度」，操作不可恢复，会一并清除已通关记录与金币。",
)

# 规则页的按键功能表（左列、右列）。改按键就改这里，界面与测试都跟着走。
# 注意：随机关卡已经挪到开始页的入口按钮上，不再占用字母键。
KEY_HINTS = (
    (("U", "撤销一步"), ("滚轮", "缩放棋盘（也可用 - 与 =）")),
    (("H", "提示一步（消耗金币）"), ("拖动", "放大后按住棋盘拖动")),
    (("A", "AI 自动求解本关"), ("方向键", "微调棋盘位置")),
    (("G", "显示 / 隐藏辅助线"), ("0", "复位缩放与位置")),
    (("Esc", "打开菜单 / 返回上一级"), None),
)

# 规则页的版式：每块面板的高度由内容决定，位置依次往下累加（见 _rules_layout）。
RULES_TOP = 150                 # 第一块面板的顶边
RULES_MARGIN = 26               # 面板内的左右留白
RULES_GAP = 16                  # 面板之间
RULES_LINE_H = 32               # 「怎么玩」正文行高
RULES_PARA_GAP = 8              # 「怎么玩」三句话之间的额外间距
RULES_KEY_ROW_H = 46            # 按键功能表行距
RULES_KEY_COL_W = 286           # 按键功能表的列宽（左列起点 → 右列起点）
RULES_KEYS_PAD_TOP = 70         # 按键功能表：面板顶边到第一行
RULES_MODES_H = 236             # 三种玩法面板高度（内容固定四行：入门/基础/字母/随机）

# 开始页的纵向节奏：标题 → 副标题 → 吉祥物 → 五个入口 → 底部提示。
# 吉祥物插进来之后按钮整体下移过一次，这些数字是一组，改一个就要往下看一遍。
START_TITLE_Y = 168             # 拼装标题的中心 y
START_SUBTITLE_Y = 246          # 英文副标题的中心 y
# 吉祥物给出的 ``width`` 是**旋转前**的箭身宽，倾斜之后包围盒会膨胀约 28%，
# 排位置要按画出来的尺寸算，不能按这个数字算。
START_MASCOT_W = 285
START_MASCOT_Y = 386            # 吉祥物中心 y
# 开始页五个入口：规则介绍 / 入门玩法 / 基础玩法 / 字母玩法 / 随机关卡
START_BUTTON_Y = (540, 630, 720, 810, 900)


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
    return (max(200, width - SCREEN_RESERVE_W),
            max(200, height - SCREEN_RESERVE_H))


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
        self.is_random = game.is_random
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
        # 开始页标题专用：比 font_title 大一号，几个元素拼起来才够气派
        self.font_banner = pygame.font.SysFont(FONT_NAME, 74, bold=True)
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
        # 开始页有三个玩法：基础（12 关）、字母（26 关）、随机（每次现场生成）。
        # self.levels 始终指向「当前玩法用的那份关卡列表」；玩随机关卡时它仍
        # 指着 basic 那份，于是随机关不在列表里、也就不会被记进存档进度。
        self.basic_levels = list(LEVELS)
        self.letter_levels = list(LETTER_LEVELS)
        self.tutorial_levels = list(TUTORIAL_LEVELS)
        self.levels = self.basic_levels
        self.track = "basic"
        # 这一局是从哪一屏进来的 —— 顶栏靶心按钮据此决定退回哪里
        # （随机关从开始页进，基础 / 字母关从各自的选关页进）
        self.play_origin = GameState.START
        self.level_index = 0
        self.level_number = 1
        self.current_level = self.levels[0]
        self.board = Board(self.current_level)
        self.is_random = False
        # 随机关卡内部从 1 开始独立编号，不接在基础 / 字母关后面
        self.random_counter = 0

        # ---- 玩法状态 ----
        self.state = GameState.START
        self.rules_back = GameState.START   # 规则页从哪儿来，就回哪儿去
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
        # 棋盘平移量：相对「居中」位置的偏移（逻辑像素）。放大到超出可视区时
        # 靠它把棋盘拖到想看的位置，缩放 / 换关时会被重新夹回合法范围。
        self.pan = [0.0, 0.0]
        # 拖拽状态：按下的位置与待确认的点击格子，松手时按位移判定是拖还是点
        self.dragging = False
        self.drag_button = 1
        self.drag_last = (0, 0)
        self.press_origin = None
        self.press_cell = None

        # 棋盘几何
        self.cell_size = 34
        self.cell_gap = 4
        self.board_x = self.board_y = 0
        self.board_pixel_w = self.board_pixel_h = 0
        self._compute_geometry()

        self.rules_layout = None       # 规则页版式，首次用到时算一次（见 _rules_layout）
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
                # 顶栏靶心是「返回」：回进这一局之前的那一屏，不是固定的某一页
                "select": self.leave_level,
                "hint": self.use_hint,
                "guide": self.toggle_guide,
                "zoom": self.on_zoom_slider,
                "zoom_out": lambda: self.nudge_zoom(-0.1),
                "zoom_in": lambda: self.nudge_zoom(0.1),
            },
        )

        self.hud.zoom_slider.value = (1.0 - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)

        # 开始页的五个入口：规则介绍 / 入门玩法 / 基础玩法 / 字母玩法 / 随机关卡
        rules_y, tutorial_y, basic_y, letter_y, random_y = START_BUTTON_Y
        self.rules_button = Button((cx, rules_y), (340, 80), "规则介绍",
                                   self.open_rules, self.font_big,
                                   kind="ghost", icon=icons.book)
        self.tutorial_button = Button((cx, tutorial_y), (340, 80), "入门玩法",
                                      self.start_tutorial, self.font_big,
                                      icon=icons.star)
        self.basic_button = Button((cx, basic_y), (340, 80), "基础玩法",
                                   self.open_basic_select, self.font_big,
                                   icon=icons.play)
        self.letter_button = Button((cx, letter_y), (340, 80), "字母玩法",
                                    self.open_letter_select, self.font_big,
                                    icon=icons.letter_a)
        self.random_button = Button((cx, random_y), (340, 80), "随机关卡",
                                    self.play_random, self.font_big,
                                    kind="ghost", icon=icons.dice)
        self.start_buttons = (self.rules_button, self.tutorial_button,
                              self.basic_button, self.letter_button,
                              self.random_button)
        self.rules_home_button = Button((cx, self._rules_layout()["home_y"]),
                                        (216, 60), "返回", self.close_rules,
                                        self.font_normal, kind="ghost")
        self.next_button = Button((cx - 128, 672), (200, 56), "下一关",
                                  self.next_level, self.font_normal)
        self.retry_button = Button((cx - 128, 672), (216, 56), "重新开始",
                                   self.restart_level, self.font_normal)
        self.home_button = Button((cx + 128, 672), (176, 56), "返回首页",
                                  self.back_home, self.font_normal,
                                  kind="ghost")
        self.select_home_button = Button((cx, 672), (200, 54), "返回",
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
    def _viewport(self):
        """棋盘的可视区：顶栏与底栏之间那条。放大后棋盘只能在这里面挪。"""
        return pygame.Rect(0, TOP_BAR_HEIGHT, WINDOW_WIDTH,
                           WINDOW_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT)

    def _base_cell(self):
        """不受缩放影响的格子边长与缝隙（照可用区域铺满）。"""
        avail_w = WINDOW_WIDTH - BOARD_MARGIN_X * 2
        avail_h = (WINDOW_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT
                   - BOARD_MARGIN_Y * 2)
        cols, rows = self.board.cols, self.board.rows
        # 先按「不留缝」估一个格子边长，再按比例抽出缝隙
        cell = min(avail_w / cols, avail_h / rows)
        gap = max(2, round(cell * 0.13))
        cell = min((avail_w - gap * (cols - 1)) / cols,
                   (avail_h - gap * (rows - 1)) / rows)
        return min(cell, MAX_CELL_SIZE), gap

    def _base_position(self):
        """棋盘放得下时居中、放不下时居中的那份「零平移」坐标。"""
        view = self._viewport()
        base_x = (WINDOW_WIDTH - self.board_pixel_w) // 2
        if self.board_pixel_h <= view.height:
            offset = max(BOARD_MARGIN_Y,
                         (view.height - self.board_pixel_h) // 2)
        else:
            offset = (view.height - self.board_pixel_h) // 2
        return base_x, TOP_BAR_HEIGHT + offset

    def _clamp_position(self, x, y):
        """把棋盘位置夹进可视区。

        棋盘比可视区小 → 锁死在居中位置（没得拖）；比可视区大 → 允许拖到
        任意一侧边缘对上可视区边缘为止，但绝不允许整块被拖出屏幕。
        """
        view = self._viewport()
        if self.board_pixel_w <= view.width:
            x = (WINDOW_WIDTH - self.board_pixel_w) // 2
        else:
            x = max(view.right - self.board_pixel_w, min(view.left, x))
        if self.board_pixel_h <= view.height:
            base_y = self._base_position()[1]
            y = base_y
        else:
            y = max(view.bottom - self.board_pixel_h, min(view.top, y))
        return int(round(x)), int(round(y))

    def _compute_geometry(self, anchor=None):
        """按当前缩放重算棋盘几何。

        anchor 是画布坐标的一个锚点，缩放时它底下的那个棋盘位置尽量保持不动
        （滚轮缩放就是锚在鼠标上的）；不给就按可视区中心算。
        """
        prev_w, prev_h = self.board_pixel_w, self.board_pixel_h
        prev_x, prev_y = self.board_x, self.board_y

        base_cell, base_gap = self._base_cell()
        self.cell_size = max(6, int(base_cell * self.zoom))
        self.cell_gap = max(1, int(base_gap * self.zoom))
        cols, rows = self.board.cols, self.board.rows
        self.board_pixel_w = cols * self.cell_size + (cols - 1) * self.cell_gap
        self.board_pixel_h = rows * self.cell_size + (rows - 1) * self.cell_gap

        base_x, base_y = self._base_position()
        pan_x, pan_y = self.pan
        if anchor is not None and prev_w > 0 and prev_h > 0:
            # 锚点落在棋盘里的相对位置：缩放前后让它停在同一个百分比处
            u = (anchor[0] - prev_x) / prev_w
            v = (anchor[1] - prev_y) / prev_h
            pan_x = anchor[0] - u * self.board_pixel_w - base_x
            pan_y = anchor[1] - v * self.board_pixel_h - base_y

        self.board_x, self.board_y = self._clamp_position(base_x + pan_x,
                                                         base_y + pan_y)
        # 把夹过的结果写回 pan，避免拖到边界后越攒越多（松手再往回拖会「粘住」）
        self.pan = [self.board_x - base_x, self.board_y - base_y]

    def _board_center(self):
        return (self.board_x + self.board_pixel_w // 2,
                self.board_y + self.board_pixel_h // 2)

    def _view_center(self):
        return self._viewport().center

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
        return level_cells(self.current_level)

    # ---------------- 状态切换 ----------------
    def use_track(self, track):
        """切换当前玩法：self.levels 指向那一份关卡列表。"""
        self.track = track
        self.levels = (self.letter_levels if track == "letter"
                       else self.tutorial_levels if track == "tutorial"
                       else self.basic_levels)

    def start_game(self):
        """从基础玩法的第 1 关直接开一局。"""
        self.use_track("basic")
        self.play_origin = GameState.BASIC_SELECT
        self.level_index = 0
        self.level_number = self.levels[0].get("id", 1)
        self._load_level(self.levels[0])
        self.state = GameState.PLAYING

    def start_tutorial(self):
        """从入门玩法的第 1 关直接开一局（独立成线，不跟基础 / 字母关混）。"""
        self.use_track("tutorial")
        self.play_origin = GameState.START
        self.level_index = 0
        self.level_number = self.levels[0].get("id", 1)
        self._load_level(self.levels[0])
        self.state = GameState.PLAYING

    def open_rules(self):
        """规则介绍：记住从哪儿来，返回时回原处。"""
        self.rules_back = (self.state if self.state != GameState.RULES
                           else GameState.START)
        self.menu = None
        self._clear_effects()
        self.state = GameState.RULES

    def close_rules(self):
        """关掉规则页：回开始页，或者回打开规则前的那一屏。"""
        if self.rules_back == GameState.PLAYING:
            self.state = GameState.PLAYING
        else:
            self.back_home()

    def open_basic_select(self):
        self.use_track("basic")
        self.play_origin = GameState.BASIC_SELECT
        self.menu = None
        self._clear_effects()
        self.state = GameState.BASIC_SELECT

    def open_letter_select(self):
        self.use_track("letter")
        self.play_origin = GameState.LETTER_SELECT
        self.menu = None
        self._clear_effects()
        self.state = GameState.LETTER_SELECT

    def open_select(self):
        """菜单里的「关卡选择」：进当前玩法对应的那一页。

        这里必须**按 self.track 现场分派**。原来顶栏那个按钮接的是
        ``open_level_select``（一个在类定义时就绑死到 open_basic_select 的别名），
        于是玩字母关时点它也会跳到基础选关页 —— 别名不再保留，避免重蹈覆辙。
        """
        if self.track == "letter":
            self.open_letter_select()
        else:
            self.open_basic_select()

    def leave_level(self):
        """顶栏靶心按钮（对局中那个圆圈）：回到**进这一局之前**的那一屏。

        之前这里是「按 track 分派」的 ``open_select``：基础关回基础选关页、
        字母关回字母选关页，**但随机关卡不属于任何一条线**，于是也被当成基础关
        塞进了基础选关页 —— 玩家点它想回开始页，结果掉进一个自己从没进过的界面。
        改成认「来路」之后，三条线各自回到玩家真正出发的地方。
        """
        origin = self.play_origin
        if origin == GameState.BASIC_SELECT:
            self.open_basic_select()
        elif origin == GameState.LETTER_SELECT:
            self.open_letter_select()
        else:
            self.back_home()

    def play_random(self):
        """随机玩法：现场生成一关开打（不进选关页，也不记进度）。"""
        self.use_track("basic")
        self.play_origin = GameState.START
        self.menu = None
        self.new_random_level()

    def next_level(self):
        # 随机关卡「下一关」再生成一关随机，不跳进基础 / 字母关列表
        if self.is_random:
            self.new_random_level()
            return
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
        self.pan = [0.0, 0.0]
        self._compute_geometry()
        self.state = GameState.PLAYING

    def back_home(self):
        self._clear_effects()
        self.menu = None
        self.play_origin = GameState.START
        self.save.flush()
        self.state = GameState.START

    def select_level(self, index):
        self.level_index = index
        self.level_number = self.levels[index].get("id", index + 1)
        self._load_level(self.levels[index])
        self.state = GameState.PLAYING

    def _load_level(self, level):
        self.current_level = level
        # 不在当前关卡列表里的就是随机关卡（现场生成，不在 levels 中）
        self.is_random = not any(level is lv for lv in self.levels)
        self.board = Board(level)
        self._clear_effects()
        self.time_left = float(level.get("time_limit", 240))
        self.hints_used = 0
        self.undos_used = 0
        self.auto_queue = []
        self.pan = [0.0, 0.0]           # 新关从正中间开始，不留上一关的偏移
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
            (WINDOW_WIDTH // 2, 470), (360, 330), "设置",
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
            (WINDOW_WIDTH // 2, 520), (380, 470), "菜单",
            [
                ("撤销一步", self.undo, self.board.can_undo),
                ("提示（%d 金币）" % HINT_COST, self.use_hint,
                 self.coins >= HINT_COST and self.board.remaining > 0),
                ("AI 自动求解", self.auto_solve, self.board.remaining > 1),
                ("重新开始本关", self.restart_level),
                ("关卡选择", self.open_select),
                ("规则介绍", self.open_rules),
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

    # ---------------- 缩放与平移 ----------------
    def _zoom_ratio(self):
        """缩放值在滑杆上的比例（0 ~ 1）。"""
        return (self.zoom - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)

    def on_zoom_slider(self, value, anchor=None):
        """设置缩放（滑杆 0~1），anchor 是画布坐标的锚点。"""
        value = max(0.0, min(1.0, value))
        self.hud.zoom_slider.value = value
        self.zoom = ZOOM_MIN + value * (ZOOM_MAX - ZOOM_MIN)
        self._compute_geometry(self._view_center() if anchor is None
                               else anchor)

    def nudge_zoom(self, delta):
        self.on_zoom_slider(self._zoom_ratio() + delta)
        audio.play("click")

    def pan_by(self, dx, dy):
        """把棋盘平移 (dx, dy) 逻辑像素；真的挪动了才返回 True。"""
        if not dx and not dy:
            return False
        before = (self.board_x, self.board_y)
        base_x, base_y = self._base_position()
        self.board_x, self.board_y = self._clamp_position(self.board_x + dx,
                                                         self.board_y + dy)
        self.pan = [self.board_x - base_x, self.board_y - base_y]
        return (self.board_x, self.board_y) != before

    def reset_view(self):
        """缩放与平移都复位（棋盘重新摆回正中间）。

        注意滑杆的值是 0~1 的**比例**，1.0 对应 `ZOOM_MAX` 而不是 100%，
        所以这里直接写 `self.zoom`，再把比例同步回滑杆。
        """
        self.pan = [0.0, 0.0]
        self.zoom = 1.0
        self.hud.zoom_slider.value = self._zoom_ratio()
        self._compute_geometry()
        self.toast("视图已复位")

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
        level["name"] = "随机关卡"
        self.random_counter += 1
        level["id"] = self.random_counter
        self.level_number = self.random_counter
        # 随机关卡不按下标追踪；把 level_index 归位，避免遗留自上一玩法
        # （如字母 26 关）的大下标，让任何依赖 level_index 的代码越界。
        self.level_index = 0
        self._load_level(level)
        self.state = GameState.PLAYING
        self.toast("随机关卡来啦")

    # ---------------- 鼠标交互 ----------------
    def _handle_board_pointer(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._handle_board_motion(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_board_press(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_board_release(event)

    def _handle_board_motion(self, event):
        if self.dragging:
            if self._button_released(event):
                # 指针拖出窗口后在窗口外松手时，抬起事件可能收不到；
                # MOUSEMOTION 自带按键状态，用它兜住，免得拖拽状态卡住。
                self.dragging = False
                self.press_origin = None
                self.press_cell = None
                return
            self._drag_to(event.pos)
            return
        if (self.press_origin is not None
                and self._moved_far(event.pos) and self._can_drag()):
            # 按住后拖出了阈值：这次操作改判为「拖棋盘」，作废待确认的点击
            self.dragging = True
            self.drag_button = 1
            self.press_cell = None
            self.hover_arrow = None
            self._drag_to(event.pos, origin=self.press_origin)
            return
        self._handle_playing_motion(event)

    def _handle_board_press(self, event):
        if event.button in (2, 3):          # 中键 / 右键：按住就能拖
            if self._can_drag():
                self.dragging = True
                self.drag_button = event.button
                self.drag_last = event.pos
            return
        if event.button != 1:
            return
        # 左键先记账，松手时再按位移判定是点还是拖（否则必通盘的每一格都是
        # 线段，想拖棋盘就一定会点飞一支箭）
        self.press_origin = event.pos
        self.press_cell = self._cell_at(event.pos)

    def _button_released(self, event):
        """MOUSEMOTION 自带的按键状态是否显示拖拽键已经松开。"""
        buttons = event.dict.get("buttons")
        if buttons is None:
            return False
        index = self.drag_button - 1
        return 0 <= index < len(buttons) and not buttons[index]

    def _handle_board_release(self, event):
        if event.button in (2, 3):
            self.dragging = False
            return
        if event.button != 1:
            return
        was_dragging = self.dragging
        origin, cell = self.press_origin, self.press_cell
        self.dragging = False
        self.press_origin = None
        self.press_cell = None
        if was_dragging or origin is None or cell is None:
            return
        if abs(event.pos[0] - origin[0]) > DRAG_THRESHOLD \
                or abs(event.pos[1] - origin[1]) > DRAG_THRESHOLD:
            return
        if self.flying or self.blocked or self.menu is not None:
            return
        self._click_cell(cell)

    def _can_drag(self):
        """棋盘只有放大到超出可视区时才拖得动。"""
        view = self._viewport()
        return (self.board_pixel_w > view.width
                or self.board_pixel_h > view.height)

    def _moved_far(self, pos):
        if self.press_origin is None:
            return False
        return (abs(pos[0] - self.press_origin[0]) > DRAG_THRESHOLD
                or abs(pos[1] - self.press_origin[1]) > DRAG_THRESHOLD)

    def _drag_to(self, pos, origin=None):
        """把指针从上次的位置拖到 pos，棋盘跟着走。"""
        if origin is not None:
            self.drag_last = origin
        dx = pos[0] - self.drag_last[0]
        dy = pos[1] - self.drag_last[1]
        self.drag_last = pos
        self.pan_by(dx, dy)

    def _handle_wheel(self, event):
        """滚轮缩放，锚在鼠标指的位置上。"""
        if not event.y or self.state != GameState.PLAYING \
                or self.menu is not None:
            return
        anchor = self._to_world(pygame.mouse.get_pos())
        step = ZOOM_STEP * (1 if event.y > 0 else -1)
        self.on_zoom_slider(self._zoom_ratio() + step, anchor=anchor)

    def _handle_playing_motion(self, event):
        if event.type != pygame.MOUSEMOTION:
            return
        if self.flying or self.blocked:
            self.hover_arrow = None
            return
        cell = self._cell_at(event.pos)
        self.hover_arrow = self.board.arrow_at(*cell) if cell else None

    def _click_cell(self, cell):
        """在某一格上落实一次左键点击。"""
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
    def _frame_dt(self):
        """本帧的步进秒数（夹了上限）。

        切窗口 / 系统忙的时候 clock.tick 可能一次返回好几百毫秒，飞行线一步
        就跨过好几格，看起来像「瞬移」了一下。夹住上限，宁可让动画慢半拍，
        也不要让它跳。
        """
        return min(self.clock.tick(FPS) / 1000.0, MAX_FRAME_DT)

    def run(self):
        while True:
            dt = self._frame_dt()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                if event.type == pygame.VIDEORESIZE:
                    self._resize(event.w, event.h)
                if event.type == pygame.MOUSEWHEEL:
                    self._handle_wheel(event)
                    continue
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
            elif self.state == GameState.RULES:
                self.close_rules()
            elif self.state in (GameState.BASIC_SELECT,
                                GameState.LETTER_SELECT):
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
        elif key == pygame.K_a:
            self.auto_solve()
        elif key == pygame.K_LEFT:
            self.pan_by(PAN_STEP, 0)
        elif key == pygame.K_RIGHT:
            self.pan_by(-PAN_STEP, 0)
        elif key == pygame.K_UP:
            self.pan_by(0, PAN_STEP)
        elif key == pygame.K_DOWN:
            self.pan_by(0, -PAN_STEP)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.nudge_zoom(ZOOM_STEP)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.nudge_zoom(-ZOOM_STEP)
        elif key in (pygame.K_0, pygame.K_KP0):
            self.reset_view()

    def _grid_clicked(self, rects, event):
        """网格里被点中的格子下标；没点中返回 None。"""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        for index, rect in enumerate(rects):
            if rect.collidepoint(event.pos):
                return index
        return None

    def _dispatch_event(self, event):
        if self.menu is not None:
            self.menu.handle_event(event)
            return
        if self.state == GameState.START:
            for button in self.start_buttons:
                button.handle_event(event)
            return
        if self.state == GameState.RULES:
            self.rules_home_button.handle_event(event)
            return
        if self.state == GameState.BASIC_SELECT:
            self.back_button.handle_event(event)
            index = self._grid_clicked(self._level_rects(), event)
            if index is not None:
                self.select_level(index)
            return
        if self.state == GameState.LETTER_SELECT:
            self.back_button.handle_event(event)
            index = self._grid_clicked(self._letter_rects(), event)
            if index is not None:
                self.select_level(index)
            return
        if self.state == GameState.PLAYING:
            # 先给顶栏 / 底栏的控件；被它们吃掉的事件不要再落到棋盘上，
            # 否则放大后的棋盘铺到工具栏底下时会「点一个按钮顺带飞一支箭」。
            if self.hud.handle_event(event):
                return
            self._handle_board_pointer(event)
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
        # 只有「列表里的正经关卡」才记进度：随机关卡是现场生成的，
        # 不在 self.levels 里，绝不写进存档。用身份比较（is）做成员判断，
        # 这样即便 level_index 因切换玩法而越界也不会崩。
        is_official = any(self.current_level is lv for lv in self.levels)
        if is_official:
            self.save.mark_clear(self.current_level.get("id",
                                                        self.level_index + 1),
                                 self.stars, self.coins, self.time_left)
        else:
            self.save.flush()
        audio.play("clear")
        # 通关的恰是列表最后一关才进 ALL_CLEAR
        if is_official and self.level_index == len(self.levels) - 1:
            self.state = GameState.ALL_CLEAR
        else:
            self.state = GameState.LEVEL_CLEAR

    # ---------------- 绘制 ----------------
    def _present(self):
        # 窗口比例和画布不一致时四周会留边，用背景渐变的深色端填，
        # 画面看着像是「镶」在里面，而不是贴在一块突兀的纯色上
        self.screen.fill(theme.get().bg_bottom)
        scaled = pygame.transform.smoothscale(self.canvas, self.view_rect.size)
        self.screen.blit(scaled, self.view_rect.topleft)

    def _draw(self):
        self._draw_background()
        if self.state == GameState.START:
            self._draw_start()
            return
        if self.state == GameState.RULES:
            self._draw_rules()
            return
        if self.state == GameState.BASIC_SELECT:
            self._draw_level_select()
            return
        if self.state == GameState.LETTER_SELECT:
            self._draw_letter_select()
            return

        self._draw_board()
        self.hud.draw_top(self.canvas, HudInfo(self))
        self.hud.draw_bottom(self.canvas, HudInfo(self))

        pal = theme.get()
        if self.state == GameState.LEVEL_CLEAR:
            self._draw_overlay(
                "%s 通关！" % self.current_level.get("name", "本关"),
                self.stars,
                [self.next_button, self.home_button],
                "线段已全部清空，继续下一关",
                title_color=pal.success)
        elif self.state == GameState.GAME_OVER:
            self._draw_overlay("挑战失败", 0,
                               [self.retry_button, self.home_button],
                               "红心耗尽或时间到，再试一次吧",
                               title_color=pal.danger)
        elif self.state == GameState.ALL_CLEAR:
            self._draw_overlay("全部通关！", 3,
                               [self.select_home_button],
                               "你清空了所有关卡",
                               title_color=pal.text_gold)

        if self.menu is not None:
            self.menu.draw(self.canvas)

    def _draw_text(self, text, font, color, center=None, topleft=None):
        img = font.render(text, True, color)
        rect = img.get_rect(center=center) if center is not None \
            else img.get_rect(topleft=topleft)
        self.canvas.blit(img, rect)
        return rect

    def _draw_background(self):
        """整页底：竖向渐变 + 几团错开的柔雾，视线自然被拉到画面中间。

        非对局界面额外铺一组低透明度的彩色柔雾（`Palette.fog`），底子不再是
        一条从亮到暗的平涂，而是有远近的雾面。**对局中不铺** —— 雾会压住
        棋盘的可读性，盘面本身已经是整屏的彩色线段了。
        """
        pal = theme.get()
        if self.state == GameState.START:
            # 开始页换成「一块浅底 + 一层几乎看不见的同色暗纹」：暗纹用的是
            # 游戏自己那支胖箭（不是照抄参考图的图案），平铺成壁纸的底子。
            # 整屏预合成成一张贴图，每帧仍只是一次 blit。
            paint.blit_pattern(self.canvas, (WINDOW_WIDTH, WINDOW_HEIGHT),
                               pal.menu_top, pal.menu_bottom, pal.pattern,
                               pal.pattern_alpha)
            paint.blit_fog(self.canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), pal.fog)
            paint.blit_glow(self.canvas, (WINDOW_WIDTH // 2, START_MASCOT_Y),
                            330, pal.glow, 66, 2.1)
            return
        self.canvas.blit(paint.vertical_gradient(
            (WINDOW_WIDTH, WINDOW_HEIGHT), pal.bg_top, pal.bg_bottom), (0, 0))
        if self.state in (GameState.PLAYING, GameState.LEVEL_CLEAR,
                          GameState.GAME_OVER, GameState.ALL_CLEAR):
            paint.blit_glow(self.canvas, self._view_center(), 430, pal.glow,
                            62, 2.3)
            return
        paint.blit_fog(self.canvas, (WINDOW_WIDTH, WINDOW_HEIGHT), pal.fog)
        paint.blit_glow(self.canvas, (WINDOW_WIDTH // 2, 520), 430, pal.glow,
                        62, 2.3)

    def _draw_board(self):
        pal = theme.get()
        # 棋盘底下垫一块圆角面板：盘面是「一块台面」，不是漂浮的色块。
        # 面板比可视区小一圈，放大拖动时棋盘可以铺到面板外面去。
        panel = self._viewport().inflate(-16, -16)
        paint.draw_card(self.canvas, panel, 26,
                        fill_top=pal.board_top, fill_bottom=pal.board_bottom,
                        border=pal.board_line, border_width=1, alpha=196,
                        shadow=(16, 110, pal.card_shadow[2], 8))
        # 辅助线点阵：用抗锯齿圆点，缩到最小格子时也不会变成一撮锯齿
        if self.guide_on:
            radius = max(1, int(self.cell_size * 0.055))
            for (r, c) in self._mask_cells():
                blit_disc(self.canvas, self._cell_rect(r, c).center,
                          radius, pal.dot)

        width = segment_width(self.cell_size)
        blocked_ids = {fb.arrow_id for fb in self.blocked}
        for arrow in self.board.arrows:
            if arrow.id in blocked_ids:
                continue
            centers = [self._cell_rect(r, c).center for (r, c) in arrow.cells]

            # 高亮先铺一层更宽的光晕，真正的线段再压在它上面。
            # 光晕自己不描边 —— 描了会在光晕与线身之间夹一圈黑边。
            if arrow.id == self.hint_arrow_id and self.hint_pulse is not None:
                stroke = self.hint_pulse.stroke_color(arrow.color)
                draw_segment(self.canvas, centers, arrow.direction, stroke,
                             int(width * 1.9), outline=False)
            elif self.hover_arrow is arrow:
                draw_segment(self.canvas, centers, arrow.direction,
                             lighten(arrow.color, 48), int(width * 1.5),
                             outline=False)

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

        # 标题后面再压一团柔光：艺术字从背景里「亮」出来
        paint.blit_glow(self.canvas, (cx, START_TITLE_Y), 360, pal.glow, 78,
                        2.0)
        self._draw_start_title((cx, START_TITLE_Y))
        paint.text_shadow(self.canvas, self.font_normal, "ARROW AFTER ARROW",
                          pal.text_dim, center=(cx, START_SUBTITLE_Y),
                          shadow=(4, 8, 20), alpha=90, offset=(0, 1))
        self._draw_start_mascot()

        for button in self.start_buttons:
            button.draw(self.canvas)

        self._draw_text("放大后按住棋盘拖动 / 滚轮或滑杆缩放 · 方向键微调 / 0 复位",
                        self.font_small, pal.text_dim, center=(cx, 1082))
        self._draw_text("对局中：U 撤销 / H 提示 / A 自动求解 / G 辅助线 / Esc 菜单",
                        self.font_small, pal.text_dim, center=(cx, 1112))

    def _draw_start_mascot(self):
        """标题下方那只卡通箭（参考图里的吉祥物）。

        它本质上是**游戏自己那支箭长了张脸**：箭身渐变 + 深色描边 + 贴边暗面 +
        高光 + 两只眼睛，最后整体倾斜一点，看着像正要飞出去。画法是纯几何拼的
        （``paint.arrow_mascot``），不依赖任何图片资源，切主题会自动换配色。
        """
        pal = theme.get()
        image = paint.arrow_mascot(
            START_MASCOT_W, pal.mascot_light, pal.mascot_dark,
            pal.mascot_line, pal.mascot_gloss, eye=pal.mascot_eye,
            pupil=pal.mascot_pupil, shadow=pal.mascot_shadow,
            shadow_alpha=72, shadow_offset=(4, 10), tilt=-10,
            outline_width=6)
        rect = image.get_rect(center=(WINDOW_WIDTH // 2, START_MASCOT_Y))
        self.canvas.blit(image, rect)
        return rect

    def _start_title_pieces(self, pal):
        """标题「一箭又一箭」拆成五片：两根横条 + 三个字。

        前后两个「一」不写成汉字，直接画成带渐变的红 / 蓝圆头横杠（点题），
        末尾那个「箭」换成绿色收尾 —— 于是整条标题有节奏，不再是一排同色的字。
        横杠也加竖向渐变 + 顶部高光，像一根根有光泽的糖果条。
        """
        _width, line_h = self.font_banner.size("箭")
        face = (pal.art_top, pal.art_bottom)
        bar_a_top = paint.mix(pal.art_bar_a, (255, 255, 255), 0.34)
        bar_a_bot = paint.mix(pal.art_bar_a, (0, 0, 0), 0.20)
        bar_b_top = paint.mix(pal.art_bar_b, (255, 255, 255), 0.34)
        bar_b_bot = paint.mix(pal.art_bar_b, (0, 0, 0), 0.20)
        bar = {
            "kind": "bar",
            "width": int(line_h * 1.12),
            "height": max(12, int(line_h * 0.34)),
        }
        return [
            dict(bar, color=pal.art_bar_a, top=bar_a_top, bottom=bar_a_bot),
            {"kind": "text", "text": "箭", "top": face[0], "bottom": face[1]},
            {"kind": "text", "text": "又", "top": face[0], "bottom": face[1]},
            dict(bar, color=pal.art_bar_b, top=bar_b_top, bottom=bar_b_bot),
            {"kind": "text", "text": "箭", "top": pal.art_alt_top,
             "bottom": pal.art_alt_bottom},
        ]

    def _start_title_image(self):
        """开始页标题的贴图：拼装出来，自然宽度超了就整体等比缩回来。"""
        pal = theme.get()
        banner = paint.art_banner(
            self.font_banner, self._start_title_pieces(pal), gap=8,
            outline=pal.art_outline, outline_width=7,
            outline2=pal.art_edge, outline2_width=4,
            highlight=pal.art_gloss, shadow=(26, 24, 46),
            shadow_offset=(0, 10), lift=4)
        max_width = WINDOW_WIDTH - 56
        if banner.get_width() > max_width:
            ratio = max_width / banner.get_width()
            banner = pygame.transform.smoothscale(
                banner, (max_width, max(1, int(banner.get_height() * ratio))))
        return banner

    def _draw_start_title(self, center):
        """按中心画拼装标题，返回它占的 rect。"""
        banner = self._start_title_image()
        rect = banner.get_rect(center=(int(center[0]), int(center[1])))
        self.canvas.blit(banner, rect)
        return rect

    def _cleared_count(self, levels):
        """一份关卡列表里已通关的关数。"""
        return sum(1 for level in levels
                   if self.save.is_cleared(level.get("id")))

    def _draw_progress_bar(self, rect, ratio):
        """一条细进度条：凹槽 + 已填充段，与选关页用的是同一套画法。"""
        pal = theme.get()
        paint.draw_card(self.canvas, rect, rect.height // 2,
                        fill_top=paint.mix(pal.slider_track, pal.card_line,
                                           0.5),
                        fill_bottom=pal.slider_track,
                        border=pal.surface_line, border_width=1, alpha=235)
        width = int(rect.width * max(0.0, min(1.0, ratio)))
        if width < 6:
            return
        fill = pygame.Rect(rect.left, rect.top, width, rect.height)
        pygame.draw.rect(self.canvas, pal.accent, fill,
                         border_radius=rect.height // 2)
        upper = pygame.Rect(fill.left, fill.top, fill.width,
                            fill.height // 2 + 1)
        pygame.draw.rect(self.canvas, paint.mix(pal.accent, (255, 255, 255),
                                                0.4), upper,
                         border_radius=rect.height // 2)

    def _rules_layout(self):
        """规则页的版式（算一次就缓存）。

        `_draw_rules` 每帧都要用它，而折行要逐行做 `font.size` 度量，每帧重算
        不划算；文案、字体都不会在运行中变，算一次即可。
        """
        if self.rules_layout is None:
            self.rules_layout = self._compute_rules_layout()
        return self.rules_layout

    def _compute_rules_layout(self):
        """每块面板的高度**由内容算出来**，下一块接着往下排。

        原来三块面板的 y 与高度都是写死的数字，正文一长就会顶出卡片右边 ——
        卡片宽度不变、文字又不会折行，而且这种溢出不会有任何报错，只能靠
        肉眼发现。改成按内容累加之后，往文案里再加一句话也不会溢出。
        """
        left = 24
        width = WINDOW_WIDTH - left * 2
        inner = width - RULES_MARGIN * 2
        how_lines, how_tops = [], []
        offset = 60                       # 面板顶边 → 正文第一行
        for sentence in HOW_TO_PLAY:
            if how_lines:
                offset += RULES_PARA_GAP  # 三句话之间留一点，不然六行糊成一段
            for line in paint.wrap_text(self.font_normal, sentence, inner):
                how_lines.append(line)
                how_tops.append(offset)
                offset += RULES_LINE_H

        y = RULES_TOP
        how = pygame.Rect(left, y, width, offset + 14)
        y = how.bottom + RULES_GAP
        keys = pygame.Rect(
            left, y, width,
            RULES_KEYS_PAD_TOP + 6 + (len(KEY_HINTS) - 1) * RULES_KEY_ROW_H + 32)
        y = keys.bottom + RULES_GAP
        modes = pygame.Rect(left, y, width, RULES_MODES_H)
        y = modes.bottom + RULES_GAP
        prog_lines, prog_tops = [], []
        poff = 60
        for sentence in PROGRESS_HELP:
            if prog_lines:
                poff += RULES_PARA_GAP
            for line in paint.wrap_text(self.font_normal, sentence, inner):
                prog_lines.append(line)
                prog_tops.append(poff)
                poff += RULES_LINE_H
        progress = pygame.Rect(left, y, width, poff + 14)
        y = progress.bottom + 34
        return {
            "how": how,
            "how_lines": how_lines,
            "how_tops": how_tops,
            "keys": keys,
            "modes": modes,
            "progress": progress,
            "progress_lines": prog_lines,
            "progress_tops": prog_tops,
            "note_y": y,
            "home_y": y + 54,
            "esc_y": y + 106,
        }

    def _draw_rules(self):
        """规则介绍：玩法说明 + 按键功能表 + 三种玩法。"""
        pal = theme.get()
        cx = WINDOW_WIDTH // 2
        layout = self._rules_layout()
        paint.blit_glow(self.canvas, (cx, 100), 260, pal.glow, 58, 2.0)
        paint.text_shadow(self.canvas, self.font_title, "玩法规则", pal.text,
                          center=(cx, 100), shadow=(6, 12, 30), alpha=130,
                          offset=(0, 3))

        # ---- 怎么玩 ----
        how = layout["how"]
        paint.draw_panel(self.canvas, how, 22)
        self._draw_text("怎么玩", self.font_big, pal.text_gold,
                        topleft=(how.left + RULES_MARGIN, how.top + 18))
        for line, top in zip(layout["how_lines"], layout["how_tops"]):
            self._draw_text(line, self.font_normal, pal.text_dim,
                            topleft=(how.left + RULES_MARGIN, how.top + top))

        # ---- 按键功能表（两列）----
        keys = layout["keys"]
        paint.draw_panel(self.canvas, keys, 22)
        self._draw_text("按键功能", self.font_big, pal.text_gold,
                        topleft=(keys.left + RULES_MARGIN, keys.top + 18))
        for row_index, row in enumerate(KEY_HINTS):
            for col_index, item in enumerate(row):
                if item is None:
                    continue
                x = keys.left + RULES_MARGIN + col_index * RULES_KEY_COL_W
                # 右列不许越过面板内边距，说明文字按这个余量折行
                avail = min(RULES_KEY_COL_W,
                            keys.right - RULES_MARGIN - x)
                self._draw_key_hint(
                    x,
                    keys.top + RULES_KEYS_PAD_TOP + row_index * RULES_KEY_ROW_H,
                    item[0], item[1], avail)

        # ---- 四种玩法 ----
        modes = layout["modes"]
        paint.draw_panel(self.canvas, modes, 22)
        self._draw_text("四种玩法", self.font_big, pal.text_gold,
                        topleft=(modes.left + RULES_MARGIN, modes.top + 18))
        lines = (
            (icons.star, "入门玩法", "3 关单格箭，从零开始练手"),
            (icons.play, "基础玩法", "12 关，从小盘到大盘，难度一路递增"),
            (icons.letter_a, "字母玩法", "26 个字母各一关，整盘铺成一个字母"),
            (icons.dice, "随机关卡", "随机造型现场生成，每次都不一样"),
        )
        for index, (icon, name, desc) in enumerate(lines):
            y = modes.top + 76 + index * 40
            icon(self.canvas, (modes.left + 38, y), 22, pal.outline)
            self._draw_text(name, self.font_normal, pal.text,
                            topleft=(modes.left + 60, y - 14))
            self._draw_text(desc, self.font_small, pal.text_dim,
                            topleft=(modes.left + 176, y - 10))

        # ---- 进度与设置 ----
        progress = layout["progress"]
        paint.draw_panel(self.canvas, progress, 22)
        self._draw_text("进度与设置", self.font_big, pal.text_gold,
                        topleft=(progress.left + RULES_MARGIN,
                                 progress.top + 18))
        for line, top in zip(layout["progress_lines"], layout["progress_tops"]):
            self._draw_text(line, self.font_normal, pal.text_dim,
                            topleft=(progress.left + RULES_MARGIN,
                                     progress.top + top))

        self._draw_text("以上玩法都从开始页的按钮进入", self.font_small,
                        pal.text_dim, center=(cx, layout["note_y"]))
        self.rules_home_button.rect.center = (cx, layout["home_y"])
        self.rules_home_button.draw(self.canvas)
        self._draw_text("Esc 也可以直接返回", self.font_small, pal.text_dim,
                        center=(cx, layout["esc_y"]))

    def _draw_key_hint(self, x, y, key, label, width=RULES_KEY_COL_W):
        """一个按键胶囊 + 右侧说明；说明超宽就折成两行，不往下一行挤。"""
        pal = theme.get()
        capsule = pygame.Rect(x, y - 16, 62, 32)
        paint.draw_card(self.canvas, capsule, 9, fill_top=pal.card_top,
                        fill_bottom=pal.card_bottom, border=pal.surface_line,
                        border_width=1)
        self._draw_text(key, self.font_small, pal.text_gold,
                        center=capsule.center)
        lines = paint.wrap_text(self.font_small, label,
                                max(24, width - (capsule.width + 12)))
        # 折成两行时整体上移半行，跟左侧胶囊在视觉上仍然对齐
        top = y - 10 - (len(lines) - 1) * 11
        for index, line in enumerate(lines):
            self._draw_text(line, self.font_small, pal.text_dim,
                            topleft=(capsule.right + 12, top + index * 22))

    def _level_rects(self):
        return self._grid_rects(len(self.levels), cols=4, size=124, gap=24,
                                y0=262)

    def _grid_rects(self, count, cols, size, gap, y0):
        """网格卡片的位置：先按列数算整块宽度，再左右居中。"""
        total_w = cols * size + (cols - 1) * gap
        x0 = (WINDOW_WIDTH - total_w) // 2
        rects = []
        for index in range(count):
            row, col = divmod(index, cols)
            rects.append(pygame.Rect(x0 + col * (size + gap),
                                     y0 + row * (size + gap), size, size))
        return rects

    def _letter_rects(self):
        """字母选关页的 26 个格子（6 列 5 行）。"""
        return self._grid_rects(len(self.letter_levels), cols=6, size=88,
                                gap=12, y0=228)

    def _draw_level_select(self):
        pal = theme.get()
        cx = WINDOW_WIDTH // 2
        paint.blit_glow(self.canvas, (cx, 116), 260, pal.glow, 58, 2.0)
        paint.text_shadow(self.canvas, self.font_title, "选择关卡", pal.text,
                          center=(cx, 116), shadow=(6, 12, 30), alpha=130,
                          offset=(0, 3))
        cleared = self._cleared_count(self.basic_levels)
        self._draw_text("通关上一关即可解锁下一关 · 每关最多三颗星",
                        self.font_small, pal.text_dim, center=(cx, 172))
        self.back_button.draw(self.canvas)

        for index, rect in enumerate(self._level_rects()):
            level = self.levels[index]
            level_id = level.get("id", index + 1)
            unlocked = index == 0 or self.save.is_cleared(
                self.levels[index - 1].get("id", index))
            if unlocked:
                paint.draw_card(self.canvas, rect, 18,
                                fill_top=pal.card_top,
                                fill_bottom=pal.card_bottom,
                                border=pal.card_line, border_width=2,
                                sheen=pal.sheen, shadow=pal.card_shadow)
                color = pal.text
            else:
                # 未解锁的关卡压成一块「凹」的暗牌，一眼就能看出点不动
                paint.draw_card(self.canvas, rect, 18,
                                fill_top=pal.card_bottom,
                                fill_bottom=pal.card_bottom,
                                border=pal.surface_line, border_width=1,
                                alpha=150)
                color = pal.text_dim

            self._draw_text(str(level_id), self.font_num, color,
                            center=(rect.centerx, rect.centery - 20))
            self._draw_text(level.get("name", "").split(" ")[-1],
                            self.font_small, pal.text_dim,
                            center=(rect.centerx, rect.centery + 12))
            stars = self.save.stars_of(level_id)
            for i in range(3):
                icons.star(self.canvas,
                           (rect.centerx - 24 + i * 24, rect.bottom - 22), 18,
                           pal.text_gold if i < stars else pal.dot)

        # 底部一张进度卡：把「还差几关」做成一条进度条，顺带把下方那片
        # 空白填起来，整页的视觉重心不会全堆在标题上
        stats = pygame.Rect(cx - 190, 752, 380, 130)
        paint.draw_panel(self.canvas, stats, 20)
        total = len(self.levels)
        stars_total = sum(int(v) for v in self.save.data["stars"].values())
        self._draw_text("已通关 %d / %d 关" % (cleared, total),
                        self.font_normal, pal.text,
                        center=(cx, stats.top + 36))
        self._draw_progress_bar(
            pygame.Rect(stats.left + 40, stats.top + 62, stats.width - 80, 14),
            cleared / max(1, total))
        self._draw_text("累计 %d 星 · 金币 %d" % (stars_total, self.coins),
                        self.font_small, pal.text_dim,
                        center=(cx, stats.top + 102))

        self._draw_text("左上角返回开始页，那里还有字母玩法与随机关卡",
                        self.font_small, pal.text_dim, center=(cx, 926))

    def _draw_letter_select(self):
        """字母玩法选关：26 个字母铺成一页，不像基础玩法那样逐关解锁。"""
        pal = theme.get()
        cx = WINDOW_WIDTH // 2
        paint.blit_glow(self.canvas, (cx, 110), 260, pal.glow, 58, 2.0)
        paint.text_shadow(self.canvas, self.font_title, "字母玩法", pal.text,
                          center=(cx, 110), shadow=(6, 12, 30), alpha=130,
                          offset=(0, 3))
        done = self._cleared_count(self.letter_levels)
        self._draw_text("26 个字母各一关，随意挑一个开始",
                        self.font_small, pal.text_dim, center=(cx, 166))
        self.back_button.draw(self.canvas)

        for index, rect in enumerate(self._letter_rects()):
            level = self.letter_levels[index]
            letter = level.get("letter", level.get("id", "?"))
            stars = self.save.stars_of(level.get("id"))
            paint.draw_card(self.canvas, rect, 16, fill_top=pal.card_top,
                            fill_bottom=pal.card_bottom,
                            border=pal.card_line, border_width=2,
                            sheen=pal.sheen,
                            shadow=(10, 90, pal.card_shadow[2], 6))
            self._draw_text(letter, self.font_num, pal.text,
                            center=(rect.centerx, rect.centery - 12))
            if stars:
                for i in range(3):
                    icons.star(self.canvas,
                               (rect.centerx - 18 + i * 18,
                                rect.bottom - 18), 14,
                               pal.text_gold if i < stars else pal.dot)
            else:
                self._draw_text("未通关", self.font_small, pal.text_dim,
                                center=(rect.centerx, rect.bottom - 18))

        stats = pygame.Rect(cx - 190, 826, 380, 124)
        paint.draw_panel(self.canvas, stats, 20)
        total = len(self.letter_levels)
        stars_total = sum(self.save.stars_of(level.get("id"))
                          for level in self.letter_levels)
        self._draw_text("已通关 %d / %d 个字母" % (done, total),
                        self.font_normal, pal.text,
                        center=(cx, stats.top + 34))
        self._draw_progress_bar(
            pygame.Rect(stats.left + 40, stats.top + 58, stats.width - 80, 14),
            done / max(1, total))
        self._draw_text("已拿到 %d 颗星（共 %d 颗）" % (stars_total, total * 3),
                        self.font_small, pal.text_gold,
                        center=(cx, stats.top + 98))
        self._draw_text("左上角返回开始页 · 玩腻了可以试试随机关卡",
                        self.font_small, pal.text_dim, center=(cx, 1002))

    def _draw_overlay(self, title, stars, buttons, hint, title_color=None):
        pal = theme.get()
        veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        veil.fill(pal.veil)
        self.canvas.blit(veil, (0, 0))

        panel = pygame.Rect(0, 0, 520, 340)
        panel.center = (WINDOW_WIDTH // 2, 560)
        # 结算面板是画面里最「高」的一层：投影压得比普通卡片重一点
        paint.draw_panel(self.canvas, panel, 26, border_width=3,
                         shadow=(18, 150, pal.card_shadow[2], 14))
        # 标题上方一条渐隐的高光，像牌面顶部的一道光
        header = pygame.Rect(panel.left + 2, panel.top + 2,
                             panel.width - 4, 4)
        pygame.draw.rect(self.canvas, pal.card_line, header, border_radius=2)

        paint.text_shadow(self.canvas, self.font_big, title,
                          title_color or pal.text,
                          center=(panel.centerx, panel.top + 68),
                          shadow=(6, 12, 30), alpha=130, offset=(0, 3))
        if stars:
            for i in range(3):
                center = (panel.centerx - 56 + i * 56, panel.top + 130)
                if i < stars:
                    paint.blit_glow(self.canvas, center, 46, pal.text_gold,
                                    150, 2.0)
                icons.star(self.canvas, center, 44,
                           pal.text_gold if i < stars else pal.dot)
        paint.text_shadow(self.canvas, self.font_normal, hint, pal.text_dim,
                          center=(panel.centerx, panel.top + 196),
                          shadow=(4, 8, 20), alpha=90, offset=(0, 1))
        for button in buttons:
            button.draw(self.canvas)


def main():
    Game().run()


if __name__ == "__main__":
    main()
