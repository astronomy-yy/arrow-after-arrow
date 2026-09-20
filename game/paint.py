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


# --------------------------------------------------------------------------
# 艺术字：渐变填充 + 外描边 + 顶部高光 + 投影
# --------------------------------------------------------------------------

# 艺术字要放大得更多：描边是在放大后的空间里铺的，倍数越大描边越圆润
ART_SUPERSAMPLE = 3


def _disc_offsets(radius):
    """半径 radius 内所有整数偏移点，按离中心由近到远排序。

    描边就是把这个圆盘上的每个点都盖一遍。用圆盘（而不是 4 / 8 个方向）
    是为了让斜向的笔画也有足量的覆盖 —— 只铺 8 个方向的话，描边会在
    斜边上被啃出缺口。
    """
    radius = max(0, int(radius))
    points = [(dx, dy) for dy in range(-radius, radius + 1)
              for dx in range(-radius, radius + 1)
              if dx * dx + dy * dy <= radius * radius]
    points.sort(key=lambda p: (p[0] * p[0] + p[1] * p[1], p[1], p[0]))
    return points


def art_text(font, text, top, bottom=None, outline=None, outline_width=3,
             highlight=None, shadow=None, shadow_offset=(0, 4), alpha=255):
    """艺术字：竖向渐变填充 + 外描边 + 顶部高光 + 投影。

    做法是「先放大、再加工、最后缩回」：把文字渲染结果放大
    ``ART_SUPERSAMPLE`` 倍，描边在这个各向同性的空间里按圆盘铺出来
    （每处等宽、拐角不缺角），渐变与高光都拿文字的 alpha 当遮罩乘上去，
    最后缩回原尺寸 —— 描边与斜边的锯齿一并被磨平。

    返回的 surface 已经**把文字摆在正中间**，直接
    ``surface.get_rect(center=...)`` 就能摆位置。
    """
    top = rgb(top)
    bottom = rgb(bottom if bottom is not None else top)
    outline = rgb(outline) if outline else None
    highlight = rgb(highlight) if highlight else None
    shadow = rgb(shadow) if shadow else None
    outline_width = max(0, int(outline_width))
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))
    alpha = max(0, min(255, int(alpha)))
    key = ("art", font, text, top, bottom, outline, outline_width, highlight,
           shadow, shadow_offset, alpha)

    def build():
        base = font.render(text, True, (255, 255, 255))
        width, height = base.get_size()
        if width <= 0 or height <= 0:
            return pygame.Surface((1, 1), pygame.SRCALPHA)
        s = ART_SUPERSAMPLE
        # 四周留出描边 + 投影需要的余量，留白对上下左右一致，中心才对得准
        pad = outline_width + 2 + max(abs(shadow_offset[0]),
                                      abs(shadow_offset[1]))
        big = pygame.transform.smoothscale(base, (width * s, height * s))
        canvas = pygame.Surface(((width + pad * 2) * s, (height + pad * 2) * s),
                                pygame.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        origin = (pad * s, pad * s)

        def stamp(color, radius, shift=(0, 0)):
            """把文字染成 color，按 radius 铺满整个圆盘。"""
            tinted = big.copy()
            tinted.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            if radius <= 0:
                layer.blit(tinted, (origin[0] + shift[0], origin[1] + shift[1]))
                return layer
            for (dx, dy) in _disc_offsets(radius):
                layer.blit(tinted,
                           (origin[0] + shift[0] + dx,
                            origin[1] + shift[1] + dy),
                           special_flags=pygame.BLEND_RGBA_MAX)
            return layer

        if shadow:
            canvas.blit(stamp(shadow, outline_width, shadow_offset), (0, 0))
        if outline:
            canvas.blit(stamp(outline, outline_width), (0, 0))

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
