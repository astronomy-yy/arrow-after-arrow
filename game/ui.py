"""可复用的按钮控件：悬停高亮、按下变色与点击回调。"""

import pygame

from game.settings import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_WHITE,
)


class Button:
    """一个矩形圆角按钮。"""

    def __init__(self, center, size, text, callback, font,
                 base_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                 pressed_color=COLOR_ACCENT_PRESSED, text_color=COLOR_WHITE):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.text = text
        self.callback = callback
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.text_color = text_color
        self.hovered = False
        self.pressed = False

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
        if self.pressed and self.hovered:
            color = self.pressed_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        img = self.font.render(self.text, True, self.text_color)
        surface.blit(img, img.get_rect(center=self.rect.center))
