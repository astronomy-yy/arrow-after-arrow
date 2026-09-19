"""棋盘：线段箭的加载、占据网格、路径检测、删除与重置。

线段箭格式见 game/level.py：
- 每支箭由若干上下左右相邻的格子组成（可拐弯），最后一个格子是箭头端；
- 棋盘内部用“占据网格”记录每格属于哪支箭；
- can_fly 沿箭头端方向逐格检查，遇到任何被占据的格子即被挡。
"""

import copy

from game.arrow import CHAR_TO_DIRECTION, DIRECTION_DELTA
from game.settings import ARROW_PALETTE


class Arrow:
    """一条线段箭。"""

    def __init__(self, arrow_id, data):
        self.id = arrow_id
        self.cells = [tuple(cell) for cell in data["cells"]]  # 顺序：尾端 -> 箭头端
        self.head = self.cells[-1]
        self.direction = CHAR_TO_DIRECTION[data["dir"]]
        color_index = data.get("color", arrow_id % len(ARROW_PALETTE))
        self.color = ARROW_PALETTE[color_index]


class Board:
    """一关的棋盘状态。"""

    def __init__(self, level):
        self._level = level
        self.rows = level.get("rows", 9)
        self.cols = level.get("cols", 9)
        self._max_mistakes = level["mistakes"]
        self._initial_arrows = copy.deepcopy(level["arrows"])
        self.reset()

    def reset(self):
        """恢复本关初始布局、剩余箭数和失误次数。"""
        self.mistakes = self._max_mistakes
        self.arrows = []
        self._occ = [[None] * self.cols for _ in range(self.rows)]
        for arrow_id, data in enumerate(self._initial_arrows):
            arrow = Arrow(arrow_id, data)
            self.arrows.append(arrow)
            for (r, c) in arrow.cells:
                self._occ[r][c] = arrow
        self._remaining = len(self.arrows)

    @property
    def remaining(self):
        """剩余箭的条数。"""
        return self._remaining

    @property
    def max_mistakes(self):
        """本关失误次数上限。"""
        return self._max_mistakes

    def in_bounds(self, r, c):
        """坐标是否在棋盘内。"""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def arrow_at(self, r, c):
        """返回该格上的箭，空格返回 None。"""
        return self._occ[r][c]

    def can_fly_arrow(self, arrow):
        """判断某支箭沿箭头方向能否无阻挡飞出。"""
        dr, dc = DIRECTION_DELTA[arrow.direction]
        r, c = arrow.head
        r += dr
        c += dc
        while self.in_bounds(r, c):
            if self._occ[r][c] is not None:
                return False
            r += dr
            c += dc
        return True

    def can_fly(self, r, c):
        """判断某格上的箭能否飞出；空格返回 False。"""
        arrow = self._occ[r][c]
        return self.can_fly_arrow(arrow) if arrow is not None else False

    def remove_arrow(self, arrow):
        """把整支箭从棋盘上移除，剩余条数 -1。"""
        for (r, c) in arrow.cells:
            self._occ[r][c] = None
        if arrow in self.arrows:
            self.arrows.remove(arrow)
            self._remaining -= 1
