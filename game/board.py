"""棋盘：负责关卡网格的加载、重置、箭头计数与删除。

路径检测 can_fly 将在阶段 5 加入。
"""

import copy

from game.arrow import CHAR_TO_DIRECTION, EMPTY


class Board:
    """保存一关的棋盘状态。"""

    def __init__(self, level):
        # 保留关卡原始数据；网格使用深拷贝，避免污染 LEVELS 原始数据
        self._level = level
        self._initial_grid = copy.deepcopy(level["grid"])
        self._max_mistakes = level["mistakes"]
        self.reset()

    def reset(self):
        """恢复本关初始布局、剩余箭头数和失误次数。"""
        self._grid = copy.deepcopy(self._initial_grid)
        self.mistakes = self._max_mistakes
        self._remaining = self._count_arrows()

    @property
    def max_mistakes(self):
        """本关失误次数上限（用于界面绘制失误圆点）。"""
        return self._max_mistakes


    def _count_arrows(self):
        """统计当前网格中的箭头总数。"""
        return sum(cell != EMPTY for row in self._grid for cell in row)

    @property
    def rows(self):
        """棋盘行数。"""
        return len(self._grid)

    @property
    def cols(self):
        """棋盘列数。"""
        return len(self._grid[0])

    @property
    def remaining(self):
        """剩余箭头数。"""
        return self._remaining

    def in_bounds(self, r, c):
        """坐标是否在棋盘范围内（阶段 5 路径检测会用到）。"""
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get(self, r, c):
        """获取某格内容：返回 '.' 或方向字符。"""
        return self._grid[r][c]

    def get_direction(self, r, c):
        """获取某格箭头的方向枚举；该格为空时返回 None。"""
        return CHAR_TO_DIRECTION.get(self._grid[r][c])

    def is_empty(self, r, c):
        """该格是否为空。"""
        return self._grid[r][c] == EMPTY

    def remove_arrow(self, r, c):
        """删除某格箭头并让剩余数 -1；若本来就是空格则忽略。"""
        if not self.is_empty(r, c):
            self._grid[r][c] = EMPTY
            self._remaining -= 1
