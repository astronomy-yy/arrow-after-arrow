"""一键打包成单文件 exe。

用法（在项目根目录，用装了 pygame / pyinstaller / pillow 的解释器）::

    python tools/build_exe.py

做三件事：

1. 跑 ``tools/make_icon.py`` 重新生成 ``assets/icon.ico``（图标是画出来的，
   改了 ``game/appicon.py`` 就该重跑一次，交给这个脚本一起做省得漏）；
2. 按 ``ArrowAfterArrow.spec`` 调用 PyInstaller 打包；
3. 把产物改名成 ``dist/一箭又一箭.exe``。

单文件 exe 的启动器是靠「附加在自己末尾的归档」找代码的，**跟文件名无关**，
所以改中文名是安全的，改完照样双击就能跑。
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = "ArrowAfterArrow.spec"
BUILD_NAME = "ArrowAfterArrow"          # spec 里的 name（保持 ASCII，稳）
DELIVER_NAME = "一箭又一箭.exe"           # 交付时看到的名字
DIST = os.path.join(ROOT, "dist")
REQUIRED = ("pygame", "PyInstaller", "PIL")


def _check_requirements():
    missing = []
    for name in REQUIRED:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print("缺少打包依赖：" + "、".join(missing))
        print("请先在打包用的解释器里安装："
              f"{sys.executable} -m pip install pygame-ce pyinstaller pillow")
        return False
    return True


def _run(command):
    print("+ " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode == 0


def main():
    if not _check_requirements():
        return 1

    if not _run([sys.executable, os.path.join("tools", "make_icon.py")]):
        print("生成图标失败")
        return 1

    if not _run([sys.executable, "-m", "PyInstaller", SPEC, "--noconfirm",
                 "--log-level", "WARN"]):
        print("打包失败")
        return 1

    built = os.path.join(DIST, BUILD_NAME + ".exe")
    if not os.path.exists(built):
        print(f"打包命令成功了，但没找到 {built}")
        return 1

    deliver = os.path.join(DIST, DELIVER_NAME)
    if os.path.exists(deliver):
        os.remove(deliver)
    shutil.move(built, deliver)

    size = os.path.getsize(deliver) / 1024 / 1024
    print()
    print(f"完成：{os.path.relpath(deliver, ROOT)}（{size:.1f} MB）")
    print("说明：单文件 exe 每次启动会先把内容解到临时目录，首次启动慢一点；")
    print("      进度存档在用户目录 ~/.arrow_after_arrow/save.json，换机不影响。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
