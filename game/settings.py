"""全局配置：窗口、颜色、字体、棋盘布局等常量。"""

# 窗口
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 760
FPS = 60
TITLE = "一箭又一箭"

# 颜色（柔和深色配色）
COLOR_BG = (30, 30, 46)
COLOR_PANEL = (49, 50, 68)
COLOR_CELL_A = (54, 54, 75)
COLOR_CELL_B = (49, 50, 68)
COLOR_GRID_BORDER = (88, 91, 112)
COLOR_ARROW = (249, 226, 175)
COLOR_TEXT = (205, 214, 244)
COLOR_TEXT_DIM = (166, 173, 200)
COLOR_ACCENT = (137, 180, 250)
COLOR_ACCENT_HOVER = (116, 158, 235)
COLOR_ACCENT_PRESSED = (94, 134, 208)
COLOR_SUCCESS = (166, 229, 137)
COLOR_DANGER = (243, 139, 168)
COLOR_WHITE = (255, 255, 255)

# 棋盘布局
CELL_SIZE = 84
CELL_GAP = 6
TOP_BAR_HEIGHT = 100
BOARD_TOP_MARGIN = 40

# 字体（Windows 自带微软雅黑，依次回退）
FONT_NAME = "microsoftyahei,simhei,arial"

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
