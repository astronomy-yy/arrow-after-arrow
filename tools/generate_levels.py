# -*- coding: utf-8 -*-
"""关卡生成脚本：用 game/generator.py 的逆向构造法重写 game/level.py。

用法（在项目根目录）：
    python tools/generate_levels.py            # 全部重新生成
    python tools/generate_levels.py 3          # 只重新生成第 3 关
    python tools/generate_levels.py --check    # 只校验现有 level.py
    python tools/generate_levels.py --stats    # 打印现有 12 关的难度表

生成出来的每一关都要过三道检查：
1. 按 solution 顺序点击，每一步箭头都真的能飞出去；
2. 用 game/solver.py 的拓扑排序独立解一遍，确认 AI 求解器也解得开；
3. 开局「能直接飞出去的箭」占比不超过该关上限定值（保证有阻挡、要动脑）。

难度靠 PLAN 里的 ray_pref / max_free 两点控制，从第 1 关到第 12 关
单调变难：第 1 关约七成的箭开局就能飞（给新手留够容错），第 12 关只剩
一成左右（开局只有 2 支能直接点，其余全被别的箭压住）。
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game import generator as G                                 # noqa: E402
from game.board import Board                                    # noqa: E402
from game.shapes import cells_of, is_connected                  # noqa: E402
from game.solver import solve                                   # noqa: E402

# (名字, 形状, 行, 列, 种子, 时限秒, ray_pref, 开局可飞上限)
# 棋盘尺寸比早期版本整体放大了约 1.4 倍：格子更密（画面里格子更多、线更细），
# 每关的箭数也随之上升，所以时限按「箭数 × 约 6 秒 + 余量」重新给了一遍。
PLAN = [
    ("第1关 初露锋芒", "rect", 17, 13, 1101021, 300, 0.35, 0.78),
    ("第2关 渐入佳境", "rect", 18, 14, 2202024, 320, 0.50, 0.65),
    ("第3关 圆转如意", "round", 16, 16, 3303008, 320, 0.58, 0.56),
    ("第4关 菱光乍现", "diamond", 18, 18, 4404016, 360, 0.64, 0.50),
    ("第5关 十字路口", "cross", 18, 18, 5505032, 360, 0.70, 0.46),
    ("第6关 心之所向", "heart", 18, 18, 6606048, 360, 0.76, 0.42),
    ("第7关 长街深巷", "rect", 21, 15, 7707056, 380, 0.82, 0.38),
    ("第8关 步步登高", "triangle", 17, 18, 8808064, 380, 0.88, 0.34),
    ("第9关 大盘如月", "round", 21, 21, 9909072, 460, 0.92, 0.30),
    ("第10关 沙漏流转", "hourglass", 20, 17, 11101088, 420, 0.96, 0.27),
    ("第11关 环环相扣", "ring", 21, 21, 12121104, 460, 0.98, 0.24),
    ("第12关 满盘皆兵", "rect", 25, 19, 13131200, 520, 1.00, 0.20),
]

# 上一关的实际可飞占比要再往下压这么多，才算「这一关更难」
FREE_MARGIN = 0.004
# 上限压下去之后同一个种子不一定够得到，换这几个种子再试。
# 一个种子既满足上限、又铺到这个填充率，就收工（省得每个种子都跑一遍）。
GOOD_FILL = 0.92
SEED_STEP = 100003
RETRY_TRIES = 6
RETRY_ATTEMPTS = 160

HEADER = '''"""关卡数据（由 tools/generate_levels.py 用「逆向构造法」生成）。

每支箭的数据：
- cells：线段占据的格子，顺序为 尾端 -> 箭头端，相邻格上下左右相连，
  形状为随机蜿蜒的蛇形折线（长短混合、频繁拐弯、朝向随机）；
- dir：箭头方向（"U"/"D"/"L"/"R"），点击后各节沿自身折线流动、
  再沿该方向延长线飞出；
- color：game/settings.py 中 ARROW_PALETTE 的颜色索引。

每关的数据：
- shape：game/shapes.py 里的造型名（rect/round/diamond/heart/...），
  线段只铺在这个造型内，辅助线点阵也只画在造型格上；
- seed：生成该关用的随机种子，便于复现；
- time_limit：倒计时秒数；
- solution：一条已验证的通关顺序（箭 id 列表，id 即 arrows 列表下标）。
  它是生成时「放箭顺序」的倒序：最后放进去的箭最先点。

关卡是**有阻挡**的：一支箭的箭头常常正对着另一支箭的身体，必须先把
挡路的那支点掉。所以 solution 只是其中一条合法顺序，不是唯一解。
难度从第 1 关到第 12 关递增：开局能直接飞出去的箭，从第 1 关的约七成
递减到第 12 关的一成左右。

重新生成：python tools/generate_levels.py
难度表：  python tools/generate_levels.py --stats
"""

'''


def build_one(index, prev_free=None):
    """生成第 index 关。

    ``prev_free`` 是上一关**实际**的开局可飞占比。只靠 PLAN 里的上限压不住
    回升：每一关都在自己的上限内独立挑「铺得最满」的一版，实际值可能比上一关
    还高（上限 0.78 拿到 0.62，下一关上限 0.65 却拿到 0.64）。所以这里把上限
    再压到「上一关实际值 - FREE_MARGIN」以下。

    压下去之后还有两个坑：**同一个种子未必够得到那个上限**，而且够到了也可能
    铺得很稀。不同造型的可飞占比下限差得很远（环形 21x21 用原种子只能到 14.6%，
    换种子能到 10.8%），所以上限没满足、或者满足了但填充率不到 ``GOOD_FILL``，
    就换个种子再来一遍，取「满足上限里铺得最满」的那一版。
    """
    name, shape, rows, cols, seed, limit, ray_pref, max_free = PLAN[index]
    if prev_free is not None:
        max_free = min(max_free, prev_free - FREE_MARGIN)

    style = dict(G.DEFAULT_STYLE, ray_pref=ray_pref)
    t0 = time.time()
    best = None                 # (是否满足上限, 填充率, level, stats, seed)
    tried = 0

    for attempt in range(RETRY_TRIES):
        use_seed = seed + attempt * SEED_STEP
        tried += 1
        level = G.build_level(rows, cols, shape, use_seed, name=name,
                              mistakes=3, time_limit=limit,
                              max_attempts=240 if attempt == 0
                              else RETRY_ATTEMPTS,
                              style=style, max_free=max_free)
        if level is None or solve(Board(level)) is None:
            continue
        stats = G.board_stats(level)
        fits = stats["free_ratio"] <= max_free + 1e-9
        score = (fits, G.fill_ratio(level))
        if best is None or score > best[0]:
            best = (score, level, stats, use_seed)
        if fits and G.fill_ratio(level) >= GOOD_FILL:
            break

    if best is None:
        raise SystemExit(f"第 {index + 1} 关生成失败：{shape} {rows}x{cols}")

    _, level, stats, use_seed = best
    level["id"] = index + 1
    if not best[0][0]:
        print(f"  ! 第 {index + 1} 关换了 {tried} 个种子仍没压到 "
              f"可飞上限 {max_free:.2f}（实际 {stats['free_ratio']:.3f}）")

    print(f"  {name:12s} {shape:10s} {rows:2d}x{cols:2d} "
          f"箭数={stats['arrows']:3d} "
          f"填充率={G.fill_ratio(level):.3f} "
          f"可飞上限={max_free:.2f} "
          f"开局可飞={stats['free']:2d}({stats['free_ratio']:.0%}) "
          f"被挡={stats['blocked_ratio']:.0%} "
          f"平均挡者={stats['avg_blockers']:.2f} "
          f"种子={use_seed} "
          f"难度={G.difficulty(level):5.1f} 耗时={time.time() - t0:.1f}s")
    return level


def build_all():
    """顺序生成 12 关，每一关的可飞上限都跟着上一关的实际值压下去。"""
    levels = []
    prev_free = None
    for index in range(len(PLAN)):
        level = build_one(index, prev_free)
        levels.append(level)
        prev_free = G.board_stats(level)["free_ratio"]
    return levels


def dump(levels, path):
    lines = [HEADER, "LEVELS = ["]
    for level in levels:
        lines.append("    {")
        lines.append(f"        'id': {level['id']},")
        lines.append(f"        'name': {level['name']!r},")
        lines.append(f"        'shape': {level['shape']!r},")
        lines.append(f"        'mistakes': {level['mistakes']},")
        lines.append(f"        'rows': {level['rows']},")
        lines.append(f"        'cols': {level['cols']},")
        lines.append(f"        'seed': {level['seed']},")
        lines.append(f"        'time_limit': {level['time_limit']},")
        lines.append("        'arrows': [")
        for arrow in level["arrows"]:
            lines.append(f"            {{'cells': {arrow['cells']!r}, "
                         f"'dir': {arrow['dir']!r}, "
                         f"'color': {arrow['color']}}},")
        lines.append("        ],")
        lines.append(f"        'solution': {level['solution']!r},")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("SHAPE_LABELS = {")
    lines.append("    'rect': '方形', 'round': '圆形', 'diamond': '菱形',")
    lines.append("    'heart': '心形', 'triangle': '三角', 'cross': '十字',")
    lines.append("    'hourglass': '沙漏', 'ring': '圆环',")
    lines.append("}")
    lines.append("")
    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"已写入 {path}（{len(text)} 字节，{len(levels)} 关）")


def stats_table(levels):
    """打印难度表（生成脚本 --stats 与文档记录都用它）。"""
    print(f"{'关卡':<14}{'形状':<10}{'箭数':>4}{'填充率':>8}"
          f"{'开局可飞':>10}{'被挡':>8}{'平均挡者':>10}{'难度':>8}")
    rows = []
    for level in levels:
        stats = G.board_stats(level)
        fill = G.fill_ratio(level)
        rows.append((level["name"], level.get("shape", "?"), stats, fill))
        print(f"{level['name']:<14}{level.get('shape', '?'):<10}"
              f"{stats['arrows']:>4}{fill:>8.3f}"
              f"{stats['free']:>4}({stats['free_ratio']:.0%})"
              f"{stats['blocked_ratio']:>8.0%}"
              f"{stats['avg_blockers']:>10.2f}"
              f"{G.difficulty(level):>8.1f}")
    n = len(rows)
    print(f"{'平均':<14}{'':<10}"
          f"{sum(r[2]['arrows'] for r in rows) / n:>4.1f}"
          f"{sum(r[3] for r in rows) / n:>8.3f}"
          f"{sum(r[2]['free_ratio'] for r in rows) / n:>9.0%}"
          f"{sum(r[2]['blocked_ratio'] for r in rows) / n:>8.0%}"
          f"{sum(r[2]['avg_blockers'] for r in rows) / n:>10.2f}")
    return rows


def check(levels):
    """只读校验：形状连通、solution 全程可飞、求解器解得开、确实有阻挡。"""
    ok = True
    for index, level in enumerate(levels):
        mask = cells_of(level["rows"], level["cols"], level.get("shape", "rect"))
        connected = is_connected(mask)

        board = Board(level)
        by_id = {arrow.id: arrow for arrow in board.arrows}
        solution_ok = True
        for arrow_id in level["solution"]:
            arrow = by_id.get(arrow_id)
            if arrow is None or not board.can_fly_arrow(arrow):
                solution_ok = False
                break
            board.remove_arrow(arrow)
        solution_ok = solution_ok and board.remaining == 0

        solver_ok = solve(Board(level)) is not None
        stats = G.board_stats(level)
        blocked_ok = stats["blocked_ratio"] >= 0.25

        flag = "OK " if (connected and solution_ok and solver_ok
                         and blocked_ok) else "BAD"
        print(f"  [{flag}] {level['name']:12s} "
              f"连通={connected} solution={solution_ok} 求解器={solver_ok} "
              f"箭数={stats['arrows']:>3} 被挡={stats['blocked_ratio']:.0%} "
              f"开局可飞={stats['free']:>2}/{stats['arrows']}")
        ok = ok and connected and solution_ok and solver_ok and blocked_ok

    # 难度曲线：开局可飞占比不许回升（tests/test_blocking.py 也钉了这条）
    ratios = [G.board_stats(level)["free_ratio"] for level in levels]
    rising = [(index, ratios[index - 1], ratios[index])
              for index in range(1, len(ratios))
              if ratios[index] > ratios[index - 1] + 1e-9]
    curve_ok = not rising
    print(f"  [{'OK ' if curve_ok else 'BAD'}] 难度曲线 "
          f"{'严格不回升' if curve_ok else '出现回升 %s' % rising}："
          + " → ".join(f"{r:.0%}" for r in ratios))
    return ok and curve_ok


def main():
    args = sys.argv[1:]
    target = os.path.join(ROOT, "game", "level.py")

    if "--check" in args:
        from game.level import LEVELS
        print("校验 game/level.py：")
        raise SystemExit(0 if check(LEVELS) else 1)

    if "--stats" in args:
        from game.level import LEVELS
        print("game/level.py 的难度表：")
        stats_table(LEVELS)
        raise SystemExit(0)

    if args and args[0].isdigit():
        only = int(args[0]) - 1
        from game.level import LEVELS
        levels = list(LEVELS)
        # 用上一关的实际值压住上限；下一关的约束由 check() 的难度曲线把关
        prev = (G.board_stats(levels[only - 1])["free_ratio"] if only else None)
        print(f"重新生成第 {only + 1} 关：")
        levels[only] = build_one(only, prev)
    else:
        print("生成全部关卡：")
        levels = build_all()

    dump(levels, target)
    print("\n难度表：")
    stats_table(levels)
    print("\n校验新生成的关卡：")
    ok = check(levels)
    print("全部通过" if ok else "存在问题")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
