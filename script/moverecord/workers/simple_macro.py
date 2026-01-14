"""단순 반복 매크로 worker"""
import time
import sys
import ctypes
from tkinter import messagebox


def worker(duration_s: float, interval_ms: int, key_val, controller, stop_event, playback_stop_event, on_finished_callback=None):
    """단순 반복 키 입력 worker"""
    start = time.time()
    interval_s = interval_ms / 1000.0
    
    # wait() 오버플로우 방지: 시스템 최대값 약 49일 (4,294,967초), 실용적 제한 10일로 설정
    MAX_WAIT_SECONDS = 864_000.0  # 10일 = 864,000초
    safe_interval_s = min(max(interval_s, 0.001), MAX_WAIT_SECONDS)
    
    while not stop_event.is_set():
        elapsed = time.time() - start
        if playback_stop_event.is_set():
            break
        if elapsed >= duration_s:
            print(f"지정된 시간({duration_s}초) 경과: 자동 종료")
            stop_event.set()
            break
        
        try:
            if isinstance(key_val, str) and len(key_val) == 1:
                controller.press(key_val)
                controller.release(key_val)
            else:
                controller.press(key_val)
                controller.release(key_val)
        except Exception as e:
            print("키 입력 중 오류:", e)
        
        # 다음 입력까지 대기 (안전한 interval 사용)
        if stop_event.wait(safe_interval_s):
            break
    
    # 작업 종료 후 메시지
    show_exit_message()
    
    # 콜백 호출
    if callable(on_finished_callback):
        try:
            on_finished_callback()
        except Exception:
            pass


def show_exit_message():
    """종료 메시지 표시 (항상 최상단에 표시)"""
    if sys.platform == "win32":
        try:
            # MB_TOPMOST (0x00040000) + MB_SYSTEMMODAL (0x00001000) 플래그로 강제로 최상단 표시
            MB_TOPMOST = 0x00040000
            MB_SYSTEMMODAL = 0x00001000
            ctypes.windll.user32.MessageBoxW(None, "사용 종료", "알림", MB_TOPMOST | MB_SYSTEMMODAL)
        except Exception:
            # fallback: tkinter messagebox (topmost + focus)
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            root.lift()
            root.focus_force()
            messagebox.showinfo("알림", "사용 종료", parent=root)
            root.destroy()
    else:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()
        messagebox.showinfo("알림", "사용 종료", parent=root)
        root.destroy()
