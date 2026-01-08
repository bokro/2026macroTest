# 자동 키 입력 GUI (테스트/QA용)
# - GUI로 실행 시간을, 입력할 키, 키 입력 간격(ms)를 입력받아 동작합니다.
# - 모든 입력칸이 채워져 있어야 '시작' 버튼이 활성화됩니다.
# - ESC(글로벌)를 누르거나 '중지' 버튼을 누르면 즉시 중지됩니다.

import time
import threading
import sys
import ctypes
import tkinter as tk
from tkinter import messagebox

try:
    from pynput.keyboard import Controller, Key, Listener
except ImportError:
    print("필수 패키지 'pynput'이 설치되어 있지 않습니다.")
    print("설치: pip install pynput")
    sys.exit(1)

# 전역 컨트롤러와 이벤트
controller = Controller()
stop_event = threading.Event()
listener = None
worker_thread = None
# callback set by App to notify UI when worker finishes
on_worker_finished = None

# 글로벌 키 헬퍼: 키 이름으로 정규화 및 핫키 처리
def key_to_name(key):
    try:
        # KeyCode (문자)인 경우
        if hasattr(key, 'char') and key.char is not None:
            return key.char.lower()
    except Exception:
        pass
    try:
        # Key enum (예: Key.f5, Key.enter)
        return key.name
    except Exception:
        return str(key).lower().strip("'\"")

def parse_hotkey_str(s: str):
    k = (s or '').strip().lower()
    if not k:
        return None
    if k in SPECIAL_KEYS:
        return k
    if k.startswith('f') and k[1:].isdigit():
        return k
    if len(k) == 1:
        return k
    return k

# 기본 핫키: F5
HOTKEY = 'f5'

# 글로벌 키 핸들러: ESC(중지), 사용자 정의 핫키(시작 트리거)
def on_press_global(key):
    try:
        name = key_to_name(key)
        if name == 'esc':
            print("ESC 감지: 즉시 종료합니다.")
            stop_event.set()
            return
        hot = globals().get('HOTKEY', 'f5')
        if hot and name == hot:
            print(f"{hot.upper()} 감지: 시작 시도 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    # main thread에서 안전하게 start 호출
                    app.root.after(0, app.hotkey_start)
                except Exception:
                    pass
    except Exception:
        pass

# 키 파싱: 단일 문자 또는 특수키 이름
SPECIAL_KEYS = {
    'enter': Key.enter,
    'esc': Key.esc,
    'space': Key.space,
    'tab': Key.tab,
    'backspace': Key.backspace,
    'shift': Key.shift,
    'ctrl': Key.ctrl,
    'alt': Key.alt,
}

def parse_key(key_str: str):
    k = key_str.strip().lower()
    if not k:
        return None
    if k in SPECIAL_KEYS:
        return SPECIAL_KEYS[k]
    # 첫 글자만 사용할 경우 문자로 입력
    if len(k) == 1:
        return k
    # fallback: try first character
    return k[0]

# worker: duration(s), interval_ms, key
def worker(duration_s: float, interval_ms: int, key_val):
    start = time.time()
    interval_s = interval_ms / 1000.0
    while not stop_event.is_set():
        elapsed = time.time() - start
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
        # 다음 입력까지 대기
        if stop_event.wait(interval_s):
            break
    # 작업 종료 후 메시지
    show_exit_message()
    # 정리: worker_thread를 해제하고 UI 갱신 콜백 호출
    global worker_thread, on_worker_finished
    worker_thread = None
    if callable(on_worker_finished):
        try:
            on_worker_finished()
        except Exception:
            pass

# 종료 메시지 (Windows 전용)
def show_exit_message():
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, "사용 종료", "알림", 0)
        except Exception:
            messagebox.showinfo("알림", "사용 종료")
    else:
        messagebox.showinfo("알림", "사용 종료")

# GUI 애플리케이션
class App:
    def __init__(self, root):
        self.root = root
        root.title('Auto Key Presser')
        root.resizable(False, False)

        pad = 8
        frm = tk.Frame(root, padx=pad, pady=pad)
        frm.pack()

        # 실행 시간
        tk.Label(frm, text='실행 시간 (초)').grid(row=0, column=0, sticky='w')
        self.entry_duration = tk.Entry(frm, width=20)
        self.entry_duration.grid(row=0, column=1)

        # 키 입력 (예: s 또는 enter, space)
        tk.Label(frm, text='입력할 키').grid(row=1, column=0, sticky='w')
        self.entry_key = tk.Entry(frm, width=20)
        self.entry_key.grid(row=1, column=1)

        # 간격(ms)
        tk.Label(frm, text='간격 (ms)').grid(row=2, column=0, sticky='w')
        self.entry_interval = tk.Entry(frm, width=20)
        self.entry_interval.grid(row=2, column=1)

        # 시작 키(핫키)
        tk.Label(frm, text='시작 키 (핫키)').grid(row=3, column=0, sticky='w')
        self.entry_hotkey = tk.Entry(frm, width=20)
        self.entry_hotkey.grid(row=3, column=1)
        self.entry_hotkey.insert(0, 'F5')
        self.entry_hotkey.bind('<KeyRelease>', lambda e: self._on_hotkey_change())

        # 버튼
        self.btn_start = tk.Button(frm, text='시작', width=10, command=self.start)
        self.btn_start.grid(row=4, column=0, pady=(10,0))
        # '중지' 버튼은 눌렀을 때 프로그램 종료(앱 종료) 동작으로 변경
        self.btn_stop = tk.Button(frm, text='중지', width=10, command=self.exit_app, state='disabled')
        self.btn_stop.grid(row=4, column=1, pady=(10,0))

        # 상태 라벨
        self.status = tk.Label(frm, text='대기 중', anchor='w')
        self.status.grid(row=5, column=0, columnspan=2, sticky='we', pady=(8,0))

        # 입력 변경 시 검증
        self.entry_duration.bind('<KeyRelease>', lambda e: self.validate_inputs())
        self.entry_key.bind('<KeyRelease>', lambda e: self.validate_inputs())
        self.entry_interval.bind('<KeyRelease>', lambda e: self.validate_inputs())

        self.validate_inputs()
        # worker 종료 시 UI 갱신을 위한 콜백 등록
        global on_worker_finished
        on_worker_finished = self._on_worker_finished
        # 초기 핫키 설정
        self._on_hotkey_change()

    def _on_hotkey_change(self):
        raw = self.entry_hotkey.get().strip()
        parsed = parse_hotkey_str(raw)
        if parsed:
            globals()['HOTKEY'] = parsed
            # 상태 메시지에 핫키 반영
            self.status.config(text=f'시작: {raw.upper()}')
        else:
            globals()['HOTKEY'] = ''
            self.status.config(text='핫키 무효')

    def _on_worker_finished(self):
        # worker 스레드에서 호출될 수 있으므로 메인 스레드에서 UI 업데이트 실행
        self.root.after(0, self._finish_ui_update)

    def _finish_ui_update(self):
        self.status.config(text='대기 중')
        self.btn_stop.config(state='disabled')
        # 입력값이 유효하면 시작 버튼 활성화
        self.validate_inputs()


    def validate_inputs(self):
        d = self.entry_duration.get().strip()
        k = self.entry_key.get().strip()
        itv = self.entry_interval.get().strip()
        ok = True
        try:
            if not d or float(d) <= 0:
                ok = False
        except Exception:
            ok = False
        if not k:
            ok = False
        try:
            if not itv or int(itv) <= 0:
                ok = False
        except Exception:
            ok = False
        # 시작 버튼 활성화
        self.btn_start.config(state='normal' if ok and worker_thread is None else 'disabled')

    def start(self):
        global stop_event, listener, worker_thread
        # 입력값 읽기
        try:
            duration_s = float(self.entry_duration.get().strip())
            interval_ms = int(self.entry_interval.get().strip())
            key_val = parse_key(self.entry_key.get().strip())
            if key_val is None:
                messagebox.showerror('오류', '유효한 키를 입력하세요.')
                return
        except Exception:
            messagebox.showerror('오류', '입력값을 확인하세요.')
            return

        # 상태 업데이트
        stop_event.clear()
        worker_thread = threading.Thread(target=worker, args=(duration_s, interval_ms, key_val), daemon=True)
        worker_thread.start()

        self.status.config(text='실행 중')
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')

    def hotkey_start(self):
        # 핫키로 호출되는 토글 (main thread에서 호출됨)
        if worker_thread is not None:
            # 실행 중이면 중지
            self.stop()
            return
        # 입력값 검증 및 시작
        d = self.entry_duration.get().strip()
        k = self.entry_key.get().strip()
        itv = self.entry_interval.get().strip()
        try:
            if not d or float(d) <= 0:
                return
            if not k:
                return
            if not itv or int(itv) <= 0:
                return
        except Exception:
            return
        self.start()

    def stop(self):
        global stop_event, worker_thread
        stop_event.set()
        worker_thread = None
        self.status.config(text='중지')
        self.btn_stop.config(state='disabled')
        self.btn_start.config(state='normal' if self.entry_duration.get().strip() and self.entry_key.get().strip() and self.entry_interval.get().strip() else 'disabled')

    def exit_app(self):
        # '중지' 버튼을 눌렀을 때 앱을 종료시키는 동작
        global stop_event, worker_thread, global_hot_listener
        stop_event.set()
        worker_thread = None
        self.status.config(text='종료 중...')
        try:
            if globals().get('global_hot_listener'):
                globals()['global_hot_listener'].stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            pass

def main():
    root = tk.Tk()
    app = App(root)
    globals()['app_instance'] = app
    # persistent global hotkey listener (F5 start, ESC stop)
    global global_hot_listener
    global_hot_listener = Listener(on_press=on_press_global)
    global_hot_listener.start()
    try:
        root.mainloop()
    finally:
        try:
            global_hot_listener.stop()
        except Exception:
            pass

if __name__ == '__main__':
    main()

