"""入门玩法的三关：全部单格箭，随机散铺。

## 为什么是单格箭

单格箭只占一格。``Board.can_fly_arrow`` 只看箭头端正前方那条射线上有没有
别的线段 —— 新手一眼就能读懂「这支能不能飞」，不用先学会读蜿蜒的蛇形线段。
所以入门三关全用单格箭，红心也跟主线一样是 3 颗（``mistakes``）。

## 为什么不摆成整齐的花样

上一版是按「一串格子 + 一个方向」把箭码成图案：第 1 关每行一条朝右的链、
第 2 关上半朝上/下半朝下、第 3 关横行纵列交叉。铺是铺满了，但**一眼就能
看出规律**，玩起来像照着图上标的序号点，也没有「谁挡着谁」的错落感。

现在改成随机散铺，用的是跟 ``game/generator.py`` 同一个套路 —— 逆向构造：

1. 逐支往回放箭，**放箭顺序就是通关顺序的倒序**；
2. 放箭时唯一的硬约束：这支箭箭头前方的射线上不能有**已经放好的**箭；
3. 这条约束正好等价于「按放箭顺序倒着点，每一步都飞得出去」，所以盘面
   天生可通关 —— 不用事后搜解，也摆不出互相封死的环。

## alpha 这个旋钮

落点从候选里挑，评分是 ``alpha * 走廊长度 + (1 - alpha) * 随机``。两头都不
能去：

- ``alpha = 0``（纯随机）：开局能直接飞的箭占到 50% 以上，乱点也能过，
  等于没有阻挡；
- ``alpha = 1``（永远挑走廊最长的落点）：可飞占比能压到 15% 左右，但候选
  被按走廊长度排序之后，反而排出一排排同向的条带 —— 又回到「有规律」了。

0.30 ~ 0.45 落在中间：既有阻挡，又不成花样。三关依次取 0.30 / 0.40 / 0.45。

## 「不规律」是钉住的硬指标

种子不是随手挑的，是按下面五条从几千个种子里筛出来的（``tests/
test_letters.py`` 原样钉住，改盘面就会红）。旧版三个数字分别是 T1 / T2 / T3：

| 指标 | 旧版（码成花样） | 现在 |
| --- | --- | --- |
| 整行 / 整列同向的条带 | 12 / 7 / 6 | 0 / 0 / 0 |
| 2×2 四格同向的小方块 | 15 / 16 / 0 | 0 / 0 / 0 |
| 横竖相邻同向的最长一段 | 6 / 5 / 8 | 2 / 3 / 3 |
| 最多那个方向的占比 | 100% / 43% / 50% | 33% / 29% / 27% |
| 开局能直接飞的箭 | 20% / 31% / 4% | 37% / 31% / 23% |

铺满率一点没掉，还是 30 / 35 / 48 支，占棋盘 62% / 56% / 60%；开局可飞
依次降低，难度还是 1 → 2 → 3 递增。

种子固定写在下表里（不是导入时现搜 —— 搜一遍要一分钟，写死之后三关构建
加求解一共 0.02 秒）。要换一批盘面：改 ``_PLAN`` 里的种子，或者拿新的
alpha 重跑一遍筛选。

## id 与显示关号

``id`` 用 T1/T2/T3：存档按 id 判重，必须避开基础关（1~12）与字母关（A~Z），
否则「清掉基础第 1 关」会顺手把入门第 1 关也标成已通关。界面上的关号是
1 / 2 / 3（见 ``main.Game._level_display_number``）。

``main._draw_tutorial_select`` 取名字用的是 ``name.split(" ")[-1]``，所以
关卡名要保持「入门 N 四个字」的格式。
"""

import random

DIRECTIONS = ("U", "D", "L", "R")

STEP = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}

WINDOW = 6          # 每次随机取几个候选落点，再从中挑评分最高的


def ray_cells(rows, cols, head, direction):
    """箭头端正前方、落在棋盘内的整条射线（不含箭头自己那格）。"""
    dr, dc = STEP[direction]
    row, col = head[0] + dr, head[1] + dc
    out = []
    while 0 <= row < rows and 0 <= col < cols:
        out.append((row, col))
        row += dr
        col += dc
    return out


def scatter_arrows(rows, cols, count, seed, alpha, window=WINDOW):
    """逆向构造散铺 ``count`` 支单格箭，返回 ``[(格子, 方向), ...]``。

    返回的顺序就是**放箭顺序**，通关顺序是它的倒序（``list(reversed(...))``）。
    铺不满 ``count`` 支时返回短列表 —— 候选被约束吃光就停下，不硬凑。
    """
    rng = random.Random(seed)
    taken = set()
    placed = []
    while len(placed) < count:
        options = []
        for row in range(rows):
            for col in range(cols):
                if (row, col) in taken:
                    continue
                for direction in DIRECTIONS:
                    ray = ray_cells(rows, cols, (row, col), direction)
                    if any(cell in taken for cell in ray):
                        continue
                    options.append((len(ray), (row, col), direction))
        if not options:
            break
        longest = max(option[0] for option in options) or 1
        pool = rng.sample(options, min(window, len(options)))
        pick = max(pool, key=lambda option: alpha * (option[0] / longest)
                   + (1 - alpha) * rng.random())
        taken.add(pick[1])
        placed.append((pick[1], pick[2]))
    return placed


def build_level(level_id, name, desc, rows, cols, time_limit, count,
                seed, alpha):
    """把散铺结果补成一整关；``solution`` 交给求解器独立验一遍。"""
    from game.board import Board
    from game.solver import solve

    placed = scatter_arrows(rows, cols, count, seed, alpha)
    if len(placed) != count:
        raise ValueError("入门关 %s 的种子 %d 只铺下 %d / %d 支箭"
                         % (level_id, seed, len(placed), count))
    level = {
        "id": level_id,
        "name": name,
        "desc": desc,
        "shape": "rect",
        "mistakes": 3,                  # 红心 3 颗，跟主线一致
        "rows": rows,
        "cols": cols,
        "seed": seed,                   # 散铺用的随机种子，改它就能换盘面
        "time_limit": time_limit,
        "arrows": [{"cells": [[row, col]], "dir": direction,
                    "color": index % 10}
                   for index, ((row, col), direction) in enumerate(placed)],
    }
    order = solve(Board(level))
    # 逆向构造保证有解；真报无解说明 seed / alpha 被改坏了，导入时就炸掉
    if not order:
        raise ValueError("入门关 %s 摆成了死局，换个种子" % level_id)
    level["solution"] = order
    return level


# 三关的散铺参数。箭数 / 棋盘：30/48 = 62%、35/63 = 56%、48/80 = 60%，
# 都过一半；alpha 0.30 → 0.45 配上棋盘变大，开局可飞 37% → 31% → 23%，
# 难度还是 1 → 2 → 3 递增。
#
# 说明（desc）会接在选关卡片的「NN 支箭 · 」后面，卡片可用宽度只有 302px，
# 现在这三条分别是 255 / 255 / 237px，再加字要先量 ``font_small.size``。
TUTORIAL_PLAN = [
    {"level_id": "T1", "name": "入门 1 散落满盘", "desc": "方向杂乱，先点能飞的",
     "rows": 6, "cols": 8, "time_limit": 300, "count": 30,
     "seed": 18, "alpha": 0.30},
    {"level_id": "T2", "name": "入门 2 交错成阵", "desc": "箭头交错，先清挡路的",
     "rows": 7, "cols": 9, "time_limit": 300, "count": 35,
     "seed": 17, "alpha": 0.40},
    {"level_id": "T3", "name": "入门 3 星罗棋布", "desc": "整盘散铺，一层层拆",
     "rows": 8, "cols": 10, "time_limit": 360, "count": 48,
     "seed": 69, "alpha": 0.45},
]


TUTORIAL_LEVELS = [build_level(**entry) for entry in TUTORIAL_PLAN]
