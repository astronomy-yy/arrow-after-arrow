"""全局配置：窗口、颜色、字体、棋盘布局等常量。"""

# 窗口
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 880
FPS = 60
TITLE = "一箭又一箭"

# 颜色（参考微信小游戏的深蓝紫糖果风）
COLOR_BG = (58, 63, 94)
COLOR_PANEL = (46, 50, 78)
COLOR_TEXT = (236, 239, 250)
COLOR_TEXT_DIM = (176, 182, 210)
COLOR_ACCENT = (122, 169, 248)
COLOR_ACCENT_HOVER = (102, 149, 232)
COLOR_ACCENT_PRESSED = (82, 126, 208)
COLOR_SUCCESS = (140, 214, 150)
COLOR_DANGER = (240, 96, 108)
COLOR_WHITE = (255, 255, 255)
COLOR_HEART = (240, 86, 102)
COLOR_HEART_LOST = (92, 88, 116)
COLOR_DOT = (84, 90, 122)        # 棋盘点阵背景点
COLOR_TRAIL = (150, 156, 188)    # 线段滑出后的灰色残影

# 棋盘布局
CELL_SIZE = 72
CELL_GAP = 4
TOP_BAR_HEIGHT = 110
BOARD_TOP_MARGIN = 20
BOTTOM_BAR_HEIGHT = 70

# 线段
SEGMENT_WIDTH = 18

# 线段箭糖果色调色板（关卡数据中的 color 为该列表索引）
ARROW_PALETTE = [
    (243, 139, 168),   # 粉
    (203, 166, 247),   # 紫
    (137, 180, 250),   # 蓝
    (137, 220, 199),   # 青
    (166, 229, 137),   # 绿
    (249, 226, 175),   # 浅黄
    (235, 180, 130),   # 橙
    (245, 194, 231),   # 品红
    (116, 199, 184),   # 深青
]

# 字体
FONT_NAME = "microsoftyahei,simhei,arial"
