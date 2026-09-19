"""用“逆向构造法”生成线段箭关卡，覆写 game/level.py。

玩法（蛇形式沿轨迹滑出）：点击后线段各节沿“自身折线 + 箭头延长线”
流动飞出；身体只经过自己原来的格子，因此一支箭能否飞出只取决于
箭头端朝向到边界之间有没有其他线段。

构造保证：
1. 从空棋盘逐条放箭，新箭的箭头射线必须为空（当前局面就能飞出）；
2. 尾巴第一节强制沿箭头反方向直行（箭头顺着最后一段轨迹），
   从第二节起才允许转弯，尾巴不能绕到箭头前方；
3. 箭头端优先选边界并朝外，棋盘覆盖率更高；
4. 每支箭至少 2 格（必有箭杆）；
5. 放置顺序的逆序就是一条必然通关的消除顺序。

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
    """新格子是否位于箭头朝向射线上（尾巴不能长到自己箭头前头）。"""
    dr, dc = DELTA[dch]
    if dr != 0:
        return nc == hc and (nr - hr) * dr > 0
    return nr == hr and (nc - hc) * dc > 0


def generate_one_level(count, seed, min_len, max_len, max_turns):
    """在单个种子下尽力生成 count 支箭，返回 (箭列表, 通关顺序, 覆盖率)。"""
    rng = random.Random(seed)
    occ = [[None] * COLS for _ in range(ROWS)]
    arrows = []
    add_order = []
    last_color = None
    attempts = 0

    while len(arrows) < count and attempts < 8000:
        attempts += 1
        empties = [(r, c) for r in range(ROWS) for c in range(COLS)
                   if occ[r][c] is None]
        if not empties:
            break

        # 箭头端优先选边界格
        boundary = [(r, c) for (r, c) in empties
                    if r == 0 or r == ROWS - 1 or c == 0 or c == COLS - 1]
        if boundary and rng.random() < 0.75:
            hr, hc = rng.choice(boundary)
            outs = []
            if hr == 0:
                outs.append("U")
            if hr == ROWS - 1:
                outs.append("D")
            if hc == 0:
                outs.append("L")
            if hc == COLS - 1:
                outs.append("R")
            if outs and rng.random() < 0.65:
                dch = rng.choice(outs)
            else:
                dch = rng.choice(list(DELTA))
        else:
            hr, hc = rng.choice(empties)
            dch = rng.choice(list(DELTA))

        # 箭头射线必须为空
        if not head_path_clear(occ, hr, hc, dch):
            continue

        dr, dc = DELTA[dch]
        target_len = rng.randint(min_len, max_len)
        cells = [(hr, hc)]
        gr, gc = -dr, -dc          # 尾巴初始生长方向 = 箭头反方向
        cr, cc = hr, hc
        turns = 0
        grew = True

        for step in range(target_len - 1):
            if step == 0:
                candidates = [(gr, gc)]               # 第一节强制直行
            elif turns >= max_turns:
                candidates = [(gr, gc)]
            else:
                candidates = [(gr, gc), (gr, gc), (-gc, gr), (gc, -gr)]
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
                grew = False
                break
            nr, nc, mdr, mdc = chosen
            if (mdr, mdc) != (gr, gc):
                turns += 1
            gr, gc = mdr, mdc
            cr, cc = nr, nc
            cells.append((nr, nc))

        if not grew or len(cells) < min_len:
            continue

        cells.reverse()            # 尾端 -> 箭头端
        arrow_id = len(arrows)
        for (r, c) in cells:
            occ[r][c] = arrow_id

        color_choices = [c for c in range(PALETTE_SIZE) if c != last_color]
        color_index = rng.choice(color_choices)
        last_color = color_index

        arrows.append({"cells": cells, "dir": dch, "color": color_index})
        add_order.append(arrow_id)

    coverage = sum(len(a["cells"]) for a in arrows) / (ROWS * COLS)
    return arrows, list(reversed(add_order)), coverage


def generate_best(count, base_seed, min_len, max_len, max_turns):
    """优先找到达标的种子；都不达标则返回箭数最多的一次结果。"""
    best = None
    for offset in range(60):
        seed = base_seed + offset
        arrows, solution, coverage = generate_one_level(
            count, seed, min_len, max_len, max_turns
        )
        if len(arrows) >= count:
            return arrows, solution, seed, coverage
        if best is None or len(arrows) > len(best[0]):
            best = (arrows, solution, seed, coverage)
    print(f"  警告：目标 {count} 支未达到，采用最佳结果 {len(best[0])} 支")
    return best


HEADER = '''"""关卡数据（由 tools/generate_levels.py 用逆向构造法确定性生成）。

每支箭的数据：
- cells：线段占据的格子，顺序为 尾端 -> 箭头端，相邻格上下左右相连，可拐弯；
  紧挨着箭头端的一节与箭头同向（箭头始终顺着最后一段轨迹）；
- dir：箭头方向（"U"/"D"/"L"/"R"），点击后各节沿自身折线流动、
  再沿该方向延长线飞出；
- color：game/settings.py 中 ARROW_PALETTE 的颜色索引；
- seed：生成该关所用随机种子，便于复现；
- solution：一条已验证的通关顺序（箭 id 列表，id 即 arrows 列表下标）。
"""
'''


def main():
    # 关卡名、失误上限、目标箭数、种子、最短、最长、最多转弯次数
    configs = [
        ("第1关 初露锋芒", 3, 10, 1101, 2, 4, 1),
        ("第2关 曲径通幽", 3, 14, 2202, 2, 5, 2),
        ("第3关 满盘皆兵", 4, 18, 3303, 2, 6, 2),
    ]

    levels = []
    for name, mistakes, count, seed, min_len, max_len, max_turns in configs:
        arrows, solution, used_seed, coverage = generate_best(
            count, seed, min_len, max_len, max_turns
        )
        levels.append({
            "name": name,
            "mistakes": mistakes,
            "rows": ROWS,
            "cols": COLS,
            "seed": used_seed,
            "arrows": arrows,
            "solution": solution,
        })
        print(f"{name}：{len(arrows)} 支箭，覆盖率 {coverage:.0%}，"
              f"种子 {used_seed}")

    text = HEADER + "\nLEVELS = "
    text += pprint.pformat(levels, width=100, sort_dicts=False)
    text += "\n"

    out_path = os.path.join(os.path.dirname(__file__), "..", "game", "level.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print("已写入:", os.path.abspath(out_path))


if __name__ == "__main__":
    main()
