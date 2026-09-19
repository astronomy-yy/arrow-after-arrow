"""关卡数据（由 tools/generate_levels.py 用逆向构造法确定性生成）。

每支箭的数据：
- cells：线段占据的格子，顺序为 尾端 -> 箭头端，相邻格上下左右相连，可拐弯；
- dir：箭头方向（"U"/"D"/"L"/"R"），与最后一段走向一致；
- color：game/settings.py 中 ARROW_PALETTE 的颜色索引；
- solution：一条已验证的通关顺序（箭 id 列表，id 即 arrows 列表下标）。
"""

LEVELS = [{'name': '第1关 初露锋芒',
  'mistakes': 3,
  'rows': 9,
  'cols': 9,
  'arrows': [{'cells': [(4, 0), (5, 0)], 'dir': 'R', 'color': 0},
             {'cells': [(8, 6)], 'dir': 'R', 'color': 1},
             {'cells': [(3, 1)], 'dir': 'L', 'color': 2},
             {'cells': [(2, 6)], 'dir': 'L', 'color': 3},
             {'cells': [(8, 8), (7, 8)], 'dir': 'L', 'color': 4},
             {'cells': [(1, 2)], 'dir': 'U', 'color': 5}],
  'solution': [5, 4, 3, 2, 1, 0]},
 {'name': '第2关 曲径通幽',
  'mistakes': 3,
  'rows': 9,
  'cols': 9,
  'arrows': [{'cells': [(0, 0), (0, 1), (0, 2)], 'dir': 'U', 'color': 0},
             {'cells': [(5, 1), (4, 1), (3, 1), (2, 1)], 'dir': 'L', 'color': 1},
             {'cells': [(3, 4), (3, 5), (3, 6), (2, 6)], 'dir': 'U', 'color': 2},
             {'cells': [(4, 3), (5, 3), (6, 3)], 'dir': 'D', 'color': 3},
             {'cells': [(7, 4), (6, 4), (5, 4), (4, 4)], 'dir': 'R', 'color': 4},
             {'cells': [(1, 5), (1, 4)], 'dir': 'U', 'color': 5},
             {'cells': [(6, 0), (5, 0), (4, 0), (3, 0)], 'dir': 'L', 'color': 6},
             {'cells': [(0, 8), (1, 8), (2, 8), (3, 8)], 'dir': 'D', 'color': 7},
             {'cells': [(7, 2), (8, 2)], 'dir': 'R', 'color': 8}],
  'solution': [8, 7, 6, 5, 4, 3, 2, 1, 0]},
 {'name': '第3关 满盘皆兵',
  'mistakes': 4,
  'rows': 9,
  'cols': 9,
  'arrows': [{'cells': [(5, 0), (4, 0), (3, 0)], 'dir': 'L', 'color': 0},
             {'cells': [(2, 4), (1, 4), (0, 4), (0, 5)], 'dir': 'R', 'color': 1},
             {'cells': [(3, 5), (4, 5), (4, 6)], 'dir': 'R', 'color': 2},
             {'cells': [(4, 2), (5, 2), (6, 2)], 'dir': 'D', 'color': 3},
             {'cells': [(4, 8), (3, 8), (2, 8), (1, 8)], 'dir': 'U', 'color': 4},
             {'cells': [(7, 0), (7, 1)], 'dir': 'R', 'color': 5},
             {'cells': [(8, 7), (8, 8)], 'dir': 'R', 'color': 6},
             {'cells': [(4, 3), (5, 3)], 'dir': 'R', 'color': 7},
             {'cells': [(1, 6), (0, 6)], 'dir': 'R', 'color': 8},
             {'cells': [(6, 5), (6, 4), (5, 4), (5, 5)], 'dir': 'R', 'color': 0},
             {'cells': [(8, 4), (8, 5), (8, 6)], 'dir': 'D', 'color': 1},
             {'cells': [(4, 1), (5, 1), (6, 1), (6, 0)], 'dir': 'L', 'color': 2}],
  'solution': [11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]}]
