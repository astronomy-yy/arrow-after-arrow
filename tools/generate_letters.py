# -*- coding: utf-8 -*-
"""字母关卡生成脚本：用 game/generator.py 的逆向构造法重写 game/level_letters.py。

26 个字母各一关，棋盘统一 23x17：字模（game/letters.py 的 5×7 点阵）
按 scale=3 放大、四周留一圈空边，线段只铺在字母的笔画里。

难度也是一条爬升曲线：A 开局四成左右的箭能直接飞（给新手留够容错），
到 Z 压到三成以下（大部分箭都被别的箭压住，得先理出先后）。

用法（在项目根目录）：
    python tools/generate_letters.py            # 全部重新生成
    python tools/generate_letters.py --check    # 只校验现有 level_letters.py
    python tools/generate_letters.py --stats    # 打印 26 关的难度表
    python tools/generate_letters.py A B C      # 只重新生成指定的几个字母
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game import generator as G                                 # noqa: E402
from game import letters as L                                   # noqa: E402
from game.board import Board                                    # noqa: E402
from game.solver import solve                                   # noqa: E402

TIME_LIMIT = 300
MISTAKES = 3
ATTEMPTS = 200
# 一支箭最多几格。笔画本身不宽，但棋盘从 16x12 加密到 23x17 之后格子多了
# 一倍，max_piece 太小会留下一串填不上的空洞（填充率掉、颜色也碎）。
MAX_PIECE = 20

RAY_PREF_START, RAY_PREF_END = 0.45, 0.90
MAX_FREE_START, MAX_FREE_END = 0.58, 0.30

HEADER = '''"""字母关卡数据（由 tools/generate_letters.py 用「逆向构造法」生成）。

26 个字母各一关，棋盘统一 23x17：把 game/letters.py 的 5×7 点阵字模按
scale=3 放大，线段只铺在字母的笔画里，于是整盘看着就是那个大写字母。

- letter：这一关铺的是哪个字母；
- shape 恒为 "letter"，遮罩由点阵字模栅格化而来（辅助线点阵也只画在
  笔画格上）；连通性按**八连通**判定 —— C / S / J 这类斜笔在点阵层面
  是对角相接的，放大后两个方块共享一个角点，看着是一笔连下来的。

难度按字母顺序爬升：A 开局约四成的箭能直接飞，到 Z 压到三成以下。

重新生成：python tools/generate_letters.py
难度表：  python tools/generate_letters.py --stats
"""


'''


def plan_for(index):
    """第 index 个字母的难度旋钮（线性爬升）。"""
    total = max(1, len(L.LETTERS) - 1)
    t = index / total
    return (RAY_PREF_START + (RAY_PREF_END - RAY_PREF_START) * t,
            MAX_FREE_START + (MAX_FREE_END - MAX_FREE_START) * t)


def build_one(index):
    letter = L.LETTERS[index]
    ray_pref, max_free = plan_for(index)
    rows, cols = L.board_size()
    style = dict(G.DEFAULT_STYLE, ray_pref=ray_pref, max_piece=MAX_PIECE)
    t0 = time.time()
    level = G.build_level(rows, cols, "letter", 7000 + ord(letter),
                          name="字母 %s" % letter, mistakes=MISTAKES,
                          time_limit=TIME_LIMIT, max_attempts=ATTEMPTS,
                          style=style, max_free=max_free, letter=letter)
    if level is None:
        raise SystemExit("字母 %s 生成失败（%dx%d）" % (letter, rows, cols))
    level["id"] = letter
    level["group"] = "letter"

    stats = G.board_stats(level)
    if solve(Board(level)) is None:
        raise SystemExit("字母 %s 求解器解不开，已丢弃" % letter)

    print("  %s  %2dx%-2d 箭数=%2d 填充率=%.3f 开局可飞=%2d(%2.0f%%) "
          "被挡=%2.0f%% 平均挡者=%.2f 难度=%4.1f 耗时=%.1fs"
          % (letter, rows, cols, stats["arrows"], G.fill_ratio(level),
             stats["free"], stats["free_ratio"] * 100,
             stats["blocked_ratio"] * 100, stats["avg_blockers"],
             G.difficulty(level), time.time() - t0))
    return level


def dump(levels, path):
    lines = [HEADER, "LEVELS = ["]
    for level in levels:
        lines.append("    {")
        lines.append(f"        'id': {level['id']!r},")
        lines.append(f"        'name': {level['name']!r},")
        lines.append(f"        'letter': {level['letter']!r},")
        lines.append(f"        'shape': 'letter',")
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
    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("已写入 %s（%d 字节，%d 关）" % (path, len(text), len(levels)))


def stats_table(levels):
    print("%-4s %8s %8s %10s %8s %10s %8s"
          % ("字母", "箭数", "填充率", "开局可飞", "被挡", "平均挡者", "难度"))
    rows = []
    for level in levels:
        stats = G.board_stats(level)
        fill = G.fill_ratio(level)
        rows.append((stats, fill))
        print("%-4s %8d %8.3f %10s %7.0f%% %10.2f %8.1f"
              % (level["id"], stats["arrows"], fill,
                 "%d(%d%%)" % (stats["free"],
                               round(stats["free_ratio"] * 100)),
                 stats["blocked_ratio"] * 100, stats["avg_blockers"],
                 G.difficulty(level)))
    n = len(rows)
    print("%-4s %8.1f %8.3f %10s %7.0f%% %10.2f"
          % ("平均", sum(r[0]["arrows"] for r in rows) / n,
             sum(r[1] for r in rows) / n,
             "%.0f%%" % (sum(r[0]["free_ratio"] for r in rows) / n * 100),
             sum(r[0]["blocked_ratio"] for r in rows) / n * 100,
             sum(r[0]["avg_blockers"] for r in rows) / n))
    return rows


def check(levels):
    """只读校验：遮罩八连通、solution 全程可飞、求解器解得开、确实有阻挡。"""
    ok = True
    for level in levels:
        mask = L.letter_cells(level["rows"], level["cols"], level["letter"])
        connected = G.is_connected(mask, diagonal=True)

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
        blocked_ok = stats["blocked_ratio"] >= 0.35

        flag = "OK " if (connected and solution_ok and solver_ok
                         and blocked_ok) else "BAD"
        print("  [%s] %s  连通=%s solution=%s 求解器=%s 箭数=%2d 被挡=%.0f%% "
              "开局可飞=%d/%d"
              % (flag, level["id"], connected, solution_ok, solver_ok,
                 stats["arrows"], stats["blocked_ratio"] * 100,
                 stats["free"], stats["arrows"]))
        ok = ok and connected and solution_ok and solver_ok and blocked_ok
    return ok


def main():
    args = sys.argv[1:]
    target = os.path.join(ROOT, "game", "level_letters.py")

    if "--check" in args:
        from game.level_letters import LEVELS
        print("校验 game/level_letters.py：")
        raise SystemExit(0 if check(LEVELS) else 1)

    if "--stats" in args:
        from game.level_letters import LEVELS
        print("game/level_letters.py 的难度表：")
        stats_table(LEVELS)
        raise SystemExit(0)

    wanted = [a.upper() for a in args if a.upper() in L.LETTERS]
    if wanted:
        from game.level_letters import LEVELS
        levels = list(LEVELS)
        print("重新生成字母：%s" % " ".join(wanted))
        for letter in wanted:
            levels[L.LETTERS.index(letter)] = build_one(
                L.LETTERS.index(letter))
    else:
        print("生成全部 26 个字母关：")
        levels = [build_one(i) for i in range(len(L.LETTERS))]

    dump(levels, target)
    print("\n难度表：")
    stats_table(levels)
    print("\n校验新生成的关卡：")
    ok = check(levels)
    print("全部通过" if ok else "存在问题")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
