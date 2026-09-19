"""棋盘：线段箭的加载、占据网格、路径检测、删除、撤销与重置。

线段箭格式见 game/level.py：
- 每支箭由若干上下左右相邻的格子组成（可拐弯），最后一个格子是箭头端；
- 棋盘内部用「占据网格」记录每格属于哪支箭；
- 飞出时各节只沿线段自身的路径流动，身体不会横扫，所以能否飞出
  只取决于箭头端朝向到边界之间有没有其他线段。
"""

import copy

from game import theme
from game.arrow import CHAR_TO_DIRECTION, DIRECTION_DELTA
from game.settings import ARROW_PALETTE


class Arrow:
    """一条线段箭。"""

    def __init__(self, arrow_id, data):
        self.id = arrow_id
        self.cells = [tuple(cell) for cell in data["cells"]]  # 尾端 -> 箭头端
        self.head = self.cells[-1]
        self.direction = CHAR_TO_DIRECTION[data["dir"]]
        self.color_index = data.get("color", arrow_id % len(ARROW_PALETTE))

    @property
    def color(self):
        """按当前主题解析出的线色（切日夜时自动跟着变）。"""
        return theme.arrow_color(self.color_index)

    def __repr__(self):  # pragma: no cover - 调试用
        return f"<Arrow {self.id} {self.direction.value} {self.cells}>"


class Board:
    """一关的棋盘状态。"""

    def __init__(self, level):
        self._level = level
        self.rows = level.get("rows", 9)
        self.cols = level.get("cols", 9)
        self._max_mistakes = level["mistakes"]
        self._initial_arrows = copy.deepcopy(level["arrows"])
        # 撤销栈：每成功飞出 / 点错一步压一份快照
        self._history = []
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
        self.wrong_ids = set()      # 点错过的箭（常驻暗红标记）
        self._history = []

    # ---------------- 基本查询 ----------------

    @property
    def remaining(self):
        """剩余箭的条数。"""
        return self._remaining

    @property
    def max_mistakes(self):
        """本关失误次数上限。"""
        return self._max_mistakes

    @property
    def total(self):
        """本关初始箭数。"""
        return len(self._initial_arrows)

    @property
    def cleared_count(self):
        """已飞出的箭数。"""
        return self.total - self._remaining

    @property
    def progress(self):
        """清盘进度，0.0 ~ 1.0。"""
        return self.cleared_count / self.total if self.total else 1.0

    def in_bounds(self, r, c):
        """坐标是否在棋盘内。"""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def arrow_at(self, r, c):
        """返回该格上的箭，空格返回 None。"""
        if not self.in_bounds(r, c):
            return None
        return self._occ[r][c]

    def flyable_arrows(self):
        """当前所有能飞出的箭。"""
        return [arrow for arrow in self.arrows if self.can_fly_arrow(arrow)]

    # ---------------- 路径检测 ----------------

    def can_fly_arrow(self, arrow):
        """箭头沿自身方向到边界之间是否没有其他线段。

        蛇形式滑出时身体只经过自己原来的格子，因此只需检查
        箭头端射线上是否有别的线段（跳过线段自身）。
        """
        dr, dc = DIRECTION_DELTA[arrow.direction]
        r, c = arrow.head
        r += dr
        c += dc
        while self.in_bounds(r, c):
            other = self._occ[r][c]
            if other is not None and other is not arrow:
                return False
            r += dr
            c += dc
        return True

    def can_fly(self, r, c):
        """判断某格上的箭能否飞出；空格返回 False。"""
        arrow = self.arrow_at(r, c)
        return self.can_fly_arrow(arrow) if arrow is not None else False

    # ---------------- 修改棋盘 ----------------

    def snapshot(self):
        """把当前局面压入撤销栈。"""
        self._history.append({
            "remaining": [arrow.id for arrow in self.arrows],
            "mistakes": self.mistakes,
            "wrong": set(self.wrong_ids),
        })

    @property
    def can_undo(self):
        """是否还有可以撤销的步骤。"""
        return bool(self._history)

    def undo(self):
        """回退一步；成功返回 True。"""
        if not self._history:
            return False
        state = self._history.pop()
        alive = set(state["remaining"])
        self.arrows = []
        self._occ = [[None] * self.cols for _ in range(self.rows)]
        for arrow_id, data in enumerate(self._initial_arrows):
            if arrow_id not in alive:
                continue
            arrow = Arrow(arrow_id, data)
            self.arrows.append(arrow)
            for (r, c) in arrow.cells:
                self._occ[r][c] = arrow
        self._remaining = len(self.arrows)
        self.mistakes = state["mistakes"]
        self.wrong_ids = set(state["wrong"])
        return True

    def mark_wrong(self, arrow):
        """把点错的箭记下来，界面会把它画成暗红。"""
        self.wrong_ids.add(arrow.id)

    def remove_arrow(self, arrow):
        """把整支箭从棋盘上移除，剩余条数 -1。"""
        for (r, c) in arrow.cells:
            self._occ[r][c] = None
        if arrow in self.arrows:
            self.arrows.remove(arrow)
            self._remaining -= 1
