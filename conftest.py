"""pytest 配置：把项目根目录加进模块搜索路径，并强制无窗口运行。

所有测试都在 SDL 的 dummy 驱动下跑，不会弹出游戏窗口，也不需要显示器。
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
