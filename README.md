# 一箭又一箭（Arrow After Arrow）

一个用 Python + Pygame 实现的益智小游戏。点击棋盘上的箭头：若箭头飞行方向上没有其他箭头阻挡，箭头飞出并消失；若被挡住则失误一次。消除棋盘上全部箭头即可通关，失误耗尽则失败。

## 开发环境

- 操作系统：Windows
- Python：3.14
- pygame-ce 2.5.x（导入名仍为 `pygame`，API 与 pygame 2.x 兼容）
- pytest 9.x（单元测试）

> 说明：Python 3.14 上官方 pygame 暂无预编译安装包，直接 `pip install pygame` 会尝试本地源码编译并报错（`No module named 'setuptools._distutils.msvccompiler'`），因此本项目使用社区版 **pygame-ce**，安装包名不同但代码里照常 `import pygame`。

## 安装方法

```bash
pip install -r requirements.txt
```

## 运行方法

```bash
python main.py
```

## 操作说明

- 鼠标点击棋盘上的箭头，让它沿自身方向飞出
- 方向上无其他箭头：飞出并消失，剩余箭头数 -1
- 方向上有其他箭头：被挡住不消失，剩余失误次数 -1，并给出晃动/变红反馈
- 消除全部箭头：通关，进入下一关
- 失误次数耗尽：本关失败，可重新开始
- 游戏中可随时点击"重新开始"按钮恢复本关初始布局

## 项目结构

```text
arrow-after-arrow/
├── main.py              # 游戏入口
├── game/
│   ├── settings.py      # 全局配置（窗口、颜色、布局）
│   ├── arrow.py         # 方向枚举与箭头实体
│   ├── level.py         # 关卡数据
│   ├── board.py         # 棋盘与路径检测
│   └── states.py        # 游戏状态机
├── assets/screenshots/  # 游戏截图
├── tests/test_path.py   # 路径检测单元测试
├── requirements.txt
└── .gitignore
```

## 游戏截图

（阶段 7 界面完成后补充：开始界面 / 游戏界面 / 通关界面 / 失败界面）
