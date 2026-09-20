"""游戏状态机。"""

from enum import Enum, auto


class GameState(Enum):
    """游戏的八个状态。

    开始页有四个入口，对应三个玩法与一页说明：
    - ``RULES``：规则介绍（玩法 + 按键功能表）；
    - ``BASIC_SELECT`` / ``LETTER_SELECT``：两个玩法的选关页；
    - 随机关卡不进选关页，直接开一局。
    """

    START = auto()          # 开始界面（四个入口）
    RULES = auto()          # 规则介绍
    BASIC_SELECT = auto()   # 基础玩法选关（12 关）
    LETTER_SELECT = auto()  # 字母玩法选关（26 个字母）
    PLAYING = auto()        # 游戏进行中
    LEVEL_CLEAR = auto()    # 单关通关
    GAME_OVER = auto()      # 挑战失败
    ALL_CLEAR = auto()      # 某个玩法全部通关
