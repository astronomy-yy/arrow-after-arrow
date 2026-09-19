"""存档：进度、金币、星级、主题与设置，存在用户目录下的 JSON 文件里。"""

import json
import os

SAVE_DIR = os.path.join(os.path.expanduser("~"), ".arrow_after_arrow")
SAVE_PATH = os.path.join(SAVE_DIR, "save.json")

DEFAULT = {
    "cleared": [],          # 已通关的关卡 id
    "stars": {},            # {"关卡id": 星级 1~3}
    "coins": 10,            # 金币
    "theme": "night",       # 主题
    "sound": True,          # 音效开关
    "guide": True,          # 辅助线开关
    "best_time": {},        # {"关卡id": 剩余秒数}
    "current": 1,           # 上次玩到的关卡 id
}


def _blank():
    return json.loads(json.dumps(DEFAULT))


class Save:
    """一个很薄的存档包装：读进来当字典用，改动后调 flush() 落盘。"""

    def __init__(self, path=SAVE_PATH):
        self.path = path
        self.data = _blank()
        self.load()

    def load(self):
        """读存档；文件不存在或损坏都退回默认值。"""
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            return self.data
        if isinstance(raw, dict):
            for key, value in DEFAULT.items():
                got = raw.get(key, value)
                # 类型对得上才采用，避免手改坏的存档把游戏搞崩
                if isinstance(got, type(value)):
                    self.data[key] = got
        return self.data

    def flush(self):
        """写盘；没有权限时静默忽略（不影响游戏继续跑）。"""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    # ---- 常用操作 ----

    def mark_clear(self, level_id, stars, coins_left, seconds_left=None):
        """记录一关通关结果。"""
        if level_id not in self.data["cleared"]:
            self.data["cleared"].append(level_id)
        old = self.data["stars"].get(str(level_id), 0)
        if stars > old:
            self.data["stars"][str(level_id)] = stars
        if seconds_left is not None:
            best = self.data["best_time"].get(str(level_id), 0)
            if seconds_left > best:
                self.data["best_time"][str(level_id)] = round(seconds_left)
        self.data["coins"] = coins_left
        self.flush()

    def stars_of(self, level_id):
        return int(self.data["stars"].get(str(level_id), 0))

    def is_cleared(self, level_id):
        return level_id in self.data["cleared"]

    def reset_all(self):
        """清空进度（保留主题与音效设置）。"""
        keep = {k: self.data[k] for k in ("theme", "sound", "guide")}
        self.data = _blank()
        self.data.update(keep)
        self.flush()
