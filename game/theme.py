"""日间 / 夜间两套配色主题。

界面顶部的拨杆可以实时切换，所有绘制代码都通过 theme.get() 取色，
因此换主题不需要重启游戏。线段箭的调色板也走这里：关卡数据只存
颜色索引，具体色值按当前主题查表，所以切主题时箭头颜色会一起变。
"""

from dataclasses import dataclass

from game.settings import ARROW_PALETTE, ARROW_PALETTE_DAY


@dataclass(frozen=True)
class Palette:
    """一套完整配色。

    除了一堆单色，还有几组「成对 / 成组」的色，供 game/paint.py 画层次：

    - `bg_top` / `bg_bottom`：整页背景的竖向渐变；
    - `glow`：棋盘后方的柔光（中心亮、边缘透明）；
    - `card_top` / `card_bottom` / `card_line` / `sheen`：面板卡片的渐变、
      描边与顶部高光；`card_shadow` 是投影参数 `(spread, alpha, color, dy)`；
    - `btn_top` / `btn_bottom` / `btn_line` / `btn_text`：主按钮的渐变。
    """

    name: str
    bg: tuple              # 页面背景（渐变的中间色，兜底用）
    board_bg: tuple        # 棋盘底色（与背景一致，单独留出便于微调）
    panel: tuple           # 弹窗 / 分隔线
    card: tuple            # 卡片
    text: tuple            # 主文字
    text_dim: tuple        # 次要文字
    text_gold: tuple       # 关卡号金色
    outline: tuple         # 图标描边（青绿）
    heart: tuple           # 红心
    heart_lost: tuple      # 失去的红心
    dot: tuple             # 辅助线点阵
    coin: tuple            # 金币
    slider_track: tuple    # 滑杆轨道
    slider_knob: tuple     # 滑杆滑块
    pill: tuple            # 日夜拨杆底色
    danger: tuple
    success: tuple
    veil: tuple            # 结果界面遮罩
    trail: tuple           # 飞出残影
    rim_shade: float       # 线段外描边 = 线身色 × 这个系数
    # ---- 层次感（game/paint.py 用）----
    bg_top: tuple
    bg_bottom: tuple
    glow: tuple
    surface: tuple         # 顶栏 / 底栏的面
    surface_line: tuple    # 栏的上下分隔线
    board_top: tuple       # 棋盘面板渐变
    board_bottom: tuple
    board_line: tuple
    card_top: tuple
    card_bottom: tuple
    card_line: tuple
    sheen: tuple
    card_shadow: tuple     # (spread, alpha, color, dy)
    btn_top: tuple
    btn_bottom: tuple
    btn_line: tuple
    btn_text: tuple
    accent: tuple          # 强调色（选中 / 悬停描边）


NIGHT = Palette(
    name="night",
    bg=(56, 61, 92),
    board_bg=(56, 61, 92),
    panel=(48, 53, 80),
    card=(52, 57, 86),
    text=(240, 243, 252),
    text_dim=(168, 175, 205),
    text_gold=(247, 205, 74),
    outline=(78, 220, 198),
    heart=(240, 86, 102),
    heart_lost=(96, 92, 122),
    dot=(104, 110, 148),
    coin=(247, 197, 72),
    slider_track=(92, 98, 132),
    slider_knob=(240, 243, 252),
    pill=(90, 132, 214),
    danger=(236, 92, 104),
    success=(140, 214, 150),
    veil=(6, 8, 18, 175),
    trail=(150, 156, 188),
    # 深色底上描边要压得狠一点，线段边缘才「切」得出来
    rim_shade=0.46,
    bg_top=(68, 74, 110),
    bg_bottom=(40, 44, 68),
    glow=(96, 138, 232),
    surface=(46, 51, 78),
    surface_line=(78, 86, 124),
    board_top=(62, 68, 100),
    board_bottom=(46, 51, 78),
    board_line=(84, 92, 132),
    card_top=(66, 72, 106),
    card_bottom=(50, 55, 86),
    card_line=(96, 128, 206),
    sheen=(120, 156, 238),
    card_shadow=(16, 130, (10, 12, 24), 10),
    btn_top=(102, 152, 240),
    btn_bottom=(74, 118, 214),
    btn_line=(136, 184, 255),
    btn_text=(255, 255, 255),
    accent=(120, 214, 240),
)

DAY = Palette(
    name="day",
    bg=(238, 241, 250),
    board_bg=(238, 241, 250),
    panel=(255, 255, 255),
    card=(255, 255, 255),
    text=(42, 46, 70),
    text_dim=(122, 128, 156),
    text_gold=(232, 160, 24),
    outline=(26, 160, 148),
    heart=(240, 86, 102),
    heart_lost=(206, 210, 226),
    dot=(202, 208, 224),
    coin=(247, 197, 72),
    slider_track=(210, 216, 232),
    slider_knob=(255, 255, 255),
    pill=(104, 156, 236),
    danger=(226, 78, 92),
    success=(78, 178, 106),
    veil=(255, 255, 255, 190),
    trail=(168, 174, 200),
    # 浅色底上描边只轻轻压一档就够，压狠了整片线段会发黑发脏
    rim_shade=0.72,
    bg_top=(252, 253, 255),
    bg_bottom=(226, 232, 246),
    glow=(255, 255, 255),
    surface=(255, 255, 255),
    surface_line=(214, 221, 238),
    board_top=(255, 255, 255),
    board_bottom=(243, 246, 254),
    board_line=(204, 214, 236),
    card_top=(255, 255, 255),
    card_bottom=(243, 247, 255),
    card_line=(178, 200, 238),
    sheen=(255, 255, 255),
    card_shadow=(14, 90, (126, 140, 175), 8),
    btn_top=(124, 176, 250),
    btn_bottom=(84, 136, 226),
    btn_line=(160, 202, 255),
    btn_text=(255, 255, 255),
    accent=(38, 176, 164),
)

THEMES = {"night": NIGHT, "day": DAY}

_current = NIGHT


def get() -> Palette:
    """当前主题。"""
    return _current


def set_theme(name):
    """按名字切换主题，未知名字忽略。"""
    global _current
    if name in THEMES:
        _current = THEMES[name]
    return _current


def toggle():
    """在日间 / 夜间之间切换，返回切换后的主题。"""
    return set_theme("day" if _current.name == "night" else "night")


def arrow_palette():
    """当前主题下线段箭的调色板。"""
    return ARROW_PALETTE_DAY if _current.name == "day" else ARROW_PALETTE


def arrow_color(index):
    """按关卡里存的颜色索引取当前主题下的实际颜色。"""
    palette = arrow_palette()
    if index is None:
        index = 0
    return palette[index % len(palette)]
