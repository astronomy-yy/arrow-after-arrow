"""临时性能基准：量化美化前后的整帧耗时（不进入版本库）。"""

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
    for _ in range(10):
        game._draw()
    times = []
    for _ in range(frames):
        start = time.perf_counter()
        game._draw()
        times.append(time.perf_counter() - start)
    print("%-16s 中位 %5.2f ms   最大 %5.2f ms"
          % (label, statistics.median(times) * 1000, max(times) * 1000))


game.state = GameState.START
game._draw()
bench("开始页")
game.state = GameState.LEVEL_SELECT
game._draw()
bench("选关页")

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
