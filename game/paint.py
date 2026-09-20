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
    canvas = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    x = 0
    for part, ink in zip(parts, inks):
        canvas.blit(part, (x - ink.left, height - part.get_height()))
        x += ink.width + gap
    return canvas


def draw_art_banner(target, font, pieces, center, **kwargs):
    """按中心画一整条拼装标题，返回它占的 rect。"""
    image = art_banner(font, pieces, **kwargs)
    rect = image.get_rect(center=(int(center[0]), int(center[1])))
    target.blit(image, rect)
    return rect
