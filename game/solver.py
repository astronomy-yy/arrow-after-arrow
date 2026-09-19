"""AI 求解器：给定当前局面，找一条把剩余线段全部清空的点击顺序。

## 为什么是拓扑排序，而不是搜索

一支箭能不能飞，只取决于**箭头射线上有没有别的箭**；飞出去只是把自己
从盘上拿掉，不会动别人。所以可以定义一个有向关系：

    a 挡 b   ⟺   a 的身体压在 b 的箭头射线上

于是 b 能飞 ⟺ 所有挡着 b 的箭都不在了。整个问题就退化成「给这张有向图
找一个拓扑序」：

- 图无环 → 拓扑序就是一条通关顺序，而且**随便哪个拓扑序都行**；
- 图有环（两支队互相封死）→ 环里谁都不能先走，必然无解。

Kahn 算法一遍 O(n²) 就出结果，箭数几十支也是毫秒级。

之前这里写的是「深度优先搜索 + 失败局面记忆化」，在有阻挡的盘面上会
指数爆炸：每步平均四五支可飞，深度一二十层，60 万节点上限瞬间打满，
于是**明明有解的关卡被报成无解**，提示和 AI 自动求解直接失效。
"""

from game.arrow import DIRECTION_DELTA


def ray_cells(head, direction, rows, cols):
    """从箭头端沿朝向到棋盘边界的整条射线（不含箭头自己那格）。"""
    dr, dc = DIRECTION_DELTA[direction]
    r, c = head[0] + dr, head[1] + dc
    out = []
    while 0 <= r < rows and 0 <= c < cols:
        out.append((r, c))
        r += dr
        c += dc
    return out


def blockers_map(board):
    """返回 {箭 id: 挡住它的箭 id 集合}。

    同一支箭的不同节压在同一条射线上也只算一次。
    """
    owner = {}
    for arrow in board.arrows:
        for cell in arrow.cells:
            owner.setdefault(cell, set()).add(arrow.id)

    out = {}
    for arrow in board.arrows:
        blockers = set()
        for cell in ray_cells(arrow.head, arrow.direction,
                              board.rows, board.cols):
            for other in owner.get(cell, ()):
                if other != arrow.id:
                    blockers.add(other)
        out[arrow.id] = blockers
    return out


def free_ids(board):
    """当前所有能直接飞出的箭 id（= 拓扑入度为 0 的那批）。"""
    blockers = blockers_map(board)
    return sorted(aid for aid, bs in blockers.items() if not bs)


def solve(board):
    """返回一条完整通关顺序（箭 id 列表）；真的无解时才返回 None。"""
    blockers = blockers_map(board)
    if not blockers:
        return []

    # 反向索引：拿掉箭 a 之后，哪些箭少了一个挡者
    releases = {arrow_id: set() for arrow_id in blockers}
    for arrow_id, bs in blockers.items():
        for blocker in bs:
            releases[blocker].add(arrow_id)

    pending = {arrow_id: set(bs) for arrow_id, bs in blockers.items()}
    ready = sorted(aid for aid, bs in pending.items() if not bs)
    order = []
    while ready:
        arrow_id = ready.pop()              # 从大到小取，结果稳定可复现
        order.append(arrow_id)
        for other in sorted(releases[arrow_id]):
            pending[other].discard(arrow_id)
            if not pending[other]:
                ready.append(other)

    if len(order) != len(pending):          # 还有剩余 → 图里有环
        return None
    return order


def next_move(board):
    """提示用：返回下一步该点哪支箭；真的无解就返回任意能飞的箭。"""
    order = solve(board)
    if order:
        return order[0]
    movable = board.flyable_arrows()
    return movable[0].id if movable else None


def is_solvable(board):
    """当前局面还能不能清空。"""
    return solve(board) is not None


def apply_solution(board, order):
    """把求解结果真的执行一遍（给「AI 自动求解」演示用）。"""
    by_id = {arrow.id: arrow for arrow in board.arrows}
    for arrow_id in order:
        arrow = by_id.get(arrow_id)
        if arrow is None or not board.can_fly_arrow(arrow):
            return False
        board.remove_arrow(arrow)
    return board.remaining == 0


def greedy_hint(board):
    """最省事的提示：随便挑一支现在就能飞的箭。"""
    movable = board.flyable_arrows()
    return movable[0].id if movable else None
