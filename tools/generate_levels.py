"""用“逆向构造法”确定性生成 3 个线段箭关卡，并覆写 game/level.py。

原理（也是随机关卡模式的核心算法）：
1. 从空棋盘开始逐条放箭；
2. 每放一支新箭，只要求“它的箭头朝向到边界之间没有任何已放置的线段”，
   它在当前局面就能飞出；它的尾巴可以挡在别人前面（它会先飞走）；
3. 因此放置顺序的逆序就是一条必然通关的消除顺序。

重新生成：python tools/generate_levels.py
"""

import os
import pprint
import random

ROWS = COLS = 9
PALETTE_SIZE = 9

DELTA = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def head_path_clear(occ, hr, hc, dch):
    """箭头端朝向到边界之间是否没有任何占据。"""
    dr, dc = DELTA[dch]
    r, c = hr + dr, hc + dc
    while 0 <= r < ROWS and 0 <= c < COLS:
        if occ[r][c] is not None:
            return False
        r += dr
        c += dc
    return True


def in_front_of_head(nr, nc, hr, hc, dch):
    """新格子是否位于箭头朝向的射线上（自己的尾巴不能挡自己）。"""
    dr, dc = DELTA[dch]
    if dr != 0:
        return nc == hc and (nr - hr) * dr > 0
    return nr == hr and (nc - hc) * dc > 0


def generate(count, seed, min_len, max_len, max_turns):
    """生成 count 支箭，返回 (箭数据列表, 通关顺序)。"""
    rng = random.Random(seed)
    occ = [[None] * COLS for _ in range(ROWS)]
    arrows = []
    add_order = []

    attempts = 0
    while len(arrows) < count and attempts < 4000:
        attempts += 1
        empties = [(r, c) for r in range(ROWS) for c in range(COLS)
                   if occ[r][c] is None]
        if not empties:
            break

        hr, hc = rng.choice(empties)
        dch = rng.choice(list(DELTA))
        if not head_path_clear(occ, hr, hc, dch):
            continue

        dr, dc = DELTA[dch]
        target_len = rng.randint(min_len, max_len)
        cells = [(hr, hc)]
        gr, gc = -dr, -dc          # 尾巴从箭头反方向开始生长
        cr, cc = hr, hc
        turns = 0

        for _ in range(target_len - 1):
            # 直行权重更高，允许按 max_turns 转弯
            candidates = [(gr, gc), (gr, gc), (-gc, gr), (gc, -gr)]
            if turns >= max_turns:
                candidates = [(gr, gc)]
            rng.shuffle(candidates)

            chosen = None
            for mdr, mdc in candidates:
                nr, nc = cr + mdr, cc + mdc
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue
                if occ[nr][nc] is not None or (nr, nc) in cells:
                    continue
                if in_front_of_head(nr, nc, hr, hc, dch):
                    continue
                chosen = (nr, nc, mdr, mdc)
                break

            if chosen is None:
                break
            nr, nc, mdr, mdc = chosen
            if (mdr, mdc) != (gr, gc):
                turns += 1
            gr, gc = mdr, mdc
            cr, cc = nr, nc
            cells.append((nr, nc))

        cells.reverse()             # 转成“尾端 -> 箭头端”
        arrow_id = len(arrows)
        for (r, c) in cells:
            occ[r][c] = arrow_id
        arrows.append({
            "cells": cells,
            "dir": dch,
            "color": arrow_id % PALETTE_SIZE,
        })
        add_order.append(arrow_id)

    if len(arrows) < count:
        raise RuntimeError(f"只生成了 {len(arrows)}/{count} 支箭")

    return arrows, list(reversed(add_order))


HEADER = '''"""关卡数据（由 tools/generate_levels.py 用逆向构造法确定性生成）。

每支箭的数据：
- cells：线段占据的格子，顺序为 尾端 -> 箭头端，相邻格上下左右相连，可拐弯；
- dir：箭头方向（"U"/"D"/"L"/"R"），与最后一段走向一致；
- color：game/settings.py 中 ARROW_PALETTE 的颜色索引；
- solution：一条已验证的通关顺序（箭 id 列表，id 即 arrows 列表下标）。
"""
'''


def main():
    configs = [
        ("第1关 初露锋芒", 3, generate(6, seed=1101, min_len=1, max_len=3, max_turns=1)),
        ("第2关 曲径通幽", 3, generate(9, seed=2202, min_len=2, max_len=4, max_turns=1)),
        ("第3关 满盘皆兵", 4, generate(12, seed=3303, min_len=2, max_len=5, max_turns=2)),
    ]

    levels = []
    for name, mistakes, (arrows, solution) in configs:
        levels.append({
            "name": name,
            "mistakes": mistakes,
            "rows": ROWS,
            "cols": COLS,
            "arrows": arrows,
            "solution": solution,
        })

    text = HEADER + "\nLEVELS = "
    text += pprint.pformat(levels, width=100, sort_dicts=False)
    text += "\n"

    out_path = os.path.join(os.path.dirname(__file__), "..", "game", "level.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print("已生成:", os.path.abspath(out_path))
    for i, lv in enumerate(levels, 1):
        print(f"{lv['name']}：{len(lv['arrows'])} 支箭，通关顺序 {lv['solution']}")


if __name__ == "__main__":
    main()
