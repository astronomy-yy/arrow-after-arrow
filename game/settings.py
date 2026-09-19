"""全局配置：窗口、布局尺寸、箭头调色板、字体。

配色请见 game/theme.py（日间 / 夜间两套）。
"""

# 逻辑分辨率（游戏画面始终按这个尺寸渲染，再等比缩放到实际窗口）
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 1140

# 实际窗口的初始尺寸与最小尺寸（窗口边框可自由拖拽调整）
DEFAULT_WINDOW_W = 620
DEFAULT_WINDOW_H = 1000
MIN_WINDOW_W = 420
MIN_WINDOW_H = 680

FPS = 60
TITLE = "一箭又一箭"

# ---- 布局 ----
TOP_BAR_HEIGHT = 150         # 顶部 HUD 高度
BOTTOM_BAR_HEIGHT = 116      # 底部工具条高度
BOARD_MARGIN_X = 18          # 棋盘左右留白
BOARD_MARGIN_Y = 10          # 棋盘上下留白
CELL_GAP = 4                 # 格间距（决定线宽与格子的比例）
MAX_CELL_SIZE = 56

# ---- 底部工具条的控件位置（相对逻辑画布）----
COIN_CENTER = (62, WINDOW_HEIGHT - 66)
COIN_RADIUS = 26
HINT_LABEL_Y = WINDOW_HEIGHT - 22
ZOOM_OUT_CENTER = (188, WINDOW_HEIGHT - 66)
ZOOM_IN_CENTER = (470, WINDOW_HEIGHT - 66)
SLIDER_RECT = (226, WINDOW_HEIGHT - 74, 214, 16)
GUIDE_CENTER = (578, WINDOW_HEIGHT - 66)
GUIDE_LABEL_Y = WINDOW_HEIGHT - 22

# ---- 顶部 HUD 的控件位置 ----
SETTINGS_CENTER = (48, 54)
THEME_SWITCH_CENTER = (152, 54)
THEME_SWITCH_SIZE = (96, 42)
TOP_ICON_CENTERS = [(444, 54), (516, 54), (588, 54)]
TITLE_CENTER_Y = 46
HEART_CENTER_Y = 86
CLOCK_CENTER_Y = 122

# ---- 线段 ----
SEGMENT_WIDTH_RATIO = 0.26   # 线宽 / 格子边长（参考图里线偏细，格子看得见）
MIN_SEGMENT_WIDTH = 4
MAX_SEGMENT_WIDTH = 12
HINT_PULSE_SPEED = 4.5       # 提示高亮呼吸速度

# 线段箭糖果色调色板（关卡数据中的 color 为该列表索引），风格对齐参考图
ARROW_PALETTE = [
    (247, 205, 74),    # 0 金黄
    (239, 148, 88),    # 1 橙
    (235, 118, 104),   # 2 珊瑚红
    (238, 124, 176),   # 3 粉
    (186, 140, 240),   # 4 紫
    (120, 160, 240),   # 5 蓝
    (110, 200, 235),   # 6 天蓝
    (79, 195, 176),    # 7 青
    (139, 205, 110),   # 8 绿
    (168, 226, 205),   # 9 薄荷
]

# 日间主题用的同色系（浅底上要压深一档，否则发灰看不清）
ARROW_PALETTE_DAY = [
    (232, 174, 26),    # 0 金黄
    (233, 124, 46),    # 1 橙
    (222, 84, 74),     # 2 珊瑚红
    (223, 78, 152),    # 3 粉
    (146, 92, 226),    # 4 紫
    (62, 118, 224),    # 5 蓝
    (36, 160, 214),    # 6 天蓝
    (24, 162, 146),    # 7 青
    (98, 172, 60),     # 8 绿
    (46, 178, 150),    # 9 薄荷（改成青绿，避免浅底上消失）
]

# 点错后常驻的暗红标记色
WRONG_COLOR = (206, 62, 66)

# ---- 玩法 ----
MAX_HEARTS = 3               # 红心总数
HINT_COST = 1                # 提示消耗金币
SKIP_COST = 3                # 跳过关卡消耗金币
COIN_REWARD_CLEAR = 2        # 通关奖励金币
COIN_START = 10              # 初始金币
WRONG_FLASH = 0.45           # 点错时前冲弹回动画时长

# 字体
FONT_NAME = "microsoftyahei,simhei,arial"
