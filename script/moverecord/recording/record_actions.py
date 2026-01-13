"""키 및 마우스 녹화 함수"""
import time
import threading
from pathlib import Path
import sys
import importlib
from pynput.keyboard import Listener, Controller as KeyController
from pynput.mouse import Listener as MouseListener, Controller as MouseController


def record_actions(duration_s: float = None, sample_ms: int = 0, meta_extra=None, time_offset_ms: int = 0):
    """키 및 마우스 액션 녹화"""
    # 실행 중인 moveRecord 모듈을 먼저 찾는다 (디버거/런처로 실행 시 __main__이 다른 모듈일 수 있음)
    main = None
    for m in list(sys.modules.values()):
        try:
            mf = getattr(m, '__file__', '') or ''
            if mf.endswith('moveRecord.py') and hasattr(m, 'stop_event') and hasattr(m, 'recording'):
                main = m
                break
        except Exception:
            continue
    if main is None:
        project_root = Path(__file__).resolve().parents[3]  # .../2026macroTest
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        main = importlib.import_module('script.moverecord.moveRecord')
        # alias 등록해 이후 재사용
        sys.modules['script.moverecord.moveRecord'] = main
    
    if main.recording:
        return None
    
    main.recording = True
    main.record_events = []
    
    start = time.time()
    last_move_ms = -9999
    
    def _now_ms():
        return int((time.time() - start) * 1000) + time_offset_ms
    
    controller = KeyController()
    mouse_controller = MouseController()
    
    def on_move(x, y):
        nonlocal last_move_ms
        now = _now_ms()
        if sample_ms and (now - last_move_ms) < int(sample_ms):
            return
        last_move_ms = now
        main.record_events.append((now, 'mouse_move', x, y))
    
    def on_click(x, y, button, pressed):
        main.record_events.append((_now_ms(), 'mouse_click', str(button), 'press' if pressed else 'release', x, y))
    
    def on_scroll(x, y, dx, dy):
        main.record_events.append((_now_ms(), 'mouse_scroll', dx, dy, x, y))
    
    def on_press(k):
        try:
            ch = k.char
        except Exception:
            ch = str(k)
        main.record_events.append((_now_ms(), 'key_down', ch))
    
    def on_release(k):
        try:
            ch = k.char
        except Exception:
            ch = str(k)
        main.record_events.append((_now_ms(), 'key_up', ch))
    
    m_listener = None
    k_listener = None
    try:
        # start listeners
        m_listener = MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        k_listener = Listener(on_press=on_press, on_release=on_release)
        m_listener.start()
        k_listener.start()

        # wait duration or until stop_event is set
        if duration_s is None:
            while not main.stop_event.is_set():
                time.sleep(0.05)
        else:
            t_end = time.time() + duration_s
            while time.time() < t_end and not main.stop_event.is_set():
                time.sleep(0.05)
    except Exception as e:
        print(f"[LOG] [record_actions] 에러: {e}")
    finally:
        try:
            if m_listener:
                m_listener.stop()
        except Exception:
            pass
        try:
            if k_listener:
                k_listener.stop()
        except Exception:
            pass
        main.recording = False

    return list(main.record_events)
