"""可复用的按钮控件：支持鼠标悬停高亮与点击回调。"""

import pygame

from game.settings import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_WHITE,
)


class Button:
    """一个矩形圆角按钮。"""

    def __init__(self, center, size, text, callback, font,
                 base_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                 text_color=COLOR_WHITE):
        self.rect = pygame.Rect(0, 0, size[0], size[1])
        self.rect.center = center
        self.text = text
        self.callback = callback      # 点击时执行的函数
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.hovered = False

    def handle_event(self, event):
        """处理鼠标移动/点击；被点击时执行回调并返回 True。"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.callback is not None:
                    self.callback()
                return True
        return False

    def draw(self, surface):
        color = self.hover_color if self.hovered else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        img = self.font.render(self.text, True, self.text_color)
        surface.blit(img, img.get_rect(center=self.rect.center))
