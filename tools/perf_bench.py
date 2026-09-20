"""性能基准：量各界面稳态的整帧耗时（不进入版本库）。

界面美化加了一堆缓存贴图（渐变、投影、艺术字），这个脚本用来确认
「好看」没有把渲染拖垮 —— 60 FPS 的预算是 16.7 ms/帧。

用法（项目根目录）：python tools/perf_bench.py
"""

import os
import statistics
import sys
import tempfile
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game import theme                            # noqa: E402
from game.states import GameState                 # noqa: E402
from main import Game                             # noqa: E402

TMP = os.path.join(tempfile.gettempdir(), "aaa_perf.json")
if os.path.exists(TMP):
    os.remove(TMP)

game = Game(save_path=TMP)
theme.set_theme("night")


def bench(label, frames=90):
    for _ in range(10):                      # 先热一轮，把贴图缓存建起来
        game._draw()
    times = []
    for _ in range(frames):
        start = time.perf_counter()
        game._draw()
        times.append(time.perf_counter() - start)
    print("%-18s 中位 %5.2f ms   最大 %5.2f ms"
          % (label, statistics.median(times) * 1000, max(times) * 1000))


game.state = GameState.START
game._draw()
bench("开始页（艺术字）")

game.open_rules()
game._draw()
bench("规则页")

game.open_basic_select()
game._draw()
bench("基础选关")

game.open_letter_select()
game._draw()
bench("字母选关")

# 字母关：A 是 26 个里比较满的一档
game.use_track("letter")
game.select_level(0)
game.state = GameState.PLAYING
game._draw()
bench("字母 A 关 静态")

flyable = game.board.flyable_arrows()
if flyable:
    game._launch(max(flyable, key=lambda a: len(a.cells)))
    for _ in range(20):
        game._update(1.0 / 60)
    bench("字母 A 关 飞行中")

game.use_track("basic")
game.start_game()
game._load_level(game.levels[0])
game.state = GameState.PLAYING
game._draw()
bench("第1关 静态")

game._load_level(game.levels[11])
game.state = GameState.PLAYING
game._draw()
bench("第12关 静态")

flyable = game.board.flyable_arrows()
if flyable:
    game._launch(max(flyable, key=lambda a: len(a.cells)))
    for _ in range(20):
        game._update(1.0 / 60)
    bench("第12关 飞行中")

game.open_menu()
game._draw()
bench("菜单展开")

game.menu = None
theme.set_theme("day")
game._draw()
bench("第12关 日间")
