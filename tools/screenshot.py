# -*- coding: utf-8 -*-
"""离屏渲染各界面截图，存到 assets/screenshots/。

无头运行（不弹窗口），用于写 README / 博客时贴图：
    python tools/screenshot.py
"""

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame                                   # noqa: E402

from game import theme                          # noqa: E402
from game.states import GameState               # noqa: E402
from main import Game                           # noqa: E402

OUT = os.path.join(ROOT, "assets", "screenshots")
# 截图不能碰玩家真正的存档，写到临时目录去
TMP_SAVE = os.path.join(tempfile.gettempdir(), "arrow_after_arrow_shot.json")


def shoot(game, filename):
    game._draw()
    path = os.path.join(OUT, filename)
    pygame.image.save(game.canvas, path)
    print("saved", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    # 每次从干净的临时存档开始，否则上一轮跑出来的进度会印到本轮的图上
    if os.path.exists(TMP_SAVE):
        os.remove(TMP_SAVE)
    game = Game(save_path=TMP_SAVE)

    theme.set_theme("night")
    game.state = GameState.START
    shoot(game, "start.png")

    # 规则介绍页
    game.open_rules()
    shoot(game, "rules.png")

    # 基础玩法选关
    game.open_basic_select()
    game.save.data["cleared"] = [1, 2]
    game.save.data["stars"] = {"1": 3, "2": 2}
    shoot(game, "level_select.png")

    # 字母玩法选关（先点亮几个字母，网格上才有星）
    game.save.data["cleared"] = [1, 2, "A", "B", "C", "D", "E"]
    game.save.data["stars"] = {"1": 3, "2": 2, "A": 3, "B": 2, "C": 3,
                               "D": 1, "E": 2}
    game.open_letter_select()
    shoot(game, "letter_select.png")

    # 字母关盘面：整盘铺成一个字母
    for index in (0, 12):
        game.use_track("letter")
        game.level_index = index
        level = game.letter_levels[index]
        game.level_number = level["id"]
        game._load_level(level)
        game.state = GameState.PLAYING
        game._compute_geometry()
        shoot(game, "playing_letter_%s.png" % level["letter"].lower())

    game.use_track("basic")
    shots = [(0, "playing_level1.png"), (2, "playing_level3.png"),
             (8, "playing_level9.png"), (11, "playing_level12.png")]
    for index, name in shots:
        game.level_index = index
        game.level_number = game.levels[index].get("id", index + 1)
        game._load_level(game.levels[index])
        game.state = GameState.PLAYING
        game._compute_geometry()
        shoot(game, name)

    # 飞行中的一帧：整条线沿自身折线滑出，拐角保持直角、尾迹逐格点亮
    game.level_index = 0
    game.level_number = game.levels[0].get("id", 1)
    game._load_level(game.levels[0])
    game.state = GameState.PLAYING
    flyable = game.board.flyable_arrows()
    arrow = max(flyable, key=lambda a: len(a.cells))
    game._launch(arrow)
    for _ in range(40):
        game._update(1.0 / 60)
        if game.flying and game.flying[0].t >= 2.5:
            break
    shoot(game, "playing_flying.png")

    # 放大 + 拖到一侧：验证「缩放 + 平移」联动（可见区只剩棋盘的一部分）
    game.level_index = 8
    game.level_number = game.levels[8].get("id", 9)
    game._load_level(game.levels[8])
    game.state = GameState.PLAYING
    game.on_zoom_slider(1.0)
    game.pan_by(120, 0)
    shoot(game, "playing_zoom_pan.png")
    # 后面几张图要在默认视图下拍，先复位（用 reset_view() 而不是直接改 zoom，
    # 否则底栏滑杆的滑块位置会留在最右端）
    game.reset_view()

    # 通关 / 失败界面
    game.level_index = 0
    game.level_number = game.levels[0].get("id", 1)
    game._load_level(game.levels[0])
    game.stars = 3
    game.state = GameState.LEVEL_CLEAR
    shoot(game, "level_clear.png")

    game.board.mistakes = 0
    game.state = GameState.GAME_OVER
    shoot(game, "game_over.png")

    # 菜单面板
    game.state = GameState.PLAYING
    game.open_menu()
    shoot(game, "menu.png")

    # 设置面板
    game.open_settings()
    shoot(game, "settings.png")
    game.menu = None

    # 日间主题
    if theme.get().name != "day":
        game.toggle_theme()
    game.menu = None
    game.level_index = 2
    game._load_level(game.levels[2])
    game.state = GameState.PLAYING
    shoot(game, "playing_day.png")

    # 日间主题下的结算面板（浅底遮罩是另一套参数，单独出一张核对）
    game.stars = 2
    game.state = GameState.LEVEL_CLEAR
    shoot(game, "level_clear_day.png")

    # 日间主题的规则页与字母选关：浅底上艺术字 / 胶囊是否还压得住
    game.open_rules()
    shoot(game, "rules_day.png")
    game.open_letter_select()
    shoot(game, "letter_select_day.png")

    pygame.quit()


if __name__ == "__main__":
    main()
