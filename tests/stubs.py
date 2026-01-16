from dataclasses import dataclass, field
from typing import Any, List, Tuple

class StubKeyboardController:
    def __init__(self):
        self.events: List[Tuple[str, Any]] = []
    def press(self, k):
        self.events.append(("press", k))
    def release(self, k):
        self.events.append(("release", k))
    def type(self, s: str):
        self.events.append(("type", s))

class StubMouseController:
    def __init__(self):
        self.events: List[Tuple[str, Any]] = []
        self._position = (0, 0)
    @property
    def position(self):
        return self._position
    @position.setter
    def position(self, pos):
        self._position = pos
        self.events.append(("move", pos))
    def press(self, btn):
        self.events.append(("mpress", btn))
    def release(self, btn):
        self.events.append(("mrelease", btn))
    def scroll(self, dx, dy):
        self.events.append(("scroll", (dx, dy)))

class StubStatus:
    def __init__(self):
        self.text = ""
    def config(self, **kwargs):
        self.text = kwargs.get("text", self.text)

class StubRoot:
    def after(self, _ms, func):
        try:
            func()
        except Exception:
            pass
    def winfo_screenwidth(self):
        return 1920
    def winfo_screenheight(self):
        return 1080

class StubApp:
    def __init__(self):
        self.root = StubRoot()
        self.status = StubStatus()

class StubEntry:
    def __init__(self, initial: str = ""):
        self._val = initial
    def get(self):
        return self._val
    def delete(self, *_):
        self._val = ""
    def insert(self, _idx, txt):
        self._val = str(txt)
    def config(self, **_kwargs):
        pass
