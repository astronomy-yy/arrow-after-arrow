# -*- coding: utf-8 -*-
"""关卡生成脚本：用 game/generator.py 的逆向构造法重写 game/level.py。

用法（在项目根目录）：
    python tools/generate_levels.py            # 全部重新生成
    python tools/generate_levels.py 3          # 只重新生成第 3 关
    python tools/generate_levels.py --check    # 只校验现有 level.py

生成出来的每一关都做过完整模拟校验：按 solution 顺序点击，每一步
箭头都必须真的能飞出去。
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.generator import build_level, difficulty, fill_ratio  # noqa: E402
from game.shapes import cells_of, is_connected                  # noqa: E402

# (名字, 形状, 行, 列, 种子, 时限秒)
PLAN = [
    ("第1关 初露锋芒", "rect", 12, 9, 1101021, 240),
    ("第2关 渐入佳境", "rect", 13, 10, 2202024, 260),
    ("第3关 圆转如意", "round", 11, 11, 3303008, 240),
    ("第4关 菱光乍现", "diamond", 13, 13, 4404016, 260),
    ("第5关 十字路口", "cross", 13, 13, 5505032, 260),
    ("第6关 心之所向", "heart", 13, 13, 6606048, 260),
    ("第7关 长街深巷", "rect", 15, 11, 7707056, 300),
    ("第8关 步步登高", "triangle", 12, 13, 8808064, 280),
    ("第9关 大盘如月", "round", 15, 15, 9909072, 320),
    ("第10关 沙漏流转", "hourglass", 14, 12, 11101088, 300),
    ("第11关 环环相扣", "ring", 15, 15, 12121104, 320),
    ("第12关 满盘皆兵", "rect", 18, 13, 13131200, 360),
]

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

重新生成：python tools/generate_levels.py
"""

'''


def build_one(index):
    name, shape, rows, cols, seed, limit = PLAN[index]
    t0 = time.time()
    # 大造型的填充率方差大，靠多随机重启挑最满的一版（一关也就几百毫秒）
    level = build_level(rows, cols, shape, seed, name=name,
                        mistakes=3, time_limit=limit, max_attempts=200)
    if level is None:
        raise SystemExit(f"第 {index + 1} 关生成失败：{shape} {rows}x{cols}")
    level["id"] = index + 1
    print(f"  {name:12s} {shape:10s} {rows:2d}x{cols:2d} "
          f"箭数={len(level['arrows']):3d} "
          f"填充率={fill_ratio(level):.2f} "
          f"难度={difficulty(level):5.1f} 耗时={time.time() - t0:.1f}s")
    return level


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


def check(levels):
    """只读校验：形状连通、solution 全程可飞。"""
    from game.board import Board

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
        flag = "OK " if (connected and solution_ok) else "BAD"
        print(f"  [{flag}] 第{index + 1}关 {level['name']:12s} "
              f"形状连通={connected} solution可通关={solution_ok} "
              f"箭数={len(level['arrows'])}")
        ok = ok and connected and solution_ok
    return ok


def main():
    args = sys.argv[1:]
    target = os.path.join(ROOT, "game", "level.py")
    if target not in sys.path:
        pass

    if "--check" in args:
        from game.level import LEVELS
        print("校验 game/level.py：")
        raise SystemExit(0 if check(LEVELS) else 1)

    if args and args[0].isdigit():
        only = int(args[0]) - 1
        from game.level import LEVELS
        levels = list(LEVELS)
        print(f"重新生成第 {only + 1} 关：")
        levels[only] = build_one(only)
    else:
        print("生成全部关卡：")
        levels = [build_one(i) for i in range(len(PLAN))]

    dump(levels, target)
    print("校验新生成的关卡：")
    check(levels)


if __name__ == "__main__":
    main()
