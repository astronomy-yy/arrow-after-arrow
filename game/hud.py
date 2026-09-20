"""顶部信息栏 + 底部工具条，照着参考图 / 录屏的版式复刻。

顶栏从左到右：设置齿轮、日夜拨杆、关卡标题与金色关卡号、红心、
时钟倒计时，右侧是手柄、省略号菜单、关卡选择靶心。
底栏从左到右：金币提示、缩放滑杆、辅助线开关。
"""

import pygame

from game import icons, paint, theme
from game.settings import (
    CLOCK_CENTER_Y,
    COIN_CENTER,
    COIN_RADIUS,
    GUIDE_CENTER,
    GUIDE_LABEL_Y,
    HEART_CENTER_Y,
    HINT_LABEL_Y,
    SETTINGS_CENTER,
    SLIDER_RECT,
    THEME_SWITCH_CENTER,
    THEME_SWITCH_SIZE,
    TITLE_CENTER_Y,
    TOP_BAR_HEIGHT,
    TOP_ICON_CENTERS,
    BOTTOM_BAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZOOM_IN_CENTER,
    ZOOM_OUT_CENTER,
)
from game.ui import IconButton, Slider, ToggleSwitch

HEART_GAP = 30
HEART_SIZE = 22
RIGHT_ICON_SIZE = 44
LEFT_ICON_SIZE = 50


class Hud:
    """负责画顶栏 / 底栏，并把控件事件转成回调。"""

    def __init__(self, fonts, callbacks):
        self.font_title, self.font_normal, self.font_small = fonts
        self.callbacks = callbacks

        self.settings_button = IconButton(
            SETTINGS_CENTER, LEFT_ICON_SIZE, icons.gear,
            callbacks.get("settings"), outlined=True, radius=14)
        self.theme_switch = ToggleSwitch(
            THEME_SWITCH_CENTER, THEME_SWITCH_SIZE,
            on_change=callbacks.get("theme"))

        self.skip_button = IconButton(
            TOP_ICON_CENTERS[0], RIGHT_ICON_SIZE, icons.controller,
            callbacks.get("skip"), radius=12)
        self.menu_button = IconButton(
            TOP_ICON_CENTERS[1], RIGHT_ICON_SIZE, icons.dots,
            callbacks.get("menu"), radius=12)
        self.select_button = IconButton(
            TOP_ICON_CENTERS[2], RIGHT_ICON_SIZE, icons.target,
            callbacks.get("select"), radius=12)

        # 提示按钮的图标就是那枚金币，由 draw_bottom 单独画
        self.hint_button = _BottomButton(
            COIN_CENTER, COIN_RADIUS, None, callbacks.get("hint"), "提示",
            HINT_LABEL_Y, self.font_small)
        self.guide_button = _BottomButton(
            GUIDE_CENTER, 24, icons.hash_sign, callbacks.get("guide"),
            "辅助线", GUIDE_LABEL_Y, self.font_small)

        self.zoom_out_button = IconButton(
            ZOOM_OUT_CENTER, 42, lambda s, c, sz, col:
            icons.magnifier(s, c, sz, col, plus=False),
            callbacks.get("zoom_out"), radius=10, icon_color=None)
        self.zoom_in_button = IconButton(
            ZOOM_IN_CENTER, 42, lambda s, c, sz, col:
            icons.magnifier(s, c, sz, col, plus=True),
            callbacks.get("zoom_in"), radius=10)
        self.zoom_slider = Slider(SLIDER_RECT, 0.0, callbacks.get("zoom"))

    # ---------------- 事件 ----------------

    def handle_event(self, event):
        for widget in self.widgets():
            if widget.handle_event(event):
                return True
        return False

    def widgets(self):
        return [
            self.settings_button, self.theme_switch, self.skip_button,
            self.menu_button, self.select_button, self.hint_button,
            self.guide_button, self.zoom_out_button, self.zoom_in_button,
            self.zoom_slider,
        ]

    # ---------------- 绘制 ----------------

    def draw_top(self, surface, info):
        pal = theme.get()
        # 栏面是一层半透明「玻璃」：棋盘铺到底下时还透得出来一点，
        # 但字和图标始终有对比度。栏下再垫一道渐隐阴影，盘面和栏才分得开。
        bar = pygame.Rect(0, 0, WINDOW_WIDTH, TOP_BAR_HEIGHT)
        paint.draw_card(surface, bar, 0, fill_top=pal.surface,
                        fill_bottom=pal.surface, alpha=208)
        paint.blit_edge_fade(surface,
                            pygame.Rect(0, TOP_BAR_HEIGHT, WINDOW_WIDTH, 16),
                            pal.card_shadow[2], 78)
        pygame.draw.line(surface, pal.surface_line, (0, TOP_BAR_HEIGHT - 1),
                         (WINDOW_WIDTH, TOP_BAR_HEIGHT - 1), 1)

        self.settings_button.draw(surface)
        self.theme_switch.draw(surface)

        if info.is_random:
            # 随机关卡：不跟基础 / 字母关连号，顶栏就叫「随机关卡」
            label = self.font_title.render("随机关卡", True, pal.text_gold)
            rect = label.get_rect(center=(WINDOW_WIDTH // 2, TITLE_CENTER_Y))
            paint.text_shadow(surface, self.font_title, "随机关卡",
                              pal.text_gold, center=rect.center,
                              shadow=(58, 34, 4), alpha=120)
        else:
            title = self.font_title.render("关卡", True, pal.text)
            number = self.font_title.render(str(info.level_number), True,
                                            pal.text_gold)
            total = title.get_width() + number.get_width()
            x = (WINDOW_WIDTH - total) // 2
            rect = title.get_rect(midleft=(x, TITLE_CENTER_Y))
            paint.text_shadow(surface, self.font_title, "关卡", pal.text,
                              center=rect.center, shadow=(4, 8, 20), alpha=110)
            number_rect = number.get_rect(
                midleft=(x + title.get_width(), TITLE_CENTER_Y))
            paint.text_shadow(surface, self.font_title,
                              str(info.level_number), pal.text_gold,
                              center=number_rect.center, shadow=(58, 34, 4),
                              alpha=120)

        # 红心
        filled = info.hearts
        total_hearts = info.max_hearts
        heart_x0 = WINDOW_WIDTH // 2 - (total_hearts - 1) * HEART_GAP / 2
        for index in range(total_hearts):
            color = pal.heart if index < filled else pal.heart_lost
            center = (heart_x0 + index * HEART_GAP, HEART_CENTER_Y)
            if index < filled:
                paint.blit_shadow(surface, pygame.Rect(center[0] - 10,
                                                       center[1] - 9, 20, 18),
                                  9, spread=5, color=pal.card_shadow[2],
                                  alpha=105, dy=3)
            icons.heart(surface, center, HEART_SIZE, color)

        # 时钟 + 倒计时
        clock_c = (WINDOW_WIDTH // 2 - 46, CLOCK_CENTER_Y)
        icons.clock(surface, clock_c, 20, pal.text)
        paint.text_shadow(surface, self.font_normal,
                          _format_time(info.time_left), pal.text,
                          center=(clock_c[0] + 16 + 26, CLOCK_CENTER_Y),
                          shadow=(4, 8, 20), alpha=100)

        self.skip_button.draw(surface)
        self.menu_button.draw(surface)
        self.select_button.draw(surface)

        if info.toast and info.toast_ratio > 0:
            img = self.font_normal.render(info.toast, True, pal.danger)
            img.set_alpha(int(255 * info.toast_ratio))
            surface.blit(img, img.get_rect(
                center=(WINDOW_WIDTH // 2, TOP_BAR_HEIGHT + 26)))

    def draw_bottom(self, surface, info):
        pal = theme.get()
        top = WINDOW_HEIGHT - BOTTOM_BAR_HEIGHT
        bar = pygame.Rect(0, top, WINDOW_WIDTH, BOTTOM_BAR_HEIGHT)
        paint.draw_card(surface, bar, 0, fill_top=pal.surface,
                        fill_bottom=pal.surface, alpha=208)
        edge = pygame.Rect(0, top - 16, WINDOW_WIDTH, 16)
        paint.blit_edge_fade(surface, edge, pal.card_shadow[2], 78, flip=True)
        pygame.draw.line(surface, pal.surface_line, (0, top),
                         (WINDOW_WIDTH, top), 1)

        # 金币 + 提示
        paint.blit_shadow(surface, pygame.Rect(COIN_CENTER[0] - 22,
                                               COIN_CENTER[1] - 20, 44, 36),
                          20, spread=8, color=pal.card_shadow[2],
                          alpha=110, dy=5)
        icons.coin(surface, COIN_CENTER, COIN_RADIUS, pal.coin)
        icons.plus_badge(surface, (COIN_CENTER[0] - COIN_RADIUS + 3,
                                   COIN_CENTER[1] - COIN_RADIUS - 1),
                         8, pal.outline, pal.surface)
        coin_text = self.font_small.render(str(info.coins), True,
                                           (110, 76, 12))
        surface.blit(coin_text, coin_text.get_rect(
            center=(COIN_CENTER[0], COIN_CENTER[1] - 1)))
        self.hint_button.draw(surface)

        # 缩放
        self.zoom_out_button.draw(surface)
        self.zoom_in_button.draw(surface)
        self.zoom_slider.draw(surface)

        # 辅助线
        self.guide_button.draw(surface)
        icons.plus_badge(surface, (GUIDE_CENTER[0] + 19, GUIDE_CENTER[1] - 22),
                         8, pal.outline if info.guide else pal.text_dim,
                         pal.surface)


class _BottomButton:
    """底栏那种「图标 + 角标 + 文字」的组合按钮。"""

    def __init__(self, center, radius, icon, callback, label, label_y, font):
        self.rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        self.rect.center = center
        self.radius = radius
        self.icon = icon
        self.callback = callback
        self.label = label
        self.label_y = label_y
        self.font = font
        self.hovered = False

    def handle_event(self, event):
        hit = pygame.Rect(0, 0, self.radius * 2 + 16,
                          self.radius * 2 + 16 + 26)
        hit.center = (self.rect.centerx, self.rect.centery + 10)
        if event.type == pygame.MOUSEMOTION:
            self.hovered = hit.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hit.collidepoint(event.pos):
                if self.callback is not None:
                    self.callback()
                return True
        return False

    def draw(self, surface):
        pal = theme.get()
        if self.icon is not None:
            if self.hovered:
                paint.draw_card(surface, self.rect.inflate(14, 14),
                                self.radius, fill_top=pal.card_top,
                                fill_bottom=pal.card_bottom,
                                border=pal.accent, border_width=1, alpha=150)
            self.icon(surface, self.rect.center, self.radius * 1.8,
                      pal.text_dim if not self.hovered else pal.text)
        paint.text_shadow(surface, self.font, self.label,
                          pal.text if self.hovered else pal.text_dim,
                          center=(self.rect.centerx, self.label_y),
                          shadow=(4, 8, 20), alpha=90, offset=(0, 1))


def _format_time(seconds):
    seconds = max(0, int(seconds))
    return "%02d:%02d" % (seconds // 60, seconds % 60)
