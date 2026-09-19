"""一箭又一箭（Arrow After Arrow）游戏入口。

阶段 6：鼠标点击判定、飞出/碰撞动画、失误扣减、通关/失败、重新开始。
临时调试快捷键（阶段 8 删除）：
    C   模拟当前关通关
    F   模拟失败
    Esc 回到开始界面
"""

import sys

import pygame

from game.animations import (
    TOAST_DURATION,
    BlockedFeedback,
    FlyingArrow,
)
from game.arrow import draw_arrow
from game.board import Board
from game.level import LEVELS
from game.settings import (
    BOARD_TOP_MARGIN,
    CELL_GAP,
    CELL_SIZE,
    COLOR_ARROW,
    COLOR_BG,
    COLOR_CELL_A,
    COLOR_CELL_B,
    COLOR_DANGER,
    COLOR_GRID_BORDER,
    COLOR_PANEL,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    FONT_NAME,
    FPS,
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

        # 字体
        self.font_title = pygame.font.SysFont(FONT_NAME, 60, bold=True)
        self.font_big = pygame.font.SysFont(FONT_NAME, 40, bold=True)
        self.font_normal = pygame.font.SysFont(FONT_NAME, 26)
        self.font_small = pygame.font.SysFont(FONT_NAME, 21)

        # 状态与关卡
        self.state = GameState.START
        self.level_index = 0
        self.board = Board(LEVELS[self.level_index])
        self.board_x = self.board_y = 0
        self.board_pixel_w = self.board_pixel_h = 0
        self._compute_board_geometry()

        # 动画与提示
        self.flying = []        # 正在飞出的 FlyingArrow 列表
        self.blocked = []       # 被挡反馈 BlockedFeedback 列表
        self.toast_text = ""
        self.toast_timer = 0.0

        # 各界面按钮
        cx = WINDOW_WIDTH // 2
        self.start_button = Button(
            (cx, 510), (230, 66), "开始游戏", self.start_game, self.font_big
        )
        self.restart_button = Button(
            (WINDOW_WIDTH - 110, 50), (150, 46), "重新开始",
            self.restart_level, self.font_small
        )
        self.next_button = Button(
            (cx - 135, 445), (200, 58), "下一关",
            self.next_level, self.font_normal
        )
        self.retry_button = Button(
            (cx - 135, 445), (220, 58), "重新开始本关",
            self.restart_level, self.font_normal
        )
        self.home_button = Button(
            (cx + 135, 445), (180, 58), "回到开始",
            self.back_home, self.font_normal
        )
        self.home_button_single = Button(
            (cx, 445), (220, 58), "回到开始",
            self.back_home, self.font_normal
        )

    # ---------------- 状态切换动作 ----------------
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
        """清空所有动画与提示（切关、重开、回开始时调用）。"""
        self.flying.clear()
        self.blocked.clear()
        self.toast_text = ""
        self.toast_timer = 0.0

    # ---------------- 棋盘几何 ----------------
    def _compute_board_geometry(self):
        self.board_pixel_w = (
            self.board.cols * CELL_SIZE + (self.board.cols - 1) * CELL_GAP
        )
        self.board_pixel_h = (
            self.board.rows * CELL_SIZE + (self.board.rows - 1) * CELL_GAP
        )
        self.board_x = (WINDOW_WIDTH - self.board_pixel_w) // 2
        self.board_y = TOP_BAR_HEIGHT + BOARD_TOP_MARGIN

    def _cell_rect(self, r, c):
        x = self.board_x + c * (CELL_SIZE + CELL_GAP)
        y = self.board_y + r * (CELL_SIZE + CELL_GAP)
        return pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

    def _cell_at(self, pos):
        """鼠标像素坐标 -> (行, 列)；不在棋盘格子内返回 None。"""
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

    # ---------------- 点击处理 ----------------
    def _handle_board_click(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        # 动画播放期间不接受点击，避免连点造成状态混乱
        if self.flying or self.blocked:
            return

        cell = self._cell_at(event.pos)
        if cell is None:
            return
        r, c = cell

        if self.board.is_empty(r, c):
            return  # 点击空白格：不处理、不扣失误

        if self.board.can_fly(r, c):
            self._launch_arrow(r, c)
        else:
            self._block_arrow(r, c)

    def _launch_arrow(self, r, c):
        """箭头无阻挡：创建飞出动画并从网格删除。"""
        direction = self.board.get_direction(r, c)
        center = self._cell_rect(r, c).center
        self.flying.append(
            FlyingArrow(center, direction, int(CELL_SIZE * 0.6))
        )
        self.board.remove_arrow(r, c)

    def _block_arrow(self, r, c):
        """箭头被挡：不删除，失误 -1，播放反馈。"""
        self.board.mistakes -= 1
        self.blocked.append(
            BlockedFeedback(r, c, self._cell_rect(r, c),
                            self.board.get_direction(r, c))
        )
        self.toast_text = "被挡住了！"
        self.toast_timer = TOAST_DURATION

    # ---------------- 主循环 ----------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.back_home()
                    elif event.key == pygame.K_c:
                        self._debug_level_clear()
                    elif event.key == pygame.K_f:
                        if self.state == GameState.PLAYING:
                            self.board.mistakes = 0
                            self.state = GameState.GAME_OVER
                self._dispatch_event(event)

            if self.state == GameState.PLAYING:
                self._update_animations(dt)
            self._draw()
            pygame.display.flip()

    def _dispatch_event(self, event):
        if self.state == GameState.START:
            self.start_button.handle_event(event)
        elif self.state == GameState.PLAYING:
            self.restart_button.handle_event(event)
            self._handle_board_click(event)
        elif self.state == GameState.LEVEL_CLEAR:
            self.next_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.GAME_OVER:
            self.retry_button.handle_event(event)
            self.home_button.handle_event(event)
        elif self.state == GameState.ALL_CLEAR:
            self.home_button_single.handle_event(event)

    def _update_animations(self, dt):
        # 飞出动画
        for arrow in self.flying:
            arrow.update(dt)
        self.flying = [a for a in self.flying if not a.dead]

        # 碰撞反馈
        for fb in self.blocked:
            fb.update(dt)
        self.blocked = [fb for fb in self.blocked if not fb.dead]

        # 提示文字倒计时
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        # 最后一个箭头飞出屏幕后判定通关
        if not self.flying and self.board.remaining == 0:
            if self.level_index == len(LEVELS) - 1:
                self.state = GameState.ALL_CLEAR
            else:
                self.state = GameState.LEVEL_CLEAR
        # 失误耗尽且碰撞反馈播完后判定失败（让玩家看到红色反馈）
        elif self.board.mistakes <= 0 and not self.blocked:
            self.state = GameState.GAME_OVER

    def _debug_level_clear(self):
        """临时调试：模拟本关箭头全部消除。"""
        if self.state != GameState.PLAYING:
            return
        if self.level_index == len(LEVELS) - 1:
            self.state = GameState.ALL_CLEAR
        else:
            self.state = GameState.LEVEL_CLEAR

    # ---------------- 绘制 ----------------
    def _draw(self):
        self.screen.fill(COLOR_BG)

        if self.state == GameState.START:
            self._draw_start()
            return

        self._draw_playing_base()

        if self.state == GameState.LEVEL_CLEAR:
            self._draw_overlay(
                "第 %d 关通关！" % (self.level_index + 1),
                COLOR_SUCCESS,
                [self.next_button, self.home_button],
                "箭头已全部消除，继续挑战下一关",
            )
        elif self.state == GameState.GAME_OVER:
            self._draw_overlay(
                "挑战失败",
                COLOR_DANGER,
                [self.retry_button, self.home_button],
                "失误次数已耗尽，再试一次吧",
            )
        elif self.state == GameState.ALL_CLEAR:
            self._draw_overlay(
                "全部通关！",
                COLOR_SUCCESS,
                [self.home_button_single],
                "你消除了所有关卡的箭头",
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
                        center=(cx, 170))
        self._draw_text("Arrow After Arrow", self.font_normal, COLOR_TEXT_DIM,
                        center=(cx, 235))
        rules = [
            "鼠标点击箭头，让它沿自身方向飞出棋盘",
            "飞行路线上若有其他箭头，会被挡住，失误次数 -1",
            "消除本关全部箭头即可通关，失误次数耗尽则失败",
        ]
        for i, line in enumerate(rules):
            self._draw_text(line, self.font_normal, COLOR_TEXT_DIM,
                            center=(cx, 310 + i * 50))
        self.start_button.draw(self.screen)
        self._draw_text("共 %d 关" % len(LEVELS), self.font_small,
                        COLOR_TEXT_DIM, center=(cx, 600))

    def _draw_playing_base(self):
        # 顶部信息栏
        pygame.draw.rect(self.screen, COLOR_PANEL,
                         pygame.Rect(0, 0, WINDOW_WIDTH, TOP_BAR_HEIGHT))
        self._draw_text(
            "第 %d 关 / 共 %d 关" % (self.level_index + 1, len(LEVELS)),
            self.font_normal, COLOR_TEXT, topleft=(28, 16)
        )
        self._draw_text("剩余箭头：%d" % self.board.remaining,
                        self.font_normal, COLOR_TEXT, topleft=(28, 56))

        # 剩余失误：文字 + 圆点（亮色=剩余，暗色=已用掉）
        self._draw_text("剩余失误", self.font_small, COLOR_TEXT_DIM,
                        topleft=(330, 22))
        for i in range(self.board.max_mistakes):
            dot_color = COLOR_DANGER if i < self.board.mistakes else COLOR_GRID_BORDER
            pygame.draw.circle(self.screen, dot_color, (430 + i * 28, 33), 9)

        # 棋盘格子与静止箭头（正在播放碰撞反馈的箭头交给反馈对象绘制）
        blocked_cells = {(fb.r, fb.c) for fb in self.blocked}
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                rect = self._cell_rect(r, c)
                cell_color = COLOR_CELL_A if (r + c) % 2 == 0 else COLOR_CELL_B
                pygame.draw.rect(self.screen, cell_color, rect, border_radius=8)
                pygame.draw.rect(self.screen, COLOR_GRID_BORDER, rect, 1,
                                 border_radius=8)
                direction = self.board.get_direction(r, c)
                if direction is not None and (r, c) not in blocked_cells:
                    draw_arrow(self.screen, direction, rect.center,
                               int(CELL_SIZE * 0.6), COLOR_ARROW)

        # 碰撞反馈（红色晃动箭头）
        for fb in self.blocked:
            fb.draw(self.screen)

        # 飞出中的箭头（最上层）
        for arrow in self.flying:
            arrow.draw(self.screen)

        # “被挡住了！”提示
        if self.toast_timer > 0:
            self._draw_text(self.toast_text, self.font_normal, COLOR_DANGER,
                            center=(WINDOW_WIDTH // 2, self.board_y - 14))

        # 右上角重新开始按钮
        self.restart_button.draw(self.screen)

        # 底部调试提示（阶段 8 删除）
        self._draw_text("开发预览：C 模拟通关　F 模拟失败　Esc 回到开始",
                        self.font_small, COLOR_TEXT_DIM,
                        center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 28))

    def _draw_overlay(self, title, title_color, buttons, hint):
        """在游戏画面上覆盖半透明结果面板。"""
        veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 160))
        self.screen.blit(veil, (0, 0))

        panel = pygame.Rect(0, 0, 560, 300)
        panel.center = (WINDOW_WIDTH // 2, 360)
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
