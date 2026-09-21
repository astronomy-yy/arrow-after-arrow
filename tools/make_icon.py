"""把 ``game.appicon`` 画出来的图标落成打包要用的文件。

用法（需要 pygame 与 Pillow）::

    python tools/make_icon.py

写出两个文件：

- ``assets/icon.ico`` —— 多尺寸（256 / 128 / 64 / 48 / 32 / 16），喂给 PyInstaller；
- ``assets/icon.png`` —— 256×256 预览图，给文档和博客用。

两者都是从 ``game/appicon.py`` 现场画出来的，所以改了图标只需重跑本脚本，
不需要维护任何图片素材；游戏运行时也不读这两个文件。
"""

import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame                                     # noqa: E402
from PIL import Image                             # noqa: E402

from game import appicon                          # noqa: E402

BIG = 256
ICO_SIZES = [256, 128, 64, 48, 32, 16]
ICO_PATH = os.path.join(ROOT, "assets", "icon.ico")
PNG_PATH = os.path.join(ROOT, "assets", "icon.png")


def _report(path):
    """打印 ICO 里每个尺寸的字节数与存放格式，便于一眼确认生成正常。"""
    with open(path, "rb") as handle:
        raw = handle.read()
    count = struct.unpack_from("<H", raw, 4)[0]
    rows = []
    for index in range(count):
        width, height, _colors, _res, _planes, bits, size, offset = \
            struct.unpack_from("<BBBBHHII", raw, 6 + index * 16)
        body = raw[offset:offset + 4]
        kind = "PNG" if body == b"\x89PNG" else "BMP"
        rows.append((width or 256, height or 256, bits, size, kind))
    rows.sort(reverse=True)
    for width, height, bits, size, kind in rows:
        print(f"    {width:>3}x{height:<3} {bits:>2}bit {kind} "
              f"{size:>7} 字节")
    return rows


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))          # dummy 驱动下的占位显示

    image = appicon.surface(BIG)
    raw = pygame.image.tobytes(image, "RGBA")
    picture = Image.frombytes("RGBA", (BIG, BIG), raw)

    os.makedirs(os.path.dirname(ICO_PATH), exist_ok=True)
    # bitmap_format 必须显式给 "bmp"：Pillow 从 9.x 起默认把每个尺寸都存成
    # PNG 条目，而传统 BMP(DIB) 条目才是 Windows shell 各处都吃的格式。
    # 代价是体积大一些（32 位色 + AND 掩码），但打包进 exe 后可以忽略。
    picture.save(ICO_PATH, sizes=[(s, s) for s in ICO_SIZES],
                 bitmap_format="bmp")
    picture.save(PNG_PATH)

    print(f"已生成 {os.path.relpath(ICO_PATH, ROOT)}：")
    _report(ICO_PATH)
    print(f"已生成 {os.path.relpath(PNG_PATH, ROOT)}：{BIG}x{BIG} 预览图")
    pygame.quit()


if __name__ == "__main__":
    main()
