"""日间 / 夜间两套配色主题。

界面顶部的拨杆可以实时切换，所有绘制代码都通过 theme.get() 取色，
因此换主题不需要重启游戏。线段箭的调色板也走这里：关卡数据只存
颜色索引，具体色值按当前主题查表，所以切主题时箭头颜色会一起变。
"""

from dataclasses import dataclass

from game.settings import ARROW_PALETTE, ARROW_PALETTE_DAY


@dataclass(frozen=True)
class Palette:
    """一套完整配色。"""

    name: str
    bg: tuple              # 页面背景
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


NIGHT = Palette(
    name="night",
    bg=(61, 66, 95),
    board_bg=(61, 66, 95),
    panel=(48, 53, 80),
    card=(52, 57, 86),
    text=(240, 243, 252),
    text_dim=(168, 175, 205),
    text_gold=(247, 205, 74),
    outline=(78, 220, 198),
    heart=(240, 86, 102),
    heart_lost=(96, 92, 122),
    dot=(106, 112, 148),
    coin=(247, 197, 72),
    slider_track=(112, 118, 152),
    slider_knob=(240, 243, 252),
    pill=(90, 132, 214),
    danger=(236, 92, 104),
    success=(140, 214, 150),
    veil=(0, 0, 0, 165),
    trail=(150, 156, 188),
)

DAY = Palette(
    name="day",
    bg=(238, 240, 248),
    board_bg=(238, 240, 248),
    panel=(255, 255, 255),
    card=(255, 255, 255),
    text=(42, 46, 70),
    text_dim=(122, 128, 156),
    text_gold=(232, 160, 24),
    outline=(26, 160, 148),
    heart=(240, 86, 102),
    heart_lost=(206, 210, 226),
    dot=(206, 211, 226),
    coin=(247, 197, 72),
    slider_track=(210, 216, 232),
    slider_knob=(255, 255, 255),
    pill=(104, 156, 236),
    danger=(226, 78, 92),
    success=(78, 178, 106),
    veil=(255, 255, 255, 190),
    trail=(168, 174, 200),
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
