"""一箭又一箭（Arrow After Arrow）游戏入口。

线段箭版本：点击彩色线段，各节沿线段自身轨迹流动、再沿箭头方向飞出；
被其他线段挡住则整条变红、沿轨迹前冲后弹回，并消耗一颗心。
Esc：回到开始界面。
"""

import sys

import pygame

from game.animations import (
    TOAST_DURATION,
    BlockedFeedback,
    FlyingSegment,
)
from game.arrow import DIRECTION_DELTA, draw_segment
from game.board import Board
from game.level import LEVELS
from game.settings import (
    BOARD_TOP_MARGIN,
    BOTTOM_BAR_HEIGHT,
    CELL_GAP,
    CELL_SIZE,
    COLOR_BG,
    COLOR_DANGER,
    COLOR_DOT,
    COLOR_HEART,
    COLOR_HEART_LOST,
    COLOR_PANEL,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_NAME,
    FPS,
    SEGMENT_WIDTH,
    TITLE,
    TOP_BAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from game.states import GameState
from game.ui import Button


class Game:
    """游戏主控制器：状态、关卡、动画与主循环。"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont(FONT_NAME, 60, bold=True)
        self.font_big = pygame.font.SysFont(FONT_NAME, 36, bold=True)
        self.font_normal = pygame.font.SysFont(FONT_NAME, 26)
        self.font_small = pygame.font.SysFont(FONT_NAME, 21)

        self.state = GameState.START
        self.level_index = 0
        self.board = Board(LEVELS[self.level_index])
        self.board_x = self.board_y = 0
        self.board_pixel_w = self.board_pixel_h = 0
        self._compute_board_geometry()

        # 动画、提示、悬停
        self.flying = []
        self.blocked = []
        self.toast_text = ""
        self.toast_timer = 0.0
        self.hover_arrow = None

        # 按钮
        cx = WINDOW_WIDTH // 2
        self.start_button = Button(
            (cx, 600), (230, 66), "开始游戏", self.start_game, self.font_big
        )
        self.restart_button = Button(
            (WINDOW_WIDTH - 95, 52), (140, 44), "重新开始",
            self.restart_level, self.font_small
        )
        self.next_button = Button(
            (cx - 135, 475), (200, 58), "下一关",
            self.next_level, self.font_normal
        )
        self.retry_button = Button(
            (cx - 135, 475), (220, 58), "重新开始本关",
            self.restart_level, self.font_normal
        )
        self.home_button = Button(
            (cx + 135, 475), (180, 58), "回到开始",
            self.back_home, self.font_normal
        )
        self.home_button_single = Button(
            (cx, 475), (220, 58), "回到开始",
            self.back_home, self.font_normal
        )

    # ---------------- 状态切换 ----------------
    def start_game(self):
        self.level_index = 0
        self._load_level(0)
        self.state = GameState.PLAYING

    def next_level(self):
        if self.level_index + 1 < len(LEVELS):
            self.level_index += 1
            self._load_level(self.level_index)
            self.state = GameState.PLAYING

    def restart_level(self):
        self.board.reset()
        self._clear_effects()
        self.state = GameState.PLAYING

    def back_home(self):
        self._clear_effects()
        self.state = GameState.START

    def _load_level(self, index):
        self.board = Board(LEVELS[index])
        self._clear_effects()
        self._compute_board_geometry()

    def _clear_effects(self):
        self.flying.clear()
        self.blocked.clear()
        self.toast_text = ""
        self.toast_timer = 0.0
        self.hover_arrow = None

    # ---------------- 几何 ----------------
    def _compute_board_geometry(self):
        self.board_pixel_w = (
            self.board.cols * CELL_SIZE + (self.board.cols - 1) * CELL_GAP
        )
        self.board_pixel_h = (
            self.board.rows * CELL_SIZE + (self.board.rows - 1) * CELL_GAP
        )
        self.board_x = (WINDOW_WIDTH - self.board_pixel_w) // 2
        self.board_y = TOP_BAR_HEIGHT + BOARD_TOP_MARGIN

    def _board_rect(self):
        return pygame.Rect(self.board_x, self.board_y,
                           self.board_pixel_w, self.board_pixel_h)

    def _cell_rect(self, r, c):
        x = self.board_x + c * (CELL_SIZE + CELL_GAP)
        y = self.board_y + r * (CELL_SIZE + CELL_GAP)
        return pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

    def _grid_center(self, r, c):
        """行列（允许越界，用于路径延长线）-> 像素中心。"""
        x = self.board_x + c * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2
        y = self.board_y + r * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2
        return x, y

    def _cell_at(self, pos):
        """鼠标像素坐标 -> (行, 列)；不在格子内返回 None。"""
        x, y = pos
        if not (0 <= x - self.board_x <= self.board_pixel_w and
                0 <= y - self.board_y <= self.board_pixel_h):
            return None
        c = int((x - self.board_x) // (CELL_SIZE + CELL_GAP))
        r = int((y - self.board_y) // (CELL_SIZE + CELL_GAP))
        if 0 <= r < self.board.rows and 0 <= c < self.board.cols:
            if self._cell_rect(r, c).collidepoint(pos):
                return r, c
        return None

    def _arrow_centers(self, arrow):
        return [self._cell_rect(r, c).center for (r, c) in arrow.cells]

    def _build_route(self, arrow):
        """构造滑出像素路径：自身格子（尾 -> 头）+ 箭头方向延长线。

        返回 (route, trail_points)，trail_points 为棋盘内的路径点（残影用）。
        """
        dr, dc = DIRECTION_DELTA[arrow.direction]
        route = [self._grid_center(r, c) for (r, c) in arrow.cells]
        trail = list(route)
        rr, cc = arrow.head
        for _ in range(24):
            rr += dr
            cc += dc
            point = self._grid_center(rr, cc)
            route.append(point)
            if self.board.in_bounds(rr, cc):
                trail.append(point)
        return route, trail

    # ---------------- 鼠标交互 ----------------
    def _handle_playing_motion(self, event):
        if event.type != pygame.MOUSEMOTION:
            return
        if self.flying or self.blocked:
            self.hover_arrow = None
            return
        cell = self._cell_at(event.pos)
        self.hover_arrow = self.board.arrow_at(*cell) if cell else None

    def _handle_board_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.flying or self.blocked:
            return

        cell = self._cell_at(event.pos)
        if cell is None:
            return
        arrow = self.board.arrow_at(*cell)
        if arrow is None:
            return  # 点到空白：不扣心

        if self.board.can_fly_arrow(arrow):
            self._launch(arrow)
        else:
            self._block(arrow)

    def _launch(self, arrow):
        route, trail = self._build_route(arrow)
        self.flying.append(FlyingSegment(
            route, trail, len(arrow.cells), arrow.direction, arrow.color
        ))
        self.board.remove_arrow(arrow)
        self.hover_arrow = None

    def _block(self, arrow):
        self.board.mistakes -= 1
        route, _ = self._build_route(arrow)
        self.blocked.append(
            BlockedFeedback(route, len(arrow.cells), arrow)
        )
        self.toast_text = "被挡住了！"
        self.toast_timer = TOAST_DURATION
        self.hover_arrow = None

    # ---------------- 主循环 ----------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.back_home()
                self._dispatch_event(event)

            if self.state == GameState.PLAYING:
                self._update(dt)
            self._draw()
            pygame.display.flip()

    def _dispatch_event(self, event):
        if self.state == GameState.START:
            self.start_button.handle_event(event)
        elif self.state == GameState.PLAYING:
            self.restart_button.handle_event(event)
            self._handle_playing_motion(event)
            self._handle_board_click(event)
        elif self.state == GameState.LEVEL_CLEAR:
            self.next_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.GAME_OVER:
            self.retry_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.ALL_CLEAR:
            self.home_button_single.handle_event(event)

    def _update(self, dt):
        board_rect = self._board_rect()

        for flying in self.flying:
            flying.update(dt, board_rect)
        self.flying = [f for f in self.flying if not f.dead]

        for feedback in self.blocked:
            feedback.update(dt)
        self.blocked = [f for f in self.blocked if not f.dead]

        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        # 最后一条线段飞出后判定通关
        if not self.flying and self.board.remaining == 0:
            if self.level_index == len(LEVELS) - 1:
                self.state = GameState.ALL_CLEAR
            else:
                self.state = GameState.LEVEL_CLEAR
        # 心耗尽且弹回动画播完后判定失败
        elif self.board.mistakes <= 0 and not self.blocked:
            self.state = GameState.GAME_OVER

    # ---------------- 绘制 ----------------
    def _draw(self):
        self.screen.fill(COLOR_BG)

        if self.state == GameState.START:
            self._draw_start()
            return

        self._draw_playing_base()

        if self.state == GameState.LEVEL_CLEAR:
            self._draw_overlay(
                LEVELS[self.level_index]["name"] + " 通关！",
                COLOR_SUCCESS,
                [self.next_button, self.home_button],
                "线段已全部清空，继续下一关",
            )
        elif self.state == GameState.GAME_OVER:
            self._draw_overlay(
                "挑战失败",
                COLOR_DANGER,
                [self.retry_button, self.home_button],
                "红心已耗尽，再试一次吧",
            )
        elif self.state == GameState.ALL_CLEAR:
            self._draw_overlay(
                "全部通关！",
                COLOR_SUCCESS,
                [self.home_button_single],
                "你清空了所有关卡的线段",
            )

    def _draw_text(self, text, font, color, center=None, topleft=None):
        img = font.render(text, True, color)
        if center is not None:
            rect = img.get_rect(center=center)
        else:
            rect = img.get_rect(topleft=topleft)
        self.screen.blit(img, rect)

    def _draw_start(self):
        cx = WINDOW_WIDTH // 2
        self._draw_text("一箭又一箭", self.font_title, COLOR_TEXT,
                        center=(cx, 230))
        self._draw_text("Arrow After Arrow", self.font_normal, COLOR_TEXT_DIM,
                        center=(cx, 295))
        rules = [
            "点击彩色线段，让它沿自身轨迹从箭头方向滑出",
            "箭头方向上若有其他线段，会被弹回，消耗一颗红心",
            "清空本关全部线段即可通关，红心耗尽则失败",
        ]
        for i, line in enumerate(rules):
            self._draw_text(line, self.font_normal, COLOR_TEXT_DIM,
                            center=(cx, 380 + i * 48))
        self.start_button.draw(self.screen)
        self._draw_text("共 %d 关" % len(LEVELS), self.font_small,
                        COLOR_TEXT_DIM, center=(cx, 690))

    def _draw_heart(self, center, size, color):
        """画一个简单的心形：两个圆 + 一个三角。"""
        x, y = center
        r = size / 4
        pygame.draw.circle(self.screen, color,
                           (int(x - r), int(y - r / 2)), int(r))
        pygame.draw.circle(self.screen, color,
                           (int(x + r), int(y - r / 2)), int(r))
        pygame.draw.polygon(self.screen, color, [
            (int(x - 2 * r), int(y - r / 2.5)),
            (int(x + 2 * r), int(y - r / 2.5)),
            (int(x), int(y + 2 * r)),
        ])

    def _draw_playing_base(self):
        cx = WINDOW_WIDTH // 2

        # ---- 顶部 HUD ----
        self._draw_text(
            LEVELS[self.level_index].get("name", "第 %d 关" % (self.level_index + 1)),
            self.font_big, COLOR_TEXT, center=(cx, 34)
        )

        # 红心
        total = self.board.max_mistakes
        gap = 38
        heart_x0 = cx - (total - 1) * gap / 2
        for i in range(total):
            color = COLOR_HEART if i < self.board.mistakes else COLOR_HEART_LOST
            self._draw_heart((heart_x0 + i * gap, 80), 22, color)

        # 剩余箭数
        self._draw_text("剩余箭：%d" % self.board.remaining,
                        self.font_small, COLOR_TEXT_DIM, topleft=(28, 42))

        self.restart_button.draw(self.screen)

        # 顶部分隔线
        pygame.draw.line(self.screen, COLOR_PANEL,
                         (0, TOP_BAR_HEIGHT), (WINDOW_WIDTH, TOP_BAR_HEIGHT), 2)

        # ---- 点阵背景 ----
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                x, y = self._cell_rect(r, c).center
                pygame.draw.circle(self.screen, COLOR_DOT, (x, y), 2)

        # ---- 线段 ----
        blocked_ids = {fb.arrow_id for fb in self.blocked}
        for arrow in self.board.arrows:
            if arrow.id in blocked_ids:
                continue
            centers = self._arrow_centers(arrow)
            if self.hover_arrow is arrow:
                # 悬停提亮：先画一圈更宽的浅色底
                light = tuple(min(255, c + 55) for c in arrow.color)
                draw_segment(self.screen, centers, arrow.direction,
                             light, SEGMENT_WIDTH + 7)
            draw_segment(self.screen, centers, arrow.direction,
                         arrow.color, SEGMENT_WIDTH)

        # 碰撞反馈（红色沿轨迹前冲弹回）
        for feedback in self.blocked:
            feedback.draw(self.screen)

        # 滑出中的线段
        for flying in self.flying:
            flying.draw(self.screen)

        # ---- 底部栏（提示文字 / 后续扩展按钮位）----
        bottom_line_y = WINDOW_HEIGHT - BOTTOM_BAR_HEIGHT
        pygame.draw.line(self.screen, COLOR_PANEL,
                         (0, bottom_line_y), (WINDOW_WIDTH, bottom_line_y), 2)

        if self.toast_timer > 0:
            remain = self.toast_timer
            fade_in, fade_out = 0.12, 0.30
            if remain > TOAST_DURATION - fade_in:
                ratio = (TOAST_DURATION - remain) / fade_in
            elif remain < fade_out:
                ratio = remain / fade_out
            else:
                ratio = 1.0
            toast_img = self.font_normal.render(self.toast_text, True,
                                                COLOR_DANGER)
            toast_img.set_alpha(int(255 * ratio))
            rect = toast_img.get_rect(center=(cx, WINDOW_HEIGHT - 35))
            self.screen.blit(toast_img, rect)

    def _draw_overlay(self, title, title_color, buttons, hint):
        veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        self.screen.blit(veil, (0, 0))

        panel = pygame.Rect(0, 0, 560, 300)
        panel.center = (WINDOW_WIDTH // 2, 400)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=18)
        pygame.draw.rect(self.screen, title_color, panel, 3, border_radius=18)

        self._draw_text(title, self.font_big, title_color,
                        center=(panel.centerx, panel.top + 75))
        self._draw_text(hint, self.font_normal, COLOR_TEXT_DIM,
                        center=(panel.centerx, panel.top + 140))
        for button in buttons:
            button.draw(self.screen)


def main():
    Game().run()


if __name__ == "__main__":
    main()
