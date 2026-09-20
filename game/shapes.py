"""关卡形状遮罩。

棋盘先按 rows x cols 划格，再用形状函数筛出真正参与游戏的格子。
线段只铺在遮罩内，于是整关看起来就是「一个圆」「一颗心」等等，
与参考图 / 录屏里的关卡造型一致。

字母玩法的 26 关用的是 ``shape="letter"``：遮罩由 game/letters.py 的
点阵字模栅格化而来，整盘铺成一个大写字母。
"""

SHAPE_NAMES = [
    ("rect", "方形"),
    ("round", "圆形"),
    ("diamond", "菱形"),
    ("heart", "心形"),
    ("triangle", "三角"),
    ("cross", "十字"),
    ("hourglass", "沙漏"),
    ("ring", "圆环"),
]


def _ellipse(rows, cols, ratio=1.0):
    """椭圆：返回满足 (dr/a)^2 + (dc/b)^2 <= 1 的格子。"""
    cr = (rows - 1) / 2
    cc = (cols - 1) / 2
    a = cr + 0.5
    b = cc + 0.5
    cells = set()
    for r in range(rows):
        for c in range(cols):
            dr = (r - cr) / a
            dc = (c - cc) / b
            if dr * dr + dc * dc <= ratio:
                cells.add((r, c))
    return cells


def _heart(rows, cols):
    """心形：用经典隐函数 (x^2+y^2-1)^3 - x^2 y^3 <= 0。"""
    cr = (rows - 1) / 2
    cc = (cols - 1) / 2
    scale = min(rows, cols) / 2.6
    cells = set()
    for r in range(rows):
        for c in range(cols):
            x = (c - cc) / scale
            y = -(r - cr) / scale + 0.28   # y 轴向上，整体上移让心尖朝下
            v = (x * x + y * y - 1) ** 3 - x * x * y ** 3
            if v <= 0:
                cells.add((r, c))
    return cells


def _diamond(rows, cols):
    cr = (rows - 1) / 2
    cc = (cols - 1) / 2
    a = cr + 0.5
    b = cc + 0.5
    cells = set()
    for r in range(rows):
        for c in range(cols):
            if abs(r - cr) / a + abs(c - cc) / b <= 1.0:
                cells.add((r, c))
    return cells


def _triangle(rows, cols):
    """等腰三角形，尖端朝上。"""
    cells = set()
    for r in range(rows):
        half = (cols / 2) * ((r + 1) / rows)
        cc = (cols - 1) / 2
        for c in range(cols):
            if abs(c - cc) <= half:
                cells.add((r, c))
    return cells


def _cross(rows, cols):
    """十字：横竖两条带，带宽度约为三成。"""
    band_r = max(1, int(rows * 0.32))
    band_c = max(1, int(cols * 0.32))
    r0 = (rows - band_r) // 2
    c0 = (cols - band_c) // 2
    cells = set()
    for r in range(rows):
        for c in range(cols):
            row_band = r0 <= r < r0 + band_r
            col_band = c0 <= c < c0 + band_c
            if row_band or col_band:
                cells.add((r, c))
    return cells


def _hourglass(rows, cols):
    """沙漏：上下宽、中间收腰。"""
    cr = (rows - 1) / 2
    cells = set()
    for r in range(rows):
        t = abs(r - cr) / (cr + 0.5)            # 0 中间 -> 1 两端
        half = ((cols - 1) / 2) * (0.12 + 0.88 * t)
        cc = (cols - 1) / 2
        for c in range(cols):
            if abs(c - cc) <= half:
                cells.add((r, c))
    return cells


def _ring(rows, cols, thickness=0.34):
    """圆环：外圆挖掉内圆（内圆半径取外圆的一半左右）。"""
    outer = _ellipse(rows, cols)
    cr = (rows - 1) / 2
    cc = (cols - 1) / 2
    a = cr + 0.5
    b = cc + 0.5
    limit = (1.0 - thickness) ** 2
    cells = set()
    for (r, c) in outer:
        dr = (r - cr) / a
        dc = (c - cc) / b
        if dr * dr + dc * dc >= limit:
            cells.add((r, c))
    return cells


def cells_of(rows, cols, shape="rect", letter=None):
    """返回形状覆盖的格子集合；未知形状退化为整块矩形。

    ``shape="letter"`` 时走点阵字模（见 game/letters.py），此时必须给出
    ``letter``（"A"~"Z"）；缺参数时同样退化成整块矩形，不会崩。
    """
    if shape == "rect":
        return {(r, c) for r in range(rows) for c in range(cols)}
    if shape == "letter":
        from game.letters import letter_cells
        if letter is None:
            return {(r, c) for r in range(rows) for c in range(cols)}
        return letter_cells(rows, cols, letter)
    if shape == "round":
        return _ellipse(rows, cols)
    if shape == "diamond":
        return _diamond(rows, cols)
    if shape == "heart":
        return _heart(rows, cols)
    if shape == "triangle":
        return _triangle(rows, cols)
    if shape == "cross":
        return _cross(rows, cols)
    if shape == "hourglass":
        return _hourglass(rows, cols)
    if shape == "ring":
        return _ring(rows, cols)
    return {(r, c) for r in range(rows) for c in range(cols)}


def is_connected(cells, diagonal=False):
    """遮罩是否连通（默认四连通，diagonal=True 时按八连通算）。

    字母关里 ``C``、``S``、``J`` 这类斜笔在点阵层面是对角相接的，放大后
    两个方块共享一个角点、看着是一笔连下来的，所以那边用八连通判定。
    """
    if not cells:
        return False
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diagonal:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    start = next(iter(cells))
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in steps:
            neighbor = (r + dr, c + dc)
            if neighbor in cells and neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == len(cells)


def level_cells(level):
    """一关的遮罩格子（形状关走 cells_of，字母关带上字母）。"""
    return cells_of(level.get("rows", 9), level.get("cols", 9),
                    level.get("shape", "rect"), level.get("letter"))


def level_cells_connected(level):
    """一关的遮罩是否连通（字母关按八连通算）。"""
    return is_connected(level_cells(level),
                        diagonal=level.get("shape") == "letter")


def ascii_preview(cells, rows, cols):
    """调试用：把遮罩画成字符画。"""
    return "\n".join(
        "".join("#" if (r, c) in cells else "." for c in range(cols))
        for r in range(rows)
    )


def suggested_size(shape, index_hint=0):
    """给每个形状挑一个比较好看的棋盘尺寸。"""
    table = {
        "rect": (12, 9),
        "round": (15, 15),
        "diamond": (15, 15),
        "heart": (15, 15),
        "triangle": (14, 15),
        "cross": (15, 15),
        "hourglass": (16, 13),
        "ring": (15, 15),
    }
    return table.get(shape, (12, 9))


def area(cells):
    """遮罩覆盖的格子数。"""
    return len(cells)
