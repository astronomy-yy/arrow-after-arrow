"""一箭又一箭（Arrow After Arrow）游戏入口。

阶段 0：pygame 环境冒烟测试——能弹出窗口说明环境配置成功。
阶段 4 起将替换为正式游戏（开始界面 / 游戏界面 / 结果界面）。
"""

import sys

import pygame


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    pygame.display.set_caption("一箭又一箭 - 环境测试")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("microsoftyahei,simhei,arial", 30)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((30, 30, 46))
        text = font.render("pygame 环境正常！关闭此窗口退出", True, (255, 255, 255))
        screen.blit(text, (130, 220))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
