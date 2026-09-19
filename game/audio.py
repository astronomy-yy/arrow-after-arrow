"""音效：不依赖任何素材文件，直接用 numpy 合成几个短音。

好处是打包成 exe 时不用附带 wav；坏处是只能做简单的提示音。
mixer 初始化失败（比如无声卡 / 无头环境）时全部降级为静默。
"""

import math

import pygame

try:                                    # numpy 在，就能合成音效
    import numpy as np
except ImportError:                     # pragma: no cover
    np = None

SAMPLE_RATE = 44100
CHANNELS = 2
_enabled = True
_ready = False
_sounds = {}


def init():
    """初始化 mixer 并合成音效；失败则保持静默。"""
    global _ready
    if _ready:
        return True
    if np is None:
        return False
    try:
        # pygame.init() 已经用默认参数初始化过 mixer，先关掉再按我们的来
        pygame.mixer.quit()
        pygame.mixer.init(SAMPLE_RATE, -16, CHANNELS, 512)
    except pygame.error:
        return False

    _sounds["fly"] = _make_sweep(660, 1180, 0.13, 0.24, "sine")
    _sounds["block"] = _make_sweep(320, 150, 0.22, 0.30, "square")
    _sounds["click"] = _make_sweep(880, 880, 0.05, 0.16, "sine")
    _sounds["hint"] = _make_sweep(1180, 1560, 0.14, 0.20, "sine")
    _sounds["clear"] = _make_arpeggio([660, 880, 1108, 1318], 0.10, 0.24)
    _sounds["fail"] = _make_arpeggio([440, 370, 294, 220], 0.13, 0.26)
    _ready = True
    return True


def _envelope(samples, attack=0.01):
    """做一个简单的淡入淡出包络，避免爆音。"""
    n = len(samples)
    if n == 0:
        return samples
    ramp = max(1, int(attack * SAMPLE_RATE))
    env = np.ones(n)
    head = min(ramp, n)
    env[:head] = np.linspace(0.0, 1.0, head)
    tail = min(ramp * 3, n)
    env[n - tail:] = np.linspace(1.0, 0.0, tail)
    return samples * env


def _to_sound(wave, volume):
    wave = np.clip(wave * volume, -1.0, 1.0)
    data = (wave * 32767).astype(np.int16)
    stereo = np.repeat(data.reshape(-1, 1), CHANNELS, axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))


def _make_sweep(freq_from, freq_to, duration, volume, wave="sine"):
    n = int(SAMPLE_RATE * duration)
    if n <= 0:
        return None
    t = np.arange(n) / SAMPLE_RATE
    # 线性扫频：相位是频率的积分
    freq = np.linspace(freq_from, freq_to, n)
    phase = 2 * math.pi * np.cumsum(freq) / SAMPLE_RATE
    if wave == "square":
        raw = np.sign(np.sin(phase))
    else:
        raw = np.sin(phase)
    return _to_sound(_envelope(raw), volume)


def _make_arpeggio(freqs, note, volume):
    parts = []
    for freq in freqs:
        n = int(SAMPLE_RATE * note)
        t = np.arange(n) / SAMPLE_RATE
        raw = np.sin(2 * math.pi * freq * t)
        parts.append(_envelope(raw, attack=0.005))
    return _to_sound(np.concatenate(parts), volume)


def set_enabled(flag):
    """总开关。"""
    global _enabled
    _enabled = bool(flag)
    return _enabled


def enabled():
    return _enabled


def play(name):
    """播放音效；没初始化好或关掉了就直接返回。"""
    if not _enabled or not _ready:
        return
    sound = _sounds.get(name)
    if sound is not None:
        try:
            sound.play()
        except pygame.error:            # pragma: no cover
            pass
