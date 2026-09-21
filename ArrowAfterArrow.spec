# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：把「一箭又一箭」打成**单文件 exe**。

推荐用封装好的脚本，它会先生成图标再调用本文件::

    python tools/build_exe.py

也可以手动::

    pyinstaller ArrowAfterArrow.spec --noconfirm

几个刻意的选择：

- **datas / binaries 全空**：游戏运行时**不读任何图片、音频素材** ——
  图形由代码绘制、音效程序合成（`assets/` 里只有给 README 和博客用的截图），
  所以包里除了代码和 pygame 自带的 DLL，不需要额外资源。图标走 `icon=`，
  由 PyInstaller 塞进 exe 的资源段，不参与运行时打包。
- **console=False**：双击直接进游戏，不弹黑框。代价是启动期的报错不会显示在
  控制台上，改用 PyInstaller 自带的弹窗（`disable_windowed_traceback=False`）。
- **upx=False**：UPX 压缩会让部分杀软把 exe 误判成风险程序，单文件包本来就不大，
  不值得为这点体积换一个「可能被拦」的风险。
- **excludes**：测试与打包期才用到的库（在干净虚拟环境里本来也没装，
  这里显式写一遍，避免以后在本机全局环境里打包时被顺带塞进去）。
"""


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'numpy', 'PIL', 'tkinter', 'setuptools', 'pip'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArrowAfterArrow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
