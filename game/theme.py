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
    # 次要按钮走「浅色纸片」：浅底 + 深字，跟参考图里的白卡一致。
    # 夜间背景是深色的，纯白会跳得刺眼，所以夜间用一档柔和的浅蓝白。
    ghost_top: tuple
    ghost_bottom: tuple
    ghost_line: tuple
    ghost_text: tuple
    accent: tuple          # 强调色（选中 / 悬停描边）
    # 非对局界面的柔雾：若干团互相错开的低透明度色块，
    # 每项 (x 比例, y 比例, 半径, 颜色, alpha)。对局中不用 —— 雾会压住棋盘。
    fog: tuple
    # ---- 菜单外壳（开始页 / 规则页 / 选关页）----
    # 这几页共用一层「壁纸」：薄荷底渐变 + 一层同色调的箭头暗纹。
    # 对局界面不走这套 —— 棋盘要的是安静的底子，不是纹理。
    menu_top: tuple
    menu_bottom: tuple
    pattern: tuple         # 底纹颜色
    pattern_alpha: int     # 底纹透明度（很低才像暗纹）
    # ---- 开始页那只卡通箭（吉祥物）----
    mascot_light: tuple    # 箭身渐变：上端
    mascot_dark: tuple     # 箭身渐变：下端
    mascot_line: tuple     # 外描边
    mascot_gloss: tuple    # 高光块 / 星星
    mascot_eye: tuple      # 眼白
    mascot_pupil: tuple    # 瞳孔与眉毛
    mascot_shadow: tuple   # 投影
    # ---- 艺术字（开始页标题）----
    art_top: tuple         # 字面渐变上端
    art_bottom: tuple      # 字面渐变下端
    art_outline: tuple     # 内圈描边（深色那圈）
    art_gloss: tuple       # 顶部高光
    art_edge: tuple        # 外圈描边（浅色那圈，在深色背景上把字托出来）
    art_bar_a: tuple       # 装饰横条（前一个「一」）
    art_bar_b: tuple       # 装饰横条（后一个「一」）
    art_alt_top: tuple     # 末尾那个字的字面渐变上端（换个颜色做收尾）
    art_alt_bottom: tuple  # 末尾那个字的字面渐变下端
    art_alt2_top: tuple    # 中间那个「又」的字面渐变上端（再换一色，跟前后箭都不同）
    art_alt2_bottom: tuple # 中间那个「又」的字面渐变下端


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
    btn_top=(122, 172, 250),
    btn_bottom=(78, 124, 222),
    btn_line=(46, 92, 182),
    btn_text=(255, 255, 255),
    ghost_top=(236, 241, 253),
    ghost_bottom=(206, 216, 238),
    ghost_line=(255, 255, 255),
    ghost_text=(44, 48, 74),
    accent=(120, 214, 240),
    fog=(
        (0.16, 0.09, 430, (96, 138, 232), 48),      # 左上：靛蓝
        (0.90, 0.24, 380, (152, 112, 228), 40),     # 右上：紫
        (0.08, 0.70, 420, (72, 192, 208), 30),      # 左下：青
        (0.80, 0.93, 470, (88, 120, 226), 36),      # 右下：蓝
    ),
    # 夜间不另起一套底色，只在原来的深蓝底上压一层浅色暗纹
    menu_top=(68, 74, 110),
    menu_bottom=(40, 44, 68),
    pattern=(158, 196, 255),
    pattern_alpha=26,
    mascot_light=(96, 210, 250),
    mascot_dark=(28, 108, 202),
    mascot_line=(22, 26, 44),
    mascot_gloss=(186, 248, 255),
    mascot_eye=(255, 255, 255),
    mascot_pupil=(30, 34, 52),
    mascot_shadow=(8, 10, 22),
    # 卡通贴纸配方：奶白字面 + 近黑内边 + 浅色外边（三层对比，任何底色上都清晰）
    art_top=(255, 252, 240),
    art_bottom=(238, 212, 150),
    art_outline=(30, 28, 32),
    art_gloss=(255, 255, 255),
    # 深底上外圈压成淡蓝白，纯白会亮得刺眼
    art_edge=(196, 206, 236),
    art_bar_a=(236, 84, 66),
    art_bar_b=(78, 162, 236),
    art_alt_top=(124, 212, 142),
    art_alt_bottom=(52, 158, 92),
    # 中间那个「又」用暖金色，跟奶白的「箭」、绿色的收尾「箭」都拉开，三色才不糊
    art_alt2_top=(250, 184, 96),
    art_alt2_bottom=(214, 132, 46),
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
    # 参考图的蓝按钮：亮蓝填充 + **比填充更深的**描边，卡通感就来自这圈深边
    btn_top=(78, 158, 232),
    btn_bottom=(56, 134, 214),
    btn_line=(42, 98, 182),
    btn_text=(255, 255, 255),
    ghost_top=(255, 255, 255),
    ghost_bottom=(240, 245, 254),
    ghost_line=(196, 212, 240),
    ghost_text=(42, 46, 70),
    accent=(38, 176, 164),
    fog=(
        (0.16, 0.09, 440, (152, 192, 250), 34),     # 左上：淡蓝
        (0.90, 0.24, 400, (186, 168, 246), 26),     # 右上：淡紫
        (0.08, 0.70, 430, (148, 222, 226), 22),     # 左下：淡青
        (0.80, 0.93, 470, (170, 198, 248), 26),     # 右下：淡蓝
    ),
    # 日间菜单换成薄荷底（参考图那套清爽的浅青绿），配一层同色暗纹
    menu_top=(208, 241, 239),
    menu_bottom=(173, 220, 228),
    pattern=(118, 184, 196),
    pattern_alpha=62,
    mascot_light=(92, 208, 249),
    mascot_dark=(30, 112, 206),
    mascot_line=(48, 44, 56),
    mascot_gloss=(176, 250, 255),
    mascot_eye=(255, 255, 255),
    mascot_pupil=(40, 40, 52),
    mascot_shadow=(104, 152, 172),
    # 和夜间同一套卡通贴纸配色；外圈换成奶黄，浅底上才看得出这一圈边界
    art_top=(255, 253, 244),
    art_bottom=(246, 222, 162),
    art_outline=(32, 30, 34),
    art_gloss=(255, 255, 255),
    art_edge=(255, 249, 224),
    art_bar_a=(236, 84, 66),
    art_bar_b=(78, 162, 236),
    art_alt_top=(124, 212, 142),
    art_alt_bottom=(52, 158, 92),
    art_alt2_top=(248, 178, 92),
    art_alt2_bottom=(212, 128, 44),
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
