"""方向枚举与方向相关映射。"""

from enum import Enum

# 空格标记
EMPTY = "."


class Direction(Enum):
    """四个飞行方向，枚举值与关卡网格中的字符保持一致。"""

    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"


# 网格字符 -> 方向枚举
CHAR_TO_DIRECTION = {
    "U": Direction.UP,
    "D": Direction.DOWN,
    "L": Direction.LEFT,
    "R": Direction.RIGHT,
}

# 方向 -> (行增量 dr, 列增量 dc)
DIRECTION_DELTA = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}
