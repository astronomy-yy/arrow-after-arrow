"""可复用的界面控件：文字按钮、图标按钮、日夜拨杆、滑杆、菜单面板。

所有控件只吃逻辑画布坐标（main.py 会把鼠标坐标换算好再喂进来）。

观感上统一走 game/paint.py 那套「渐变 + 细描边 + 投影」：控件要浮在背景
之上，而不是跟背景糊在一起。三种状态（常态 / 悬停 / 按下）不只是换个
颜色，悬停会提亮描边、按下会整体下沉 2 像素，手感更实。
"""

import pygame

from game import icons, paint, theme


def _shift(color, delta):
    """整体加减一个亮度（悬停提亮、按下压暗）。"""
    return tuple(max(0, min(255, c + delta)) for c in color[:3])


def _scale(color, ratio):
    return tuple(max(0, min(255, int(c * ratio))) for c in color[:3])


# --------------------------------------------------------------------------
# 基础
# --------------------------------------------------------------------------

class Button:
    """一个矩形圆角文字按钮。

    kind="primary" 是实心主按钮（蓝色渐变 + 白字），kind="ghost" 是**浅色
    纸片**（浅底 + 深字）—— 同一屏里两个按钮才不会抢眼，深浅交替也让一整列
    按钮有节奏。夜间的纸片不是纯白而是浅蓝白：深色底上纯白会亮得晃眼。
    """

    def __init__(self, center, size, text, callback, font,
                 base_color=None, hover_color=None, pressed_color=None,
                 text_color=None, radius=14, kind="primary", icon=None):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.text = text
        self.callback = callback
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.text_color = text_color
        self.radius = radius
        self.kind = kind
        # 可选图标：给了就在文字左侧画一个（game/icons.py 里的函数）
        self.icon = icon
        self.hovered = False
        self.pressed = False

    def _colors(self):
        pal = theme.get()
        ghost = self.kind == "ghost"
        top = self.base_color or (pal.ghost_top if ghost else pal.btn_top)
        bottom = pal.ghost_bottom if ghost else pal.btn_bottom
        line = pal.ghost_line if ghost else pal.btn_line
        text = self.text_color or (pal.ghost_text if ghost else pal.btn_text)
        return top, bottom, line, text

    def _style(self):
        top, bottom, line, text = self._colors()
        pal = theme.get()
        if self.pressed and self.hovered:
            top, bottom = _scale(top, 0.86), _scale(bottom, 0.86)
        elif self.hovered:
            top, bottom = _shift(top, 16), _shift(bottom, 16)
            line = pal.accent
        return top, bottom, line, text

    def handle_event(self, event):
        """处理鼠标事件；被点击时执行回调并返回 True。"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            if not self.hovered:
                self.pressed = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.hovered = True
                self.pressed = True
                if self.callback is not None:
                    self.callback()
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.pressed = False
        return False

    def draw(self, surface):
        pal = theme.get()
        top, bottom, line, text_color = self._style()
        down = self.pressed and self.hovered
        rect = self.rect.move(0, 2) if down else self.rect
        spread, alpha, color, dy = pal.card_shadow
        shadow = None if down else (max(4, spread - 4),
                                    max(30, alpha - 40), color, min(dy, 6))
        paint.draw_card(
            surface, rect, self.radius,
            fill_top=top, fill_bottom=bottom, border=line, border_width=2,
            sheen=None if self.kind == "ghost" else pal.sheen, shadow=shadow)
        # 浅色纸片上写的是深色字，再垫一层深投影只会把笔画糊掉 —— 直接实心画
        ghost = self.kind == "ghost"
        text_alpha = 0 if ghost else 90
        if self.icon is None:
            paint.text_shadow(surface, self.font, self.text, text_color,
                              center=rect.center, shadow=(4, 8, 20),
                              alpha=text_alpha, offset=(0, 1))
            return
        # 有图标时「图标 + 文字」整体居中，图标左、文字右
        label = self.font.render(self.text, True, text_color)
        icon_size = rect.height * 0.46
        gap = max(10, rect.height * 0.18)
        total = icon_size + gap + label.get_width()
        left = rect.centerx - total / 2.0
        self.icon(surface, (left + icon_size / 2.0, rect.centery), icon_size,
                  text_color)
        paint.text_shadow(
            surface, self.font, self.text, text_color,
            center=(left + icon_size + gap + label.get_width() / 2.0,
                    rect.centery),
            shadow=(4, 8, 20), alpha=text_alpha, offset=(0, 1))


class IconButton:
    """圆形 / 圆角方形图标按钮。

    icon 是 game/icons.py 里的函数，签名 (surface, center, size, color)。
    """

    def __init__(self, center, size, icon, callback=None, outlined=False,
                 icon_color=None, bg_color=None, radius=None, label=None,
                 label_font=None):
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = center
        self.icon = icon
        self.callback = callback
        self.outlined = outlined
        self.icon_color = icon_color
        self.bg_color = bg_color
        self.radius = radius if radius is not None else size // 4
        self.label = label
        self.label_font = label_font
        self.enabled = True
        self.hovered = False
        self.pressed = False

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.hovered = True
                self.pressed = True
                if self.callback is not None:
                    self.callback()
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.pressed = False
        return False

    def _icon_color(self):
        pal = theme.get()
        if not self.enabled:
            return pal.heart_lost
        if self.icon_color is not None:
            return self.icon_color
        return pal.text

    def _plate(self):
        """图标底下那块底：有 bg_color 就用它，否则用卡片的浅色玻璃。

        返回 (填充上色, 填充下色, 描边色, 玻璃透明度)；返回 None 表示不画底。
        """
        pal = theme.get()
        if self.bg_color is not None:
            base = self.bg_color
            if self.pressed and self.hovered:
                base = _scale(base, 0.86)
            elif self.hovered:
                base = _shift(base, 14)
            return _shift(base, 18), base, _shift(base, 40), 255
        if self.outlined:
            return pal.card_top, pal.card_bottom, \
                pal.accent if self.hovered else pal.card_line, 235
        if self.hovered:
            return pal.card_top, pal.card_bottom, pal.card_line, 170
        return None

    def draw(self, surface):
        pal = theme.get()
        color = self._icon_color()
        plate = self._plate()
        if plate is not None:
            top, bottom, line, alpha = plate
            shadow = None if (self.pressed and self.hovered) else \
                (10, 80, pal.card_shadow[2], 5)
            rect = self.rect.move(0, 2) if self.pressed and self.hovered \
                else self.rect
            paint.draw_card(surface, rect, self.radius, fill_top=top,
                            fill_bottom=bottom, border=line, border_width=2,
                            alpha=alpha, shadow=shadow)
        self.icon(surface, self.rect.center, self.rect.width * 0.62, color)
        if self.label and self.label_font:
            paint.text_shadow(surface, self.label_font, self.label, color,
                              center=(self.rect.centerx,
                                      self.rect.bottom + 14),
                              shadow=(4, 8, 20), alpha=90, offset=(0, 1))


class ToggleSwitch:
    """日夜拨杆：一个药丸底 + 一个滑块。

    自身不存状态，直接读当前主题 —— 不管是点拨杆、按快捷键还是脚本
    直接切主题，滑块位置和图标都一定跟画面一致。
    """

    def __init__(self, center, size, on_change=None):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.on_change = on_change
        self.hovered = False

    @property
    def is_night(self):
        """当前是否夜间主题。"""
        return theme.get().name == "night"

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.on_change is not None:
                    self.on_change()
                return True
        return False

    def draw(self, surface):
        pal = theme.get()
        base = _shift(pal.pill, 16) if self.hovered else pal.pill
        paint.draw_card(
            surface, self.rect, self.rect.height // 2,
            fill_top=_shift(base, 18), fill_bottom=_scale(base, 0.82),
            border=pal.accent if self.hovered else _shift(base, 46),
            border_width=2, alpha=225,
            shadow=(8, 70, pal.card_shadow[2], 4))
        # 轨道内圈压一道暗影，滑块才像嵌在槽里
        inner = self.rect.inflate(-8, -10)
        paint.blit_edge_fade(surface, pygame.Rect(
            inner.left, inner.top, inner.width, max(4, inner.height // 2)),
            _scale(base, 0.55), 110)

        knob_r = self.rect.height // 2 - 3
        knob_x = self.rect.right - knob_r - 4 if self.is_night \
            else self.rect.left + knob_r + 4
        knob_c = (knob_x, self.rect.centery)
        paint.blit_shadow(surface, pygame.Rect(knob_c[0] - knob_r,
                                               knob_c[1] - knob_r,
                                               knob_r * 2, knob_r * 2),
                          knob_r, spread=6, color=pal.card_shadow[2],
                          alpha=90, dy=3)
        pygame.draw.circle(surface, (255, 255, 255), knob_c, knob_r)
        pygame.draw.circle(surface, _shift(pal.slider_knob, 0), knob_c,
                           knob_r - 1)
        if self.is_night:
            icons.moon(surface, knob_c, knob_r * 1.35, (86, 112, 200))
        else:
            icons.sun(surface, knob_c, knob_r * 1.35, (247, 190, 60))


class Slider:
    """横向滑杆，value 取 0.0 ~ 1.0。"""

    def __init__(self, rect, value=0.5, on_change=None):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.on_change = on_change
        self.dragging = False
        self.hovered = False

    def _set_from_x(self, x):
        ratio = (x - self.rect.left) / max(1, self.rect.width)
        ratio = max(0.0, min(1.0, ratio))
        if abs(ratio - self.value) > 1e-4:
            self.value = ratio
            if self.on_change is not None:
                self.on_change(ratio)

    def handle_event(self, event):
        hit = self.rect.inflate(0, 22)
        if event.type == pygame.MOUSEMOTION:
            self.hovered = hit.collidepoint(event.pos)
            if self.dragging:
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hit.collidepoint(event.pos):
                self.dragging = True
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        return False

    def draw(self, surface):
        pal = theme.get()
        track = pygame.Rect(self.rect)
        track.height = 10
        track.centery = self.rect.centery
        # 轨道做成「凹槽」：底色压暗 + 上缘一道暗影
        paint.draw_card(surface, track, track.height // 2,
                        fill_top=_scale(pal.slider_track, 0.82),
                        fill_bottom=_shift(pal.slider_track, 12),
                        border=_scale(pal.slider_track, 0.62),
                        border_width=1, alpha=235)

        knob_x = track.left + track.width * self.value
        filled = pygame.Rect(track.left, track.top,
                             int(knob_x - track.left), track.height)
        if filled.width >= 6:
            # 已填充的一段：上下两半深浅不同，做出一点金属光泽。
            # 这里不走去缓存的卡片贴图 —— 拖动时宽度每帧都在变，缓存会被
            # 不停灌满然后整片清空，反倒比直接画两个圆角矩形更费。
            pygame.draw.rect(surface, _scale(pal.outline, 0.90), filled,
                             border_radius=filled.height // 2)
            upper = pygame.Rect(filled.left, filled.top, filled.width,
                                filled.height // 2 + 1)
            pygame.draw.rect(surface, _shift(pal.outline, 34), upper,
                             border_radius=filled.height // 2)

        radius = 12 if (self.hovered or self.dragging) else 11
        knob_c = (int(knob_x), track.centery)
        paint.blit_shadow(surface, pygame.Rect(knob_c[0] - radius,
                                               knob_c[1] - radius,
                                               radius * 2, radius * 2),
                          radius, spread=7, color=pal.card_shadow[2],
                          alpha=95, dy=3)
        pygame.draw.circle(surface, pal.slider_knob, knob_c, radius)
        pygame.draw.circle(surface, pal.outline, knob_c, radius, 2)


class MenuPanel:
    """一个居中的小面板，里面是若干条菜单项。"""

    def __init__(self, center, size, title, items, fonts, on_close=None):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.title = title
        self.items = items          # [(文字, 回调, 是否可用)]
        self.font_title, self.font_item = fonts
        self.on_close = on_close
        self.hover_index = -1

    def _item_rect(self, index):
        top = self.rect.top + 76 + index * 52
        return pygame.Rect(self.rect.left + 18, top, self.rect.width - 36, 44)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover_index = -1
            for index in range(len(self.items)):
                if self._item_rect(index).collidepoint(event.pos):
                    self.hover_index = index
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                if self.on_close is not None:
                    self.on_close()
                return True
            for index, item in enumerate(self.items):
                if self._item_rect(index).collidepoint(event.pos):
                    if len(item) > 2 and not item[2]:
                        return True
                    if item[1] is not None:
                        item[1]()
                    return True
        return False

    def draw(self, surface):
        pal = theme.get()
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill(pal.veil)
        surface.blit(veil, (0, 0))

        paint.draw_panel(surface, self.rect, 22)
        # 标题下方一条渐隐的分隔线，把「标题区」和「菜单项」分开
        header = pygame.Rect(self.rect.left + 26, self.rect.top + 62,
                             self.rect.width - 52, 2)
        pygame.draw.rect(surface, pal.card_line, header, border_radius=1)

        paint.text_shadow(surface, self.font_title, self.title, pal.text,
                          center=(self.rect.centerx, self.rect.top + 34),
                          shadow=(4, 8, 20), alpha=100, offset=(0, 2))

        for index, item in enumerate(self.items):
            rect = self._item_rect(index)
            usable = len(item) < 3 or item[2]
            if index == self.hover_index and usable:
                paint.draw_card(surface, rect, 12,
                                fill_top=_shift(pal.card_top, 18),
                                fill_bottom=_shift(pal.card_bottom, 18),
                                border=pal.accent, border_width=1)
                # 左侧一小段强调条，视线更容易抓住当前项
                bar = pygame.Rect(rect.left + 6, rect.top + 10, 3,
                                  rect.height - 20)
                pygame.draw.rect(surface, pal.accent, bar, border_radius=2)
            color = pal.text if usable else pal.text_dim
            paint.text_shadow(surface, self.font_item, item[0], color,
                              center=(rect.centerx, rect.centery),
                              shadow=(4, 8, 20), alpha=70, offset=(0, 1))
