"""可通关关卡生成器。

用的是「逆向构造法」，跟参考录屏里的关卡构成方式一致：

1. 先用 game.shapes 把棋盘裁成一个造型（方 / 圆 / 心……），
   线段只会铺在这个造型里；
2. 从空棋盘开始，一支一支往回放箭。**放箭顺序 = 通关顺序的倒序**：
   第一支放进去的最后才点，最后一支放进去的最先点。
3. 每放一支箭都要满足两条约束（这就是可通关的保证）：
   - 它自己箭头前方的射线上，不能有已经放好的箭；
   - 它自己的格子，不能压在已经放好的箭的射线上。
4. 因此「箭头射线」永远是空走廊 —— 参考图里那些点阵空行就是这么来的。

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

# 参考图里的线段以「短、爱拐弯」为主：绝大多数 3~6 格，直行不超过两三格
# 就会拐弯，所以整盘看起来是缠成一团的折线，而不是几根长横条。
# 参考图里的线段「又长又绕」：一支箭能长到十几格、平均 7~8 格，但直行
# 概率只有 0.28 —— 大部份步数都在拐弯，所以看起来是缠成一团的折线，
# 而不是几根长横条。长箭同时把棋盘铺得更满（大圆盘也能到 0.93+）。
DEFAULT_STYLE = {
    "max_piece": 20,        # 一支箭最多几格
    "straight_bias": 0.28,  # 身体继续直行的概率（越小拐弯越频繁）
    "stop_chance": 0.06,    # 身体长到一定长度后随机收尾的概率
    "window": 2,            # 每次在最省空间的若干个候选里随机挑一个
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

def _collect_heads(mask, rows, cols, occupied, forbidden, rng):
    """枚举所有「可以下手」的 (代价, 随机键, 箭头格, 方向, 头后面那格)。

    代价 = 这条射线会新占用多少格「永久空走廊」——已经空着的走廊不算钱，
    所以从走廊边上出发的箭几乎不浪费空间，铺得更满。
    """
    heads = []
    for cell in mask:
        if cell in occupied or cell in forbidden:
            continue
        for step in DIRS:
            back = (cell[0] - step[0], cell[1] - step[1])
            if back not in mask or back in occupied or back in forbidden:
                continue
            ray = _ray_all(cell, step, rows, cols)
            if any(cell_on_ray in occupied for cell_on_ray in ray):
                continue
            cost = sum(1 for cell_on_ray in ray
                       if cell_on_ray in mask and cell_on_ray not in forbidden)
            heads.append((cost, rng.random(), cell, step, back))
    return heads


def _grow_body(head, first_step, ray_set, mask, occupied, forbidden, rng,
               style=None):
    """从箭头端往回长身体，返回 [头, ..., 尾] 顺序的格子。"""
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
            if nxt not in mask or nxt in occupied or nxt in forbidden:
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
    window = style.get("window", 5)
    placed = []
    occupied = set()
    forbidden = set()

    while True:
        heads = _collect_heads(mask, rows, cols, occupied, forbidden, rng)
        if not heads:
            break
        heads.sort(key=lambda item: (item[0], item[1]))
        # 在最省空间的若干个候选里随机挑一个，既铺得满又有多样性
        pick = heads[rng.randrange(min(len(heads), window))]

        head, step = pick[2], pick[3]
        ray = set(_ray_all(head, step, rows, cols))
        body = _grow_body(head, step, ray, mask, occupied, forbidden, rng,
                          style)
        cells = list(reversed(body))            # 尾端 -> 箭头端
        placed.append({
            "cells": [list(cell) for cell in cells],
            "dir": direction_of(step).value,
            "color": rng.randrange(palette_size),
        })
        occupied.update(body)
        forbidden.update(cell for cell in ray if cell in mask)

    return placed, occupied


def build_level(rows, cols, shape, seed, name="", mistakes=3,
                time_limit=240, palette_size=10, min_fill=0.0,
                max_attempts=6, style=None):
    """多次尝试，取铺得最满的一关；全部不合格时返回 None。"""
    mask = cells_of(rows, cols, shape)
    if not is_connected(mask) or len(mask) < 10:
        return None

    best = None
    for attempt in range(max_attempts):
        rng = random.Random(seed * 131 + attempt * 977)
        placed, occupied = _build_once(rows, cols, mask, rng, palette_size,
                                       style)
        if len(placed) < 3:
            continue
        fill = len(occupied) / len(mask)
        if best is not None and fill <= best[0]:
            continue
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
        best = (fill, level)
        if fill >= 0.995:
            break

    if best is None:
        return None
    if min_fill and best[0] < min_fill:
        return None
    return best[1]


# --------------------------------------------------------------------------
# 校验
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


def greedy_solution(level, limit=None):
    """贪心求一条通关顺序（每一步挑一支能飞的），失败返回 None。

    用于校验「逆向构造」出来的关卡是否真的可解，也可以当作弱求解器。
    """
    from game.board import Board

    board = Board(level)
    order = []
    while board.remaining:
        movable = board.flyable_arrows()
        if not movable:
            return None
        arrow = movable[0]
        order.append(arrow.id)
        board.remove_arrow(arrow)
        if limit is not None and len(order) > limit:
            return None
    return order


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


def random_level(seed=None, palette_size=10):
    """运行时用的随机关卡：造型、尺寸都随机。"""
    rng = random.Random(seed)
    if seed is None:
        seed = rng.randrange(1 << 30)

    order = RANDOM_SHAPES[:]
    rng.shuffle(order)
    for shape, rows, cols in order:
        level = build_level(rows, cols, shape, rng.randrange(1 << 30),
                            name="随机关卡", mistakes=3, time_limit=300,
                            palette_size=palette_size, max_attempts=40)
        if level:
            level["random"] = True
            return level
    return build_level(10, 8, "rect", rng.randrange(1 << 30),
                       name="随机关卡", max_attempts=60)


# --------------------------------------------------------------------------
# 难度参考
# --------------------------------------------------------------------------

def arrow_count(level):
    return len(level["arrows"])


def total_cells(level):
    return sum(len(a["cells"]) for a in level["arrows"])


def difficulty(level):
    """粗略难度分：箭数 + 平均长度。"""
    count = arrow_count(level)
    if count == 0:
        return 0
    return round(count + total_cells(level) / count, 1)
