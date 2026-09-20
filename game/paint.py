"""柔和绘制：渐变、柔光、投影、卡片、文字阴影。

界面原来是「一块纯色 + 一圈硬描边」，扁平得没有层次。这个模块提供几样
能立刻拉开层次的东西：

- `vertical_gradient`：整页背景的竖向渐变（上浅下深，画面不闷）；
- `radial_glow`：棋盘后方的柔光，中心亮、边缘透明，视线自然落在棋盘上；
- `soft_shadow`：圆角矩形投影，外圈浅内圈深，模拟高斯模糊；
- `card_surface`：渐变填充 + 圆角 + 细描边 + 顶部高光 + 投影，一次拿齐；
- `text_shadow`：给文字垫一层半透明偏移副本，花哨背景上也读得清。

全部按「参数 -> 预渲染贴图 -> 缓存」的套路，一帧只是几次 blit。颜色本身
是缓存 key 的一部分，所以切主题会自动换一套贴图，不需要手动清缓存。
"""

import math
from functools import lru_cache

import pygame

# 大图（卡片、面板）先按 2 倍画再缩回来：圆角与描边的锯齿一并磨掉
SUPERSAMPLE = 2

_CACHE = {}
_CACHE_LIMIT = 160


def _cached(key, build):
    value = _CACHE.get(key)
    if value is None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()
        value = _CACHE[key] = build()
    return value


def cache_size():
    """当前缓存条数（测试用）。"""
    return len(_CACHE)


def clear_cache():
    """清空缓存（切主题不必调，颜色已经是 key 的一部分）。"""
    _CACHE.clear()


def rgb(color):
    """取 rgb 三元组，alpha 一律丢掉（颜色只用来上色，不参与混合）。"""
    return tuple(int(c) for c in color[:3])


def mix(a, b, t):
    """两色线性插值，t=0 取 a、t=1 取 b。"""
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# --------------------------------------------------------------------------
# 渐变与柔光
# --------------------------------------------------------------------------

def vertical_gradient(size, top, bottom):
    """竖向渐变的整张底图（不透明，blit 走快路径）。

    先画一条 1 像素宽的色带再横向拉满 —— 逐像素算只有 height 次，
    比逐行 fill 快，也不用为横向做任何计算。
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    top, bottom = rgb(top), rgb(bottom)
    key = ("vgrad", width, height, top, bottom)

    def build():
        strip = pygame.Surface((1, height))
        for y in range(height):
            strip.set_at((0, y), mix(top, bottom, y / max(1, height - 1)))
        return pygame.transform.scale(strip, (width, height))

    return _cached(key, build)


def radial_glow(radius, color, alpha=70, softness=1.8):
    """柔光圆：中心 alpha 最亮，向外按幂函数衰减到全透明。

    先在小图上逐像素算衰减（只有 64×64 次循环），再放大 —— 放大本身就
    把阶梯抹平了，比在大图上逐像素算快两个数量级。
    """
    radius = max(1, int(radius))
    color, alpha = rgb(color), max(0, min(255, int(alpha)))
    size = radius * 2 + 2
    key = ("glow", size, color, alpha, round(float(softness), 2))

    def build():
        n = 64
        small = pygame.Surface((n, n), pygame.SRCALPHA)
        small.fill((*color, 0))
        center = (n - 1) / 2.0
        for y in range(n):
            for x in range(n):
                d = math.hypot(x - center, y - center) / center
                falloff = max(0.0, 1.0 - d) ** softness
                small.set_at((x, y), (*color, int(round(alpha * falloff))))
        return pygame.transform.smoothscale(small, (size, size))

    return _cached(key, build)


def blit_glow(surface, center, radius, color, alpha=70, softness=1.8):
    """在 center 处贴一片柔光。"""
    glow = radial_glow(radius, color, alpha, softness)
    surface.blit(glow, (int(center[0]) - glow.get_width() // 2,
                        int(center[1]) - glow.get_height() // 2))


def fog_layer(size, blobs):
    """把一组柔雾预合成成一张整屏贴图。

    每团柔光自己已经是缓存贴图了，但逐团贴仍是「四张 800+ 见方的半透明
    图」逐帧混合，一页就是 4 ms 上下。雾是**不动的**，所以干脆先合成成一张
    （结果完全一样：叠加顺序不变），之后每帧只剩一次 blit。

    `blobs` 每项是 (x 比例, y 比例, 半径, 颜色, alpha)。
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    key = ("fog", width, height,
           tuple((round(fx, 4), round(fy, 4), int(radius), rgb(color),
                  int(alpha)) for fx, fy, radius, color, alpha in blobs))

    def build():
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        for fx, fy, radius, color, alpha in blobs:
            glow = radial_glow(radius, color, alpha)
            layer.blit(glow, (int(width * fx) - glow.get_width() // 2,
                              int(height * fy) - glow.get_height() // 2))
        return layer

    return _cached(key, build)


def blit_fog(surface, size, blobs):
    """铺一整层预合成好的柔雾。"""
    surface.blit(fog_layer(size, blobs), (0, 0))


# --------------------------------------------------------------------------
# 投影
# --------------------------------------------------------------------------

def _paint_shadow(layer, rect, radius, color, alpha, spread, dy=0.0):
    """在 layer 上叠一组同心圆角矩形，越靠外越淡，得到柔和的投影。"""
    color = rgb(color)
    steps = max(1, int(spread))
    for i in range(steps, 0, -1):
        t = steps - i + 1                     # 1 → steps，越内圈越大
        level = int(alpha * (t / steps) ** 1.7)
        if level <= 0:
            continue
        ring = rect.inflate(i * 2, i * 2).move(0, dy)
        pygame.draw.rect(layer, (*color, level), ring,
                         border_radius=radius + i)


def soft_shadow(size, radius, spread=12, color=(0, 0, 0), alpha=95, dy=6):
    """一块圆角矩形投影贴图；调用方按 (left-spread, top-spread) 摆。"""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    spread = max(1, int(spread))
    dy = int(dy)
    color, alpha = rgb(color), max(0, min(255, int(alpha)))
    total = (width + spread * 2, height + spread * 2 + max(0, dy))
    key = ("shadow", width, height, radius, spread, color, alpha, dy)

    def build():
        layer = pygame.Surface(total, pygame.SRCALPHA)
        layer.fill((*color, 0))
        _paint_shadow(layer, pygame.Rect(spread, spread, width, height),
                      radius, color, alpha, spread, dy)
        return layer

    return _cached(key, build)


def blit_shadow(surface, rect, radius, spread=12, color=(0, 0, 0),
                alpha=95, dy=6):
    """把投影贴在 rect 后面（rect 本身不画东西）。"""
    layer = soft_shadow((rect.width, rect.height), radius, spread, color,
                        alpha, dy)
    surface.blit(layer, (rect.left - spread, rect.top - spread))
    return layer


def edge_fade(size, color, alpha=90, flip=False):
    """一条线性衰减的渐变条，给工具栏边缘垫一层过渡阴影。

    size 形如 (宽, 高)：高度方向从「实」渐变到「全透明」，flip=True 反向。
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    color, alpha = rgb(color), max(0, min(255, int(alpha)))
    key = ("fade", width, height, color, alpha, bool(flip))

    def build():
        strip = pygame.Surface((width, 1), pygame.SRCALPHA)
        for x in range(width):
            strip.set_at((x, 0), (*color, 0))
        ramp = pygame.Surface((1, height), pygame.SRCALPHA)
        for y in range(height):
            t = y / max(1, height - 1)
            if flip:
                t = 1.0 - t
            ramp.set_at((0, y), (*color, int(round(alpha * t))))
        return pygame.transform.smoothscale(ramp, (width, height))

    return _cached(key, build)


def blit_edge_fade(surface, rect, color, alpha=90, flip=False):
    """把渐变条贴到 rect 里（rect 决定位置与方向）。"""
    strip = edge_fade(rect.size, color, alpha, flip)
    surface.blit(strip, rect.topleft)
    return strip


# --------------------------------------------------------------------------
# 卡片：渐变填充 + 圆角 + 描边 + 顶部高光 + 投影
# --------------------------------------------------------------------------

def card_surface(size, radius, fill_top, fill_bottom=None, border=None,
                 border_width=2, sheen=None, shadow=None, alpha=255):
    """一张卡片贴图，返回 (surface, offset)。

    把 surface 贴到 `(left + offset[0], top + offset[1])`，卡片本体就正好
    落在 `(left, top, size)` 上 —— offset 是投影在四周留出的余量。

    shadow 传 `(spread, alpha, color, dy)`；不传就没投影。
    alpha < 255 时整块半透明（顶栏 / 底栏那种「玻璃」面板就用它）。
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    fill_top = rgb(fill_top)
    fill_bottom = rgb(fill_bottom if fill_bottom is not None else fill_top)
    border = rgb(border) if border else None
    sheen = rgb(sheen) if sheen else None
    shadow = (int(shadow[0]), int(shadow[1]), rgb(shadow[2]), int(shadow[3])) \
        if shadow else None
    radius = max(0, int(radius))
    border_width = max(0, int(border_width))
    alpha = max(0, min(255, int(alpha)))
    key = ("card", width, height, radius, fill_top, fill_bottom, border,
           border_width, sheen, shadow, alpha)

    def build():
        s = SUPERSAMPLE
        pad = shadow[0] if shadow else 0
        dy = shadow[3] if shadow else 0
        total = (width + pad * 2, height + pad * 2 + max(0, dy))

        body = pygame.Surface((width * s, height * s), pygame.SRCALPHA)
        # 透明处也填成填充色：缩小时取平均才不会往边上渗黑
        body.fill((*fill_top, 0))
        for y in range(height * s):
            pygame.draw.line(body,
                             (*mix(fill_top, fill_bottom,
                                   y / max(1, height * s - 1)), 255),
                             (0, y), (width * s - 1, y))

        if sheen:
            # 顶部一团柔光，模拟「光从上面打下来」
            glow = radial_glow(int(width * s * 0.60), sheen, 70, 2.4)
            body.blit(glow, (width * s // 2 - glow.get_width() // 2,
                             -glow.get_height() // 2))

        mask = pygame.Surface((width * s, height * s), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_radius=radius * s)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        if border and border_width:
            pygame.draw.rect(body, border, body.get_rect(),
                             max(1, border_width * s),
                             border_radius=radius * s)

        if alpha < 255:
            body.fill((255, 255, 255, alpha),
                      special_flags=pygame.BLEND_RGBA_MULT)

        canvas = pygame.Surface((total[0] * s, total[1] * s), pygame.SRCALPHA)
        canvas.fill((*(shadow[2] if shadow else (0, 0, 0)), 0))
        if shadow:
            spread, level, color, dy = shadow
            _paint_shadow(canvas, pygame.Rect(pad * s, pad * s,
                                              width * s, height * s),
                          radius * s, color, level, spread * s, dy * s)
        canvas.blit(body, (pad * s, pad * s))
        return pygame.transform.smoothscale(canvas, total), (-pad, -pad)

    return _cached(key, build)


def draw_card(surface, rect, radius, **kwargs):
    """按 rect 画一张卡片（渐变色 / 描边 / 高光 / 投影都从 kwargs 来）。"""
    card, offset = card_surface((rect.width, rect.height), radius, **kwargs)
    surface.blit(card, (rect.left + offset[0], rect.top + offset[1]))
    return card


def draw_panel(surface, rect, radius, theme_palette=None, **kwargs):
    """画一张「主题默认样式」的卡片：省得每处都重复填一遍配色。"""
    pal = theme_palette
    if pal is None:
        from game import theme as theme_module
        pal = theme_module.get()
    kwargs.setdefault("fill_top", pal.card_top)
    kwargs.setdefault("fill_bottom", pal.card_bottom)
    kwargs.setdefault("border", pal.card_line)
    kwargs.setdefault("sheen", pal.sheen)
    kwargs.setdefault("shadow", pal.card_shadow)
    return draw_card(surface, rect, radius, **kwargs)


# --------------------------------------------------------------------------
# 文字
# --------------------------------------------------------------------------

def text_shadow(target, font, text, color, center=None, topleft=None,
                shadow=(0, 0, 0), alpha=110, offset=(0, 2)):
    """画一行带投影的文字，返回它占的 rect。"""
    image = font.render(text, True, color)
    rect = image.get_rect(center=center) if center is not None \
        else image.get_rect(topleft=topleft)
    if alpha > 0:
        dark = font.render(text, True, rgb(shadow))
        dark.set_alpha(max(0, min(255, int(alpha))))
        target.blit(dark, (rect.left + int(offset[0]),
                           rect.top + int(offset[1])))
    target.blit(image, rect)
    return rect


_OPEN_BRACKETS = "（【《「‘“"
_CLOSE_BRACKETS = "）】》」’”"


def _word_tokens(text):
    """把一段文字切成「不该被拆开」的最小单元。

    两类单元额外照顾：

    - 连续的 ASCII（英文 / 数字 / 半角符号）算一个，"第 12 关" 因此不会折成
      "第 1" 和 "2 关"；
    - 一对全角括号连同里面的内容算一个，"缩放棋盘（也可用 - 与 =）" 会整段
      挪到下一行，而不是断在「（也」中间。
    """
    tokens, buffer, depth = [], "", 0
    for char in text:
        if depth == 0 and char in _OPEN_BRACKETS:
            if buffer:
                tokens.append(buffer)
                buffer = ""
            depth, buffer = 1, char
            continue
        if depth:
            buffer += char
            if char in _CLOSE_BRACKETS:
                depth = 0
                tokens.append(buffer)
                buffer = ""
            continue
        if char.isascii() and not char.isspace():
            buffer += char
            continue
        if buffer:
            tokens.append(buffer)
            buffer = ""
        tokens.append(char)
    if buffer:
        tokens.append(buffer)
    return tokens


# 中文排版的「避头尾」：这几个收尾标点不许出现在行首。
# ASCII 的 , . ; : ! ? 由 _word_tokens 归进前一个英文词里，不会单独落到行首。
_NO_LINE_START = "，。、；：？！）】》」』”’…·"


def _fix_punctuation(lines):
    """把落到行首的收尾标点退回上一行末尾。

    中文可以逐字断行，但标点跟着下一个字跑到行首会显得很脏。退一个字符即可，
    行数不变（上一行只可能少一个字，仍然非空）。
    """
    for index in range(1, len(lines)):
        if lines[index] and lines[index][0] in _NO_LINE_START:
            previous = lines[index - 1]
            if len(previous) > 1:
                lines[index] = previous[-1] + lines[index]
                lines[index - 1] = previous[:-1]
    return lines


def _greedy_lines(tokens, font, width):
    """贪心折行：一行里尽量多塞，塞不下就断。"""
    lines, line = [], ""
    for token in tokens:
        if line and font.size(line + token)[0] > width:
            lines.append(line)
            line = token
        else:
            line += token
    lines.append(line)
    return lines


def wrap_text(font, text, max_width, balance=True):
    """按像素宽度折行，返回行列表（至少一行）。

    中文没有词边界，逐字符试探是最省事也最准的办法：一行里多塞一个单元，
    宽了就断。`max_width` 窄到放不下单个单元时，那个单元自己独占一行 ——
    宁可这一行溢出一点，也不要把一个词从中间劈开。

    `balance=True` 会在**不增加行数**的前提下把各行宽度摊匀：中文句子常常只
    比容器宽一点点，纯贪心会折出「满满一行 + 两三个字的尾巴」，很难看。做法
    是二分一个更窄的有效宽度，取「仍折得出同样行数」的最小值 —— 行数没变，
    余量却均摊到了每一行。
    """
    max_width = max(1, int(max_width))
    result = []
    for paragraph in str(text).split("\n"):
        tokens = _word_tokens(paragraph)
        lines = _greedy_lines(tokens, font, max_width)
        if balance and len(lines) > 1:
            widest = max(font.size(token)[0] for token in tokens)
            low, high = max(1, widest), max_width
            while low <= high:
                mid = (low + high) // 2
                candidate = _greedy_lines(tokens, font, mid)
                if len(candidate) <= len(lines):
                    lines = candidate
                    high = mid - 1
                else:
                    low = mid + 1
        result.extend(_fix_punctuation(lines))
    return result


# --------------------------------------------------------------------------
# 艺术字：渐变填充 + 外描边 + 顶部高光 + 投影
# --------------------------------------------------------------------------

# 艺术字要放大得更多：描边是在放大后的空间里铺的，倍数越大描边越圆润
ART_SUPERSAMPLE = 3


@lru_cache(maxsize=64)
def _disc_offsets(radius):
    """半径 radius 内所有整数偏移点，按离中心由近到远排序。

    描边就是把这个圆盘上的每个点都盖一遍。用圆盘（而不是 4 / 8 个方向）
    是为了让斜向的笔画也有足量的覆盖 —— 只铺 8 个方向的话，描边会在
    斜边上被啃出缺口。

    只跟半径有关，直接缓存（半径 18 时是 1009 个点，每次现算不划算）。
    """
    radius = max(0, int(radius))
    points = [(dx, dy) for dy in range(-radius, radius + 1)
              for dx in range(-radius, radius + 1)
              if dx * dx + dy * dy <= radius * radius]
    points.sort(key=lambda p: (p[0] * p[0] + p[1] * p[1], p[1], p[0]))
    return points


# 描边膨胀的分辨率折扣：见 art_text.stamp 里的说明
EDGE_DOWN = 2


def art_text(font, text, top, bottom=None, outline=None, outline_width=3,
             highlight=None, shadow=None, shadow_offset=(0, 4), alpha=255,
             outline2=None, outline2_width=0, lift=0):
    """艺术字：竖向渐变填充 + 外描边 + 顶部高光 + 投影。

    做法是「先放大、再加工、最后缩回」：把文字渲染结果放大
    ``ART_SUPERSAMPLE`` 倍，描边在这个各向同性的空间里按圆盘铺出来
    （每处等宽、拐角不缺角），渐变与高光都拿文字的 alpha 当遮罩乘上去，
    最后缩回原尺寸 —— 描边与斜边的锯齿一并被磨平。

    ``outline2`` / ``outline2_width`` 是**第二圈描边**，画在 ``outline``
    外面（卡通贴纸那种「深色内边 + 浅色外边」的双层边，浅色外圈负责在
    深色背景上把字托出来）。

    ``lift`` 让描边整体**向下**偏若干像素而字面不动，底部描边于是比顶部厚，
    字看起来是浮在边上的 —— 这就是贴纸的立体感来源。单位是原始像素。

    返回的 surface 已经**把文字摆在正中间**，直接
    ``surface.get_rect(center=...)`` 就能摆位置。
    """
    top = rgb(top)
    bottom = rgb(bottom if bottom is not None else top)
    outline = rgb(outline) if outline else None
    outline2 = rgb(outline2) if outline2 else None
    highlight = rgb(highlight) if highlight else None
    shadow = rgb(shadow) if shadow else None
    outline_width = max(0, int(outline_width))
    outline2_width = max(0, int(outline2_width))
    lift = int(lift)
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))
    alpha = max(0, min(255, int(alpha)))
    key = ("art", font, text, top, bottom, outline, outline_width, outline2,
           outline2_width, lift, highlight, shadow, shadow_offset, alpha)

    def build():
        base = font.render(text, True, (255, 255, 255))
        width, height = base.get_size()
        if width <= 0 or height <= 0:
            return pygame.Surface((1, 1), pygame.SRCALPHA)
        s = ART_SUPERSAMPLE
        # 四周留出描边 + 投影需要的余量，留白对上下左右一致，中心才对得准
        pad = (outline_width + outline2_width + 2
               + max(abs(shadow_offset[0]), abs(shadow_offset[1]))
               + abs(lift))
        big = pygame.transform.smoothscale(base, (width * s, height * s))
        canvas = pygame.Surface(((width + pad * 2) * s, (height + pad * 2) * s),
                                pygame.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        origin = (pad * s, pad * s)
        # 描边层整体下移 lift 像素（放大空间里要乘 s）
        edge_shift = (0, lift * s)

        def stamp(color, radius, shift=(0, 0)):
            """把文字染成 color，按 ``radius`` 铺满整个圆盘。

            ``radius`` 与 ``shift`` 都用**超采样空间**的单位，调用处负责乘 ``s``。

            粗描边的圆盘动辄上千个偏移点，逐点 blit 整块文字很贵（半径 18 实测
            42 ms）。所以先在 1/``EDGE_DOWN`` 分辨率上膨胀：偏移点数与单点面积
            各降到 1/down²，总开销约 1/down⁴；再放大回去时边缘被插值柔化，
            对一层纯色描边来说反倒更接近抗锯齿。半径小的时候不折腾。
            """
            tinted = big.copy()
            tinted.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            size = canvas.get_size()
            if radius <= 0:
                layer = pygame.Surface(size, pygame.SRCALPHA)
                layer.blit(tinted, (origin[0] + shift[0], origin[1] + shift[1]))
                return layer
            down = EDGE_DOWN if radius >= 2 * EDGE_DOWN else 1
            if down > 1:
                small = pygame.transform.smoothscale(
                    tinted, (max(1, tinted.get_width() // down),
                             max(1, tinted.get_height() // down)))
                layer = pygame.Surface((max(1, size[0] // down),
                                        max(1, size[1] // down)), pygame.SRCALPHA)
                start = (origin[0] // down + shift[0] // down,
                         origin[1] // down + shift[1] // down)
                for (dx, dy) in _disc_offsets(max(1, int(round(radius / down)))):
                    layer.blit(small, (start[0] + dx, start[1] + dy),
                               special_flags=pygame.BLEND_RGBA_MAX)
                return pygame.transform.smoothscale(layer, size)
            layer = pygame.Surface(size, pygame.SRCALPHA)
            for (dx, dy) in _disc_offsets(radius):
                layer.blit(tinted,
                           (origin[0] + shift[0] + dx,
                            origin[1] + shift[1] + dy),
                           special_flags=pygame.BLEND_RGBA_MAX)
            return layer

        # 下面这些宽度都是**原始像素**，进 stamp 前乘 s 换成超采样空间
        if shadow:
            canvas.blit(stamp(shadow, (outline_width + outline2_width) * s,
                              (shadow_offset[0] * s, shadow_offset[1] * s)),
                        (0, 0))
        # 先铺大圆盘的外圈色，再用内圈色盖掉中间 —— 于是只看得见 outline2_width 宽
        if outline2:
            canvas.blit(stamp(outline2, (outline_width + outline2_width) * s,
                              edge_shift), (0, 0))
        if outline:
            canvas.blit(stamp(outline, outline_width * s, edge_shift), (0, 0))

        # 主体：文字的 alpha 乘上竖向渐变
        body = big.copy()
        body.blit(vertical_gradient((width * s, height * s), top, bottom),
                  (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        canvas.blit(body, origin)

        if highlight:
            # 上半部分再叠一层高光：光从上面打下来
            gloss = edge_fade((width * s, height * s), highlight, 150,
                              flip=True)
            gloss.blit(big, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            canvas.blit(gloss, origin)

        if alpha < 255:
            canvas.fill((255, 255, 255, alpha),
                        special_flags=pygame.BLEND_RGBA_MULT)
        return pygame.transform.smoothscale(
            canvas, (width + pad * 2, height + pad * 2))

    return _cached(key, build)


def draw_art_text(target, font, text, center, **kwargs):
    """按中心画一段艺术字，返回它占的 rect。"""
    image = art_text(font, text, **kwargs)
    rect = image.get_rect(center=(int(center[0]), int(center[1])))
    target.blit(image, rect)
    return rect


# --------------------------------------------------------------------------
# 胶囊横条与拼装式标题：把「一」画成一根圆头横杠，几个元素横着拼成整条标题
# --------------------------------------------------------------------------


def art_bar(width, height, color, top=None, bottom=None, outline=None,
            outline_width=0, outline2=None, outline2_width=0, highlight=None,
            shadow=None, shadow_offset=(0, 4), lift=0, alpha=255):
    """圆头横条（胶囊）：把「一」这类笔画具象成一根横杠。

    与 :func:`art_text` 共用同一套渲染栈 —— 超采样 + 双层描边 + 竖向渐变
    字面 + 顶部高光，所以横条和它旁边的字在描边粗细、立体感上完全一致。

    ``pad`` 的算法与 ``art_text`` 逐项对齐（含 ``shadow_offset`` 的余量），
    这样两者拼在一起时高度天然相等、底边一对就齐。
    """
    color = rgb(color)
    top = rgb(top if top is not None else color)
    bottom = rgb(bottom if bottom is not None else color)
    outline = rgb(outline) if outline else None
    outline2 = rgb(outline2) if outline2 else None
    highlight = rgb(highlight) if highlight else None
    shadow = rgb(shadow) if shadow else None
    outline_width = max(0, int(outline_width))
    outline2_width = max(0, int(outline2_width))
    lift = int(lift)
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))
    alpha = max(0, min(255, int(alpha)))
    width = max(1, int(width))
    height = max(2, int(height))
    key = ("bar", width, height, top, bottom, outline, outline_width, outline2,
           outline2_width, highlight, shadow, shadow_offset, lift, alpha)

    def build():
        s = ART_SUPERSAMPLE
        big_w, big_h = width * s, height * s
        radius = big_h // 2
        pad = (outline_width + outline2_width + 2
               + max(abs(shadow_offset[0]), abs(shadow_offset[1]))
               + abs(lift))
        canvas = pygame.Surface(((width + pad * 2) * s, (height + pad * 2) * s),
                                pygame.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        origin = (pad * s, pad * s)
        edge_shift = (0, lift * s)

        def capsule(extra, shift=(0, 0)):
            """半径多出 extra 像素的胶囊遮罩。"""
            layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(
                layer, (255, 255, 255, 255),
                pygame.Rect(origin[0] + shift[0] - extra * s,
                            origin[1] + shift[1] - extra * s,
                            big_w + extra * 2 * s, big_h + extra * 2 * s),
                border_radius=radius + extra * s)
            return layer

        def tinted(mask, col):
            img = mask.copy()
            img.fill((*col, 255), special_flags=pygame.BLEND_RGBA_MULT)
            return img

        if shadow:
            canvas.blit(tinted(capsule(outline_width + outline2_width,
                                       (shadow_offset[0] * s,
                                        shadow_offset[1] * s)), shadow), (0, 0))
        if outline2:
            canvas.blit(tinted(capsule(outline_width + outline2_width,
                                       edge_shift), outline2), (0, 0))
        if outline:
            canvas.blit(tinted(capsule(outline_width, edge_shift), outline),
                        (0, 0))

        # 字面：胶囊的 alpha 乘上竖向渐变
        body = capsule(0)
        grad = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        grad.blit(vertical_gradient((big_w, big_h), top, bottom), origin)
        body.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        canvas.blit(body, (0, 0))

        if highlight:
            # 上半截与胶囊求交，再叠一层浅色 —— 顶部那道反光
            upper = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(upper, (255, 255, 255, 255),
                             pygame.Rect(origin[0], origin[1], big_w, big_h // 2),
                             border_radius=radius)
            upper.blit(body, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            upper.fill((*highlight, 130), special_flags=pygame.BLEND_RGBA_MULT)
            canvas.blit(upper, (0, 0))

        if alpha < 255:
            canvas.fill((255, 255, 255, alpha),
                        special_flags=pygame.BLEND_RGBA_MULT)
        return pygame.transform.smoothscale(
            canvas, (width + pad * 2, height + pad * 2))

    return _cached(key, build)


def art_banner(font, pieces, gap=6, outline=None, outline_width=5,
               outline2=None, outline2_width=2, highlight=None, shadow=None,
               shadow_offset=(0, 6), lift=3, alpha=255):
    """把若干「字符 / 横条」横着拼成整条艺术字标题。

    ``pieces`` 里每一项是 dict：

    * ``{"kind": "text", "text": "箭", "top": ..., "bottom": ...}``
    * ``{"kind": "bar", "width": 96, "height": 30, "color": ...}``

    两处对齐都要绕开「描边留白」这个坑：

    * **横向**按每片的**墨迹边界**（``get_bounding_rect``）排布。每片四周都
      留着描边用的透明边距，直接拿 surface 宽度累加的话，两片之间会凭空多出
      ``2 × pad``（这里约 44 px）的空隙，字就散开了。
    * **纵向**按整片叠放。描边参数在所有片上取同一份，而同一字体的每个汉字
      渲染高度相同，所以各片等高，叠起来天然就是垂直居中对齐。
    """
    parts = []
    for piece in pieces:
        if piece.get("kind") == "bar":
            image = art_bar(piece["width"], piece["height"], piece["color"],
                            top=piece.get("top"), bottom=piece.get("bottom"),
                            outline=outline, outline_width=outline_width,
                            outline2=outline2, outline2_width=outline2_width,
                            highlight=highlight, shadow=shadow,
                            shadow_offset=shadow_offset, lift=lift, alpha=alpha)
        else:
            image = art_text(font, piece["text"], piece.get("top"),
                             piece.get("bottom"),
                             outline=outline, outline_width=outline_width,
                             outline2=outline2, outline2_width=outline2_width,
                             highlight=highlight, shadow=shadow,
                             shadow_offset=shadow_offset, lift=lift, alpha=alpha)
        parts.append(image)
    if not parts:
        return pygame.Surface((1, 1), pygame.SRCALPHA)
    gap = max(0, int(gap))
    inks = [part.get_bounding_rect() for part in parts]
    width = sum(ink.width for ink in inks) + gap * (len(parts) - 1)
    height = max(part.get_height() for part in parts)
    # 纵向按**墨迹中心**对齐：每一片都绕各自的墨迹中心摆，参考线取最高那一片
    # 的墨迹中心。于是矮的胶囊横条会自动落在字的中间，不再贴着字的下沿。
    # （原来按 ``height - part.get_height()`` 底边对齐，横条比字矮，就被压到了底部。）
    ref_center = 0
    for part, ink in zip(parts, inks):
        if part.get_height() == height:
            ref_center = ink.centery
            break
    canvas = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    x = 0
    for part, ink in zip(parts, inks):
        y = int(round(ref_center - ink.centery))
        canvas.blit(part, (x - ink.left, y))
        x += ink.width + gap
    return canvas


def draw_art_banner(target, font, pieces, center, **kwargs):
    """按中心画一整条拼装标题，返回它占的 rect。"""
    image = art_banner(font, pieces, **kwargs)
    rect = image.get_rect(center=(int(center[0]), int(center[1])))
    target.blit(image, rect)
    return rect


# --------------------------------------------------------------------------
# 卡通箭（开始页吉祥物）与底纹
# --------------------------------------------------------------------------

MASCOT_SUPERSAMPLE = 2
MASCOT_ASPECT = 0.62        # 箭身「高 / 宽」，标题下方那只箭的胖瘦
ARROW_CORNER = 0.13         # 箭头三个角的圆角半径，按箭身高度取比例
ARROW_SHAFT_H = 0.48        # 杆的粗细，同样按高度取比例（脸要画在杆上）
MASCOT_EYE_X = (0.16, 0.33)     # 两只眼睛中心在箭身宽上的相对位置
MASCOT_EYE_Y = 0.50             # 眼睛中心在箭身高度上的相对位置
MASCOT_SMILE_X = 0.245          # 笑（一段圆弧）的中心
MASCOT_SMILE_Y = 0.78


def _tinted(mask, color, alpha=255):
    """把一张白色遮罩染成某个颜色（顺带整体降透明度）。"""
    layer = mask.copy()
    layer.fill((*rgb(color), max(0, min(255, int(alpha)))),
               special_flags=pygame.BLEND_RGBA_MULT)
    return layer


def _capsule(surface, color, p0, p1, width):
    """粗线段 + 两端补圆 = 圆头胶囊。

    pygame 的 ``line`` 是平头（butt cap），两端各补一个圆才圆润；圆头横杠、
    眉毛这类「一笔」都用它画。
    """
    width = max(1, int(width))
    pygame.draw.line(surface, color, p0, p1, width)
    radius = max(1, width // 2)
    for point in (p0, p1):
        pygame.draw.circle(surface, color, (int(point[0]), int(point[1])),
                           radius)


def _round_polygon(surface, color, points, radius, grow=0.0):
    """圆角多边形。

    **不能**只在每个顶点画一个圆 —— 圆会鼓到边的外侧去，一个锐角三角形画出来
    像一根骨头。这里按正规做法：每个顶点沿**角平分线**内缩 d = r / tan(θ/2)
    得到两个切点，圆心落在距两边都是 r 的地方，先填「切点围成的多边形」、
    再在三个角补圆。这样圆角恰好和两条边相切，一点都不外凸。

    ``grow`` 把多边形**整体往外胖一圈**（描边用）：每个顶点沿外向角平分线挪
    ``grow / sin(θ/2)``，圆角半径同步加 ``grow`` —— 于是尖角会按比例往外伸长，
    而不是简单缩放。
    """
    points = [(float(p[0]), float(p[1])) for p in points]
    count = len(points)
    if count < 3:
        return
    if grow:
        # 先算出「往外挪」之后的顶点：外向角平分线 = -(两条边向内的单位向量之和)
        expanded = []
        for index in range(count):
            prev = points[(index - 1) % count]
            cur = points[index]
            nxt = points[(index + 1) % count]
            u = _unit(prev[0] - cur[0], prev[1] - cur[1])
            v = _unit(nxt[0] - cur[0], nxt[1] - cur[1])
            bisector = _unit(u[0] + v[0], u[1] + v[1])
            sin_half = max(0.25, math.hypot(bisector[0], bisector[1]) * 0.5)
            reach = grow / sin_half
            expanded.append((cur[0] - bisector[0] * reach,
                             cur[1] - bisector[1] * reach))
        points = expanded
        radius += grow

    radius = max(0.0, float(radius))
    if radius <= 0.5:
        pygame.draw.polygon(surface, color, points)
        return
    centres, tangents = [], []
    for index in range(count):
        prev = points[(index - 1) % count]
        cur = points[index]
        nxt = points[(index + 1) % count]
        u = _unit(prev[0] - cur[0], prev[1] - cur[1])
        v = _unit(nxt[0] - cur[0], nxt[1] - cur[1])
        cos_angle = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
        angle = math.acos(cos_angle)
        if angle < 0.05:
            centres.append(None)
            tangents.append((cur, cur))
            continue
        half = angle * 0.5
        reach = min(radius / math.tan(half),
                    math.hypot(prev[0] - cur[0], prev[1] - cur[1]) * 0.5,
                    math.hypot(nxt[0] - cur[0], nxt[1] - cur[1]) * 0.5)
        # 圆心在两条边的角平分线上，距顶点 radius / sin(half)
        bisector = _unit(u[0] + v[0], u[1] + v[1])
        centres.append((cur[0] + bisector[0] * radius / math.sin(half),
                        cur[1] + bisector[1] * radius / math.sin(half)))
        tangents.append(((cur[0] + u[0] * reach, cur[1] + u[1] * reach),
                         (cur[0] + v[0] * reach, cur[1] + v[1] * reach)))

    # 切点按「绕行顺序」连成内多边形：每个顶点贡献两个切点（先到边、后出边），
    # 相邻顶点的切点落在同一条边的那一段正是直线段。顺序错了会连成蝴蝶结。
    outline = [point for pair in tangents for point in pair]
    pygame.draw.polygon(surface, color, outline)
    for index, centre in enumerate(centres):
        if centre is None:
            continue
        pygame.draw.circle(surface, color, (int(round(centre[0])),
                                            int(round(centre[1]))),
                           int(round(radius)))


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _sparkle(surface, center, radius, color):
    """四角星（卡通高光点），``radius`` 是外圈半径。"""
    cx, cy = float(center[0]), float(center[1])
    radius = max(1.0, float(radius))
    thin = radius * 0.28
    points = []
    for index in range(8):
        angle = math.pi / 4 * index - math.pi / 2
        reach = radius if index % 2 == 0 else thin
        points.append((cx + math.cos(angle) * reach,
                       cy + math.sin(angle) * reach))
    pygame.draw.polygon(surface, color, points)


def _arrow_shape(canvas_size, box, grow=0.0):
    """一支朝右的胖箭剪影：白色实心，其余透明。

    形状 = 一根圆头短杆 + 一个大圆角三角头。``box`` 是箭身本体在画布里的
    位置与尺寸（``(x, y, w, h)``）；``grow`` 让**每个组成元素各自往外胖一圈**
    （杆变粗、三角的边也加粗、三个角的半径一起变大）。

    这一步是「描边」能做得又准又快的关键：想描边就把同一支箭按
    ``grow=描边宽`` 再画一遍填深色，不必对剪影做逐点膨胀 —— 后者在
    粗描边下动辄几千次 blit，这里始终只有五六次绘图调用。
    """
    width, height = max(2, int(canvas_size[0])), max(2, int(canvas_size[1]))
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    white = (255, 255, 255, 255)
    x, y, box_w, box_h = box
    grow = max(0.0, float(grow))

    # 杆要**够粗**：脸就画在杆上，杆细了五官就没地方放。0.60 的高度是按
    # 「两只眼睛 + 眉毛 + 一道笑」塞进去反推的，不是随手取的。
    shaft_h = box_h * ARROW_SHAFT_H + grow * 2
    shaft_y = y + box_h * 0.5
    _capsule(mask, white, (x + box_w * 0.03 - grow * 0.5, shaft_y),
             (x + box_w * 0.45 + grow * 0.5, shaft_y), shaft_h)

    head = ((x + box_w * 0.41, y + box_h * 0.02),
            (x + box_w * 0.99, y + box_h * 0.5),
            (x + box_w * 0.41, y + box_h * 0.98))
    _round_polygon(mask, white, head, max(2, int(box_h * ARROW_CORNER)),
                   grow)
    return mask


def _mascot_eye_size(box_w, box_h):
    """一只眼睛的尺寸（宽、高）。"""
    return max(4, int(round(box_w * 0.142))), max(6, int(round(box_h * 0.29)))


def _mascot_face(canvas_size, box, eye, pupil):
    """吉祥物的五官，单独画在一层上。

    五官**必须单独成层**：画好之后拿箭身剪影做一次 ``BLEND_RGBA_MULT`` 把
    多出来的部分抹掉（剪影是纯白 + 全不透明，乘上去只影响 alpha）。否则眼睛
    一歪就浮在箭身外面，而且这种「溢出」在斜着看的时候特别明显。
    """
    layer = pygame.Surface(canvas_size, pygame.SRCALPHA)
    layer.fill((0, 0, 0, 0))
    x, y, box_w, box_h = box
    eye_w, eye_h = _mascot_eye_size(box_w, box_h)
    for index, fx in enumerate(MASCOT_EYE_X):
        rect = pygame.Rect(0, 0, eye_w, eye_h)
        rect.center = (int(x + box_w * fx), int(y + box_h * MASCOT_EYE_Y))
        pygame.draw.ellipse(layer, eye, rect)
        radius = max(2, int(round(eye_w * 0.40)))
        centre = (rect.centerx + rect.width * 0.08,
                  rect.centery + rect.height * 0.06)
        pygame.draw.circle(layer, pupil, (int(centre[0]), int(centre[1])),
                           radius)
        pygame.draw.circle(
            layer, eye,
            (int(centre[0] - radius * 0.34), int(centre[1] - radius * 0.42)),
            max(1, int(radius * 0.32)))
        # 眉毛：挂在眼睛正上方，外端略高一点，才有「精神」
        brow = max(2, int(box_h * 0.050))
        _capsule(layer, pupil,
                 (rect.centerx - eye_w * 0.44, rect.top - box_h * 0.055),
                 (rect.centerx + eye_w * 0.48, rect.top - box_h * 0.100), brow)
    # 笑：一段圆弧，缺的那一块在下方，正好构成一个向下弯的嘴角
    smile = pygame.Rect(0, 0, int(box_w * 0.21), int(box_h * 0.17))
    smile.center = (int(x + box_w * MASCOT_SMILE_X),
                    int(y + box_h * MASCOT_SMILE_Y))
    pygame.draw.arc(layer, pupil, smile, math.pi * 1.10, math.pi * 1.90,
                    max(2, int(box_h * 0.045)))
    return layer


def arrow_mascot(width, light, dark, outline, gloss, eye=(255, 255, 255),
                 pupil=(40, 44, 62), tilt=-10, outline_width=6,
                 shade=None, shadow=(28, 40, 72), shadow_alpha=64,
                 shadow_offset=(3, 8)):
    """开始页标题下方那只卡通箭：胖箭 + 一张脸。

    图层顺序（全部在超采样空间里画，最后旋转 + 缩回）：

    1. **投影**：三四圈逐渐收窄、逐渐加深的剪影，错开一点贴上去，模拟模糊；
    2. **外描边**：``grow=描边宽`` 的剪影填深色；
    3. **箭身**：剪影 × 竖向渐变；
    4. **内圈暗面**：剪影 **减去**「往左上挪几像素的剪影」（``BLEND_RGBA_SUB``），
       得到贴着描边的右下那一圈，填暗色压上去 —— 参考图里那股立体感就来自
       这一圈，比再做一套渐变便宜得多；
    5. **高光块 + 四角星**：亮色块与剪影求交（``BLEND_RGBA_MIN``）；
    6. **脸**：两只眼白 + 瞳孔 + 白点 + 两道眉毛（眉毛用胶囊，一起旋转）。

    返回的 surface 已经裁到**墨迹边界**，直接 ``get_rect(center=...)`` 摆位。
    注意 ``width`` 是「旋转前」的箭身宽，倾斜之后可见范围会略宽一点。
    """
    width = max(40, int(width))
    light, dark, outline, gloss = (rgb(light), rgb(dark), rgb(outline),
                                   rgb(gloss))
    eye, pupil = rgb(eye), rgb(pupil)
    shade = rgb(shade) if shade else mix(dark, outline, 0.45)
    shadow = rgb(shadow)
    outline_width = max(0, int(outline_width))
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))
    tilt = float(tilt)
    s = MASCOT_SUPERSAMPLE
    key = ("mascot", s, width, light, dark, outline, gloss, eye, pupil, shade,
           shadow, shadow_alpha, shadow_offset, round(tilt, 2), outline_width)

    def build():
        body_w = width * s
        body_h = max(8, int(round(width * MASCOT_ASPECT)) * s)
        # 留白要装得下：三个角的圆角、描边的外扩、投影的偏移
        pad = int(body_h * 0.2) + outline_width * 2 * s \
            + abs(shadow_offset[0]) * s + 10
        canvas_size = (body_w + pad * 2, body_h + pad * 2)
        box = (pad, pad, body_w, body_h)
        grow = outline_width * s

        canvas = pygame.Surface(canvas_size, pygame.SRCALPHA)
        canvas.fill((0, 0, 0, 0))

        for extra, alpha in ((4 * s, 0.42), (2 * s, 0.66), (0, 1.0)):
            layer = _tinted(_arrow_shape(canvas_size, box, grow + extra),
                            shadow, int(shadow_alpha * alpha))
            canvas.blit(layer, (shadow_offset[0] * s, shadow_offset[1] * s))
        canvas.blit(_tinted(_arrow_shape(canvas_size, box, grow), outline),
                    (0, 0))

        body = _arrow_shape(canvas_size, box, 0)
        # 渐变要**铺满整张画布**，不能只铺在体框内：箭尾的圆头伸出体框左边，
        # 那里被乘成全透明，底下的深色描边就露出来 —— 看着像尾巴被烧黑了一块。
        # 体框内仍是原来的斜坡，框外向上取最亮、向下取最深。
        gradient = pygame.Surface(canvas_size, pygame.SRCALPHA)
        gradient.fill((*light, 255))
        gradient.blit(vertical_gradient((body_w, body_h), light, dark),
                      (0, box[1]))
        below = box[1] + body_h
        if below < canvas_size[1]:
            gradient.fill((*dark, 255),
                          pygame.Rect(0, below, canvas_size[0],
                                      canvas_size[1] - below))
        image = body.copy()
        image.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        offset = max(2, int(grow * 0.5))
        inner = _arrow_shape(
            canvas_size, (box[0] - offset, box[1] - offset, body_w, body_h), 0)
        rim = body.copy()
        rim.blit(inner, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        image.blit(_tinted(rim, shade, 150), (0, 0))

        shine = pygame.Surface(canvas_size, pygame.SRCALPHA)
        shine.fill((0, 0, 0, 0))
        for (fx, fy, fw, fh, alpha) in ((0.10, 0.10, 0.26, 0.22, 200),
                                        (0.60, 0.30, 0.22, 0.16, 130)):
            rect = pygame.Rect(0, 0, int(body_w * fw), int(body_h * fh))
            rect.center = (int(box[0] + body_w * fx + rect.width * 0.5),
                           int(box[1] + body_h * fy + rect.height * 0.5))
            pygame.draw.ellipse(shine, (255, 255, 255, alpha), rect)
        shine.blit(body, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        shine.fill((*gloss, 255), special_flags=pygame.BLEND_RGBA_MULT)
        image.blit(shine, (0, 0))
        canvas.blit(image, (0, 0))

        # ---- 脸：单独成层，用箭身剪影裁一刀，五官永远不会跑到箭身外面 ----
        face = _mascot_face(canvas_size, box, eye, pupil)
        face.blit(body, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        canvas.blit(face, (0, 0))

        # 高光星点浮在箭头附近（不参与剪影裁剪），参考图里就是这种「闪光」点缀
        for (fx, fy, size, alpha) in ((0.74, -0.03, 0.085, 220),
                                      (0.97, 0.22, 0.065, 190)):
            _sparkle(canvas, (box[0] + body_w * fx, box[1] + body_h * fy),
                     body_h * size, (255, 255, 255, alpha))

        rotated = pygame.transform.rotate(canvas, tilt)
        small = pygame.transform.smoothscale(
            rotated, (max(1, rotated.get_width() // s),
                      max(1, rotated.get_height() // s)))
        ink = small.get_bounding_rect()
        if ink.width < 1 or ink.height < 1:
            return small
        return small.subsurface(ink).copy()

    return _cached(key, build)


def pattern_layer(size, top, bottom, ink, ink_alpha=70, step=88, arrow=54,
                  tilt=0.0):
    """底纹：整屏平铺的小箭头，同色调、极低对比。

    参考图的背景是「一块浅浅的底色 + 一层几乎看不见的同色暗纹」，单靠渐变
    出不来这种「有纹理但不抢戏」的底子。这里用游戏自己的那支胖箭当图案
    （不是照抄参考图的圆角方块）：隔行错开半格、上下交替，像铺了一层壁纸。

    结果整屏预合成成**一张不透明贴图**（底色渐变也在里面），每帧只需一次
    ``blit``；`step` 是格子边长，`arrow` 是单支箭的宽。
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    step, arrow = max(12, int(step)), max(6, int(arrow))
    ink_alpha = max(0, min(255, int(ink_alpha)))
    key = ("pattern", width, height, rgb(top), rgb(bottom), rgb(ink),
           ink_alpha, step, arrow, round(float(tilt), 2))

    def build():
        layer = pygame.Surface((width, height))
        layer.blit(vertical_gradient((width, height), top, bottom), (0, 0))
        if ink_alpha <= 0:
            return layer

        s = 2
        sprite_h = max(4, int(round(arrow * MASCOT_ASPECT)))
        pad = int(sprite_h * ARROW_CORNER) + 2
        sprite = _arrow_shape((arrow * s + pad * 2, sprite_h * s + pad * 2),
                              (pad, pad, arrow * s, sprite_h * s))
        sprite = pygame.transform.smoothscale(
            sprite, (arrow + pad * 2, sprite_h + pad * 2))
        sprite = _tinted(sprite, ink, ink_alpha)
        flipped = pygame.transform.flip(sprite, False, True)

        rows = height // step + 2
        cols = width // step + 2
        for row in range(-1, rows):
            for col in range(-1, cols):
                x = col * step + (step // 2 if row % 2 else 0) - sprite.get_width() // 2
                y = row * step - sprite.get_height() // 2
                image = sprite if (row + col) % 2 == 0 else flipped
                layer.blit(image, (x, y))
        return layer

    return _cached(key, build)


def blit_pattern(surface, size, top, bottom, ink, ink_alpha=70, step=88,
                 arrow=54, tilt=0.0):
    """铺一整层预合成好的底纹（含底色渐变）。"""
    surface.blit(pattern_layer(size, top, bottom, ink, ink_alpha, step, arrow,
                               tilt), (0, 0))
