"""可通关关卡生成器。

用的是「逆向构造法」，跟参考录屏里的关卡构成方式一致：

1. 先用 game.shapes 把棋盘裁成一个造型（方 / 圆 / 心……），
   线段只会铺在这个造型里；
2. 从空棋盘开始，一支一支往回放箭。**放箭顺序 = 通关顺序的倒序**：
   第一支放进去的最后才点，最后一支放进去的最先点；
3. 每放一支箭只要求一条约束：**它自己箭头前方的射线上，当时不能有
   已经放好的箭**。

这条约束正好等价于「按放箭的倒序点，每一步都飞得出去」，所以关卡必然
可通关：第 j 支箭飞的时候，留在盘上的恰好是比它早放的 1..j-1 支，而它
的射线在放置那一刻就确认过躲开了这些箭。

## 关于「阻挡」——曾经踩过的坑

早期版本还加了第二条约束：**箭的身体也不许压在已放好箭的射线上**。
它和上面那条合起来，等价于对任意两支箭都有

    射线(a) ∩ 身体(b) = ∅

也就是每支箭的出口走廊永远是空的：开局全盘任何一支都能直接飞出去，
点什么都对，关卡退化成「无脑乱点必通关」。第二条约束对可通关性毫无
贡献，纯粹是把玩法抹掉了，已经删除。

删掉之后，**后放的箭（先点）可以名正言顺地站在先放的箭（后点）的
射线上**，这就是关卡里的阻挡与先后依赖。

难度由 ``ray_pref`` 一个旋钮控制：挑落点时偏好「前方空走廊长」还是
「短」。走廊越长，越容易被后面放的箭压住 → 阻挡越多。实测这个旋钮
从 0 到 1，开局可飞的箭从 99% 一路压到 22%，而填充率反而从 0.924 升到
0.965 —— 阻挡和「铺得满」并不矛盾。

单支箭的数据：
- cells：尾端 -> 箭头端，相邻格上下左右相连，可以拐弯；
- dir：箭头方向（"U"/"D"/"L"/"R"）；
- color：game/settings.py 中 ARROW_PALETTE 的颜色索引。
"""

import random

from game.arrow import DIRECTION_DELTA
from game.shapes import cells_of, is_connected

DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))

MIN_PIECE = 2       # 一支箭最少几格

# 参考图里的线段「又长又绕」：一支箭能长到十几格、平均 7~8 格，但直行
# 概率只有 0.24 —— 大部份步数都在拐弯，所以看起来是缠成一团的折线，
# 而不是几根长横条。长箭同时把棋盘铺得更满（大圆盘也能到 0.96+）。
DEFAULT_STYLE = {
    "max_piece": 26,        # 一支箭最多几格
    "straight_bias": 0.24,  # 身体继续直行的概率（越小拐弯越频繁）
    "stop_chance": 0.03,    # 身体长到一定长度后随机收尾的概率
    "window": 4,            # 每次在若干个候选落点里随机挑一个
    "ray_pref": 0.65,       # 偏好「前方空走廊长」的落点（0=短，1=长）
}


def direction_of(step):
    """把 (dr, dc) 步长翻译成方向枚举。"""
    for direction, delta in DIRECTION_DELTA.items():
        if delta == step:
            return direction
    raise ValueError(f"不是合法的网格步长：{step}")


def _ray_all(head, step, rows, cols):
    """箭头前方的整条射线（含棋盘外的部分不返回）。"""
    dr, dc = step
    r, c = head[0] + dr, head[1] + dc
    out = []
    while 0 <= r < rows and 0 <= c < cols:
        out.append((r, c))
        r += dr
        c += dc
    return out


# --------------------------------------------------------------------------
# 逆向构造
# --------------------------------------------------------------------------

def _collect_heads(mask, rows, cols, occupied, rng):
    """枚举所有「可以下手」的 (前方走廊长, 随机键, 箭头格, 方向, 头后一格)。

    走廊长 = 箭头前方落在造型内、且当前还空着的格子数。它同时代表两件事：
    这些格子能不能被后面的箭填满（填充率），以及这支箭未来有多容易被压住
    （阻挡强度）。
    """
    heads = []
    for cell in mask:
        if cell in occupied:
            continue
        for step in DIRS:
            back = (cell[0] - step[0], cell[1] - step[1])
            if back not in mask or back in occupied:
                continue
            ray = _ray_all(cell, step, rows, cols)
            if any(cell_on_ray in occupied for cell_on_ray in ray):
                continue
            ahead = sum(1 for cell_on_ray in ray if cell_on_ray in mask)
            heads.append((ahead, rng.random(), cell, step, back))
    return heads


def _grow_body(head, first_step, ray_set, mask, occupied, rng, style=None):
    """从箭头端往回长身体，返回 [头, ..., 尾] 顺序的格子。

    唯一要躲开的是**自己那条射线**（``ray_set``）：身体一旦压上自己的出口
    走廊，这支箭就永远飞不出去了。
    """
    style = style or DEFAULT_STYLE
    max_piece = style["max_piece"]
    straight_bias = style["straight_bias"]
    stop_chance = style["stop_chance"]
    back = (head[0] - first_step[0], head[1] - first_step[1])
    body = [head, back]
    used = {head, back}
    cur = back
    while len(body) < max_piece:
        opts = []
        for step in DIRS:
            nxt = (cur[0] + step[0], cur[1] + step[1])
            if nxt not in mask or nxt in occupied:
                continue
            if nxt in used or nxt in ray_set:
                continue
            opts.append((nxt, step))
        if not opts:
            break
        if len(body) >= 3 and rng.random() < straight_bias:
            prev = body[-2]
            straight = (cur[0] - prev[0], cur[1] - prev[1])
            opts = [o for o in opts if o[1] == straight] or opts
        nxt, _ = opts[rng.randrange(len(opts))]
        body.append(nxt)
        used.add(nxt)
        cur = nxt
        if len(body) >= MIN_PIECE and rng.random() < stop_chance:
            break
    return body


def _build_once(rows, cols, mask, rng, palette_size, style=None):
    """跑一遍逆向构造，返回 (arrows, 已占用格集合)。"""
    style = style or DEFAULT_STYLE
    window = max(1, style.get("window", 3))
    ray_pref = style.get("ray_pref", 0.0)
    placed = []
    occupied = set()

    while True:
        heads = _collect_heads(mask, rows, cols, occupied, rng)
        if not heads:
            break
        heads.sort(key=lambda item: (item[0], item[1]))
        # ray_pref 越大越偏好「前方走廊长」的落点：走廊长 → 后面放的箭
        # 容易压在它身上 → 阻挡多、难度高、也铺得更满。
        if len(heads) > window and rng.random() < ray_pref:
            pool = heads[-window:]
        else:
            pool = heads[:window]
        pick = pool[rng.randrange(len(pool))]

        head, step = pick[2], pick[3]
        ray = set(_ray_all(head, step, rows, cols))
        body = _grow_body(head, step, ray, mask, occupied, rng, style)
        cells = list(reversed(body))            # 尾端 -> 箭头端
        placed.append({
            "cells": [list(cell) for cell in cells],
            "dir": direction_of(step).value,
            "color": rng.randrange(palette_size),
        })
        occupied.update(body)

    return placed, occupied


def build_level(rows, cols, shape, seed, name="", mistakes=3,
                time_limit=240, palette_size=10, min_fill=0.0, max_free=None,
                max_attempts=6, style=None):
    """多次尝试，取「满足难度约束且铺得最满」的一关。

    - ``min_fill``：填充率下限；
    - ``max_free``：开局可飞箭数的占比上限。设成 0.3 就代表「开局最多
      三成的箭能直接飞」，剩下的必须靠推理排出先后。None = 不限制。

    限制无法满足时（造型太小 / 运气差）会退而取综合分最高的一版，
    绝不会返回不可通关的关卡。
    """
    mask = cells_of(rows, cols, shape)
    if not is_connected(mask) or len(mask) < 10:
        return None

    best = None         # 满足约束里填充率最高的
    fallback = None     # 兜底：偏离约束最少的一版
    for attempt in range(max_attempts):
        rng = random.Random(seed * 131 + attempt * 977)
        placed, occupied = _build_once(rows, cols, mask, rng, palette_size,
                                       style)
        if len(placed) < 3:
            continue
        fill = len(occupied) / len(mask)
        level = {
            "name": name or f"{shape} #{seed}",
            "mistakes": mistakes,
            "rows": rows,
            "cols": cols,
            "shape": shape,
            "seed": seed,
            "time_limit": time_limit,
            "arrows": placed,
            # 放箭顺序的倒序就是通关顺序
            "solution": list(range(len(placed) - 1, -1, -1)),
        }
        if not verify_solution(level):
            continue

        stats = board_stats(level)
        if stats["free"] < 1:       # 理论上有解，但保险起见
            continue
        fits = fill >= min_fill and (max_free is None
                                     or stats["free_ratio"] <= max_free)
        if fits:
            if best is None or fill > best[0]:
                best = (fill, level)
                if fill >= 0.995:
                    break
        else:
            # 综合分：填充率越高越好，超出可飞上限的部分扣分
            over = 0.0
            if max_free is not None:
                over = max(0.0, stats["free_ratio"] - max_free)
            score = fill - 0.8 * over
            if fallback is None or score > fallback[0]:
                fallback = (score, level)

    if best is not None:
        return best[1]
    return fallback[1] if fallback else None


# --------------------------------------------------------------------------
# 校验与统计
# --------------------------------------------------------------------------

def verify_solution(level):
    """整条 solution 是否每一步都能飞（拿真正盘跑一遍）。"""
    from game.board import Board

    board = Board(level)
    by_id = {arrow.id: arrow for arrow in board.arrows}
    for arrow_id in level["solution"]:
        arrow = by_id.get(arrow_id)
        if arrow is None or not board.can_fly_arrow(arrow):
            return False
        board.remove_arrow(arrow)
    return board.remaining == 0


def blockers_of(board, arrow):
    """当前局面下，挡住这支箭的箭有哪几支（同一支只算一次）。"""
    dr, dc = DIRECTION_DELTA[arrow.direction]
    r, c = arrow.head[0] + dr, arrow.head[1] + dc
    out = []
    while board.in_bounds(r, c):
        other = board.arrow_at(r, c)
        if other is not None and other is not arrow and other not in out:
            out.append(other)
        r += dr
        c += dc
    return out


def board_stats(level):
    """开局盘面的难度指标。

    - ``free`` / ``free_ratio``：开局能直接飞出去的箭数（及其占比）；
      占比越低，越需要先推理出该从哪支下手，而不是乱点；
    - ``blocked_ratio``：被别的箭挡住的箭的比例，0 就说明毫无阻挡；
    - ``avg_blockers``：平均每支箭被几支箭挡着。
    """
    from game.board import Board

    board = Board(level)
    total = board.total
    free = len(board.flyable_arrows())
    blocked = 0
    blocker_total = 0
    for arrow in board.arrows:
        count = len(blockers_of(board, arrow))
        blocker_total += count
        if count:
            blocked += 1
    return {
        "arrows": total,
        "free": free,
        "free_ratio": free / total if total else 1.0,
        "blocked_ratio": blocked / total if total else 0.0,
        "avg_blockers": blocker_total / total if total else 0.0,
    }


def fill_ratio(level):
    """线段占遮罩格子的比例（参考图的关卡大约在 0.85 ~ 0.95）。"""
    mask = cells_of(level["rows"], level["cols"], level.get("shape", "rect"))
    used = sum(len(a["cells"]) for a in level["arrows"])
    return used / len(mask) if mask else 0.0


# --------------------------------------------------------------------------
# 运行时的随机关卡
# --------------------------------------------------------------------------

RANDOM_SHAPES = [
    ("round", 13, 13), ("round", 15, 15), ("diamond", 13, 13),
    ("heart", 13, 13), ("heart", 15, 15), ("cross", 13, 13),
    ("rect", 12, 9), ("rect", 14, 10), ("hourglass", 14, 12),
    ("triangle", 12, 13), ("ring", 15, 15), ("round", 11, 11),
]


def random_level(seed=None, palette_size=10, max_free=0.45):
    """运行时用的随机关卡：造型、尺寸都随机，但同样是「有阻挡」的。"""
    rng = random.Random(seed)
    if seed is None:
        seed = rng.randrange(1 << 30)

    order = RANDOM_SHAPES[:]
    rng.shuffle(order)
    for shape, rows, cols in order:
        level = build_level(rows, cols, shape, rng.randrange(1 << 30),
                            name="随机关卡", mistakes=3, time_limit=300,
                            palette_size=palette_size, max_attempts=40,
                            max_free=max_free)
        if level:
            level["random"] = True
            return level
    return build_level(10, 8, "rect", rng.randrange(1 << 30),
                       name="随机关卡", max_attempts=60, max_free=max_free)


# --------------------------------------------------------------------------
# 难度参考
# --------------------------------------------------------------------------

def arrow_count(level):
    return len(level["arrows"])


def total_cells(level):
    return sum(len(a["cells"]) for a in level["arrows"])


def difficulty(level):
    """粗略难度分：箭数 + 平均长度 + 阻挡强度。"""
    count = arrow_count(level)
    if count == 0:
        return 0
    stats = board_stats(level)
    return round(count + total_cells(level) / count
                 + 10 * stats["blocked_ratio"], 1)
