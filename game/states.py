"""游戏状态机。"""

from enum import Enum, auto


class GameState(Enum):
    """游戏的六个状态。"""

    START = auto()         # 开始界面
    LEVEL_SELECT = auto()  # 关卡选择
    PLAYING = auto()       # 游戏进行中
    LEVEL_CLEAR = auto()   # 单关通关
    GAME_OVER = auto()     # 挑战失败
    ALL_CLEAR = auto()     # 全部关卡通关
