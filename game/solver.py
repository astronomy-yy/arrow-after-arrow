"""AI 求解器：给定当前局面，找一条把剩余线段全部清空的点击顺序。

思路是最朴素的深度优先搜索 + 记忆化：

- 局面 = 还剩下哪些线段箭（用 id 集合表示）；
- 可走的一步 = 任意一支「箭头射线上没有别的箭」的线段；
- 同一个局面只失败一次（memo），避免重复搜索；
- 加一个节点上限，超时/超量就退回到「随便挑一支能飞的」当提示。

这样即使是 37 支箭的大关，通常也能在毫秒级返回结果。
"""

from game.arrow import DIRECTION_DELTA


class _Board:
    """求解器专用的轻量棋盘（只保留 id / 格子 / 占据关系）。"""

    def __init__(self, board):
        self.rows = board.rows
        self.cols = board.cols
        self.meta = {}
        self.occ = {}
        for arrow in board.arrows:
            self.meta[arrow.id] = (arrow.head, DIRECTION_DELTA[arrow.direction])
            for cell in arrow.cells:
                self.occ[cell] = arrow.id
        self.alive = set(self.meta)

    def flyable(self):
        """返回所有当前能飞出的箭 id。"""
        out = []
        for arrow_id in self.alive:
            head, (dr, dc) = self.meta[arrow_id]
            r, c = head[0] + dr, head[1] + dc
            blocked = False
            while 0 <= r < self.rows and 0 <= c < self.cols:
                owner = self.occ.get((r, c))
                if owner is not None and owner != arrow_id:
                    blocked = True
                    break
                r += dr
                c += dc
            if not blocked:
                out.append(arrow_id)
        return out

    def state_key(self):
        return frozenset(self.alive)


def solve(board, max_nodes=60000):
    """返回一条完整通关顺序（箭 id 列表）；搜不到返回 None。"""
    state = _Board(board)
    if not state.alive:
        return []

    failed = set()
    order = []
    nodes = [0]

    def dfs():
        if not state.alive:
            return True
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return False
        key = state.state_key()
        if key in failed:
            return False

        for arrow_id in state.flyable():
            state.alive.discard(arrow_id)
            order.append(arrow_id)
            if dfs():
                return True
            order.pop()
            state.alive.add(arrow_id)

        failed.add(key)
        return False

    if dfs():
        return order
    return None


def next_move(board, max_nodes=60000):
    """提示用：返回下一步该点哪支箭；实在解不出来就返回任意能飞的箭。"""
    order = solve(board, max_nodes=max_nodes)
    if order:
        return order[0]
    movable = board.flyable_arrows()
    return movable[0].id if movable else None


def is_solvable(board, max_nodes=60000):
    """当前局面还能不能清空。"""
    return solve(board, max_nodes=max_nodes) is not None


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
