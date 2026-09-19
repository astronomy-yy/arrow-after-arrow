"""可复用的界面控件：文字按钮、图标按钮、日夜拨杆、滑杆、菜单面板。

所有控件只吃逻辑画布坐标（main.py 会把鼠标坐标换算好再喂进来）。
"""

import pygame

from game import icons, theme


# --------------------------------------------------------------------------
# 基础
# --------------------------------------------------------------------------

class Button:
    """一个矩形圆角文字按钮。"""

    def __init__(self, center, size, text, callback, font,
                 base_color=None, hover_color=None, pressed_color=None,
                 text_color=None, radius=12):
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
        self.hovered = False
        self.pressed = False

    def _colors(self):
        pal = theme.get()
        base = self.base_color or pal.pill
        hover = self.hover_color or tuple(min(255, c + 18) for c in base)
        pressed = self.pressed_color or tuple(max(0, c - 18) for c in base)
        text = self.text_color or pal.text
        return base, hover, pressed, text

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
        base, hover, pressed, text_color = self._colors()
        if self.pressed and self.hovered:
            color = pressed
        elif self.hovered:
            color = hover
        else:
            color = base
        pygame.draw.rect(surface, color, self.rect, border_radius=self.radius)
        img = self.font.render(self.text, True, text_color)
        surface.blit(img, img.get_rect(center=self.rect.center))


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

    def draw(self, surface):
        pal = theme.get()
        color = self._icon_color()
        if self.bg_color is not None:
            bg = self.bg_color
            if self.pressed and self.hovered:
                bg = tuple(max(0, c - 14) for c in bg)
            elif self.hovered:
                bg = tuple(min(255, c + 14) for c in bg)
            pygame.draw.rect(surface, bg, self.rect, border_radius=self.radius)
        elif self.hovered:
            icons._alpha_circle(surface, pal.text_dim, self.rect.center,
                                self.rect.width // 2, 40)
        if self.outlined:
            pygame.draw.rect(surface, pal.outline, self.rect, 2,
                             border_radius=self.radius)
        self.icon(surface, self.rect.center, self.rect.width * 0.62, color)
        if self.label and self.label_font:
            img = self.label_font.render(self.label, True, color)
            surface.blit(img, img.get_rect(
                center=(self.rect.centerx, self.rect.bottom + 14)))


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
        body = self.rect.inflate(0, 0)
        pygame.draw.rect(surface, pal.pill, body,
                         border_radius=self.rect.height // 2)
        knob_r = self.rect.height // 2 - 3
        if self.is_night:
            knob_x = self.rect.right - knob_r - 4
        else:
            knob_x = self.rect.left + knob_r + 4
        knob_c = (knob_x, self.rect.centery)
        pygame.draw.circle(surface, pal.panel, knob_c, knob_r + 1)
        pygame.draw.circle(surface, (255, 255, 255), knob_c, knob_r)
        if self.is_night:
            icons.moon(surface, knob_c, knob_r * 1.35, (86, 112, 200))
        else:
            icons.sun(surface, knob_c, knob_r * 1.35, (247, 190, 60))
        if self.hovered:
            pygame.draw.rect(surface, pal.outline, body, 2,
                             border_radius=self.rect.height // 2)


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
        track.height = 8
        track.centery = self.rect.centery
        pygame.draw.rect(surface, pal.slider_track, track,
                         border_radius=track.height // 2)
        knob_x = track.left + track.width * self.value
        filled = pygame.Rect(track.left, track.top,
                             int(knob_x - track.left), track.height)
        if filled.width > 0:
            pygame.draw.rect(surface, pal.outline, filled,
                             border_radius=track.height // 2)
        radius = 11 if (self.hovered or self.dragging) else 10
        pygame.draw.circle(surface, pal.slider_knob, (int(knob_x), track.centery),
                           radius)
        pygame.draw.circle(surface, pal.outline, (int(knob_x), track.centery),
                           radius, 2)


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
        top = self.rect.top + 64 + index * 52
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
        pygame.draw.rect(surface, pal.card, self.rect, border_radius=18)
        pygame.draw.rect(surface, pal.outline, self.rect, 2, border_radius=18)
        img = self.font_title.render(self.title, True, pal.text)
        surface.blit(img, img.get_rect(
            center=(self.rect.centerx, self.rect.top + 34)))
        for index, item in enumerate(self.items):
            rect = self._item_rect(index)
            usable = len(item) < 3 or item[2]
            if index == self.hover_index and usable:
                pygame.draw.rect(surface, pal.panel, rect, border_radius=10)
            color = pal.text if usable else pal.text_dim
            label = self.font_item.render(item[0], True, color)
            surface.blit(label, label.get_rect(
                center=(rect.centerx, rect.centery)))
