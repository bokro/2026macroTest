# 자동 키 입력 GUI (테스트/QA용)
# - GUI로 실행 시간을, 입력할 키, 키 입력 간격(ms)를 입력받아 동작합니다.
# - 모든 입력칸이 채워져 있어야 '시작' 버튼이 활성화됩니다.
# - ESC(글로벌)를 누르거나 '중지' 버튼을 누르면 즉시 중지됩니다..

import time
import threading
import sys
import tkinter as tk
from tkinter import messagebox, filedialog, ttk, simpledialog
import json
import os
import getpass
import webbrowser
import csv
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트 기준 경로
BASE_DIR = Path(__file__).resolve().parent.parent
# imgCheck를 위한 경로 (script/imgcheck)
IMGCHECK_DIR = BASE_DIR / 'imgcheck'
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ============ 모듈 임포트 ============
# 설정 임포트
from config.constants import (
    RECORDER_VERSION, HOTKEY, PLAY_HOTKEY, RECORD_START_HOTKEY,
    RECORD_STOP_HOTKEY, SUPPRESS_HOTKEY, DID_DISABLE_UNDO_REDO_ONCE, SPECIAL_KEYS
)

# 유틸 임포트
from utils.key_utils import key_to_name, parse_hotkey_str, parse_key
from utils.file_utils import path_to_href
from utils.html_utils import generate_html

# 녹화 임포트
from recording.save_events import save_events_to_file, migrate_txt_to_json as _migrate_txt_to_json
from recording.record_actions import record_actions

# 재생 임포트
from playback.playback_engine import playback_from_file
import playback.playback_engine as playback_engine

# Worker 임포트
from workers.simple_macro import worker

# UI 임포트
from ui.ui_setup import setup_ui
from ui.json_editor_mixin import JsonEditorMixin
from ui.recording_playback_mixin import RecordingPlaybackMixin

try:
    from pynput.keyboard import Controller, Key, Listener
    from pynput.mouse import Listener as MouseListener, Controller as MouseController, Button as MouseButton
except ImportError:
    print("필수 패키지 'pynput'이 설치되어 있지 않습니다.")
    print("설치: pip install pynput")
    sys.exit(1)

# imgCheck 기능 import
imgcheck_available = False
try:
    import cv2
    import numpy as np
    print(f"[INFO] opencv-python {cv2.__version__}, numpy {np.__version__} 로드 완료")
    
    try:
        # 상대 경로로 imgCheck import
        sys.path.insert(0, str(IMGCHECK_DIR))
        from imgCheck import capture_window, match_templates, find_windows_for_name 
        imgcheck_available = True
        print("[INFO] imgCheck 모듈 로드 완료")
    except Exception as e:
        print(f"[ERROR] imgCheck 모듈 로드 실패: {type(e).__name__}: {e}")
        print(f"[DEBUG] IMGCHECK_DIR: {IMGCHECK_DIR}")
        print(f"[DEBUG] sys.path: {sys.path[:3]}")
        print("[WARNING] imgCheck 기능을 사용할 수 없습니다.")
        
except ImportError as e:
    print(f"[ERROR] opencv-python 또는 numpy 로드 실패: {e}")
    print("[WARNING] 설치 필요: pip install opencv-python numpy")
    print("[WARNING] imgCheck 기능을 사용할 수 없습니다.")
except Exception as e:
    print(f"[ERROR] 예상치 못한 오류: {type(e).__name__}: {e}")
    print("[WARNING] imgCheck 기능을 사용할 수 없습니다.")

# 추가 컨트롤러
mouse_controller = MouseController()

# 녹화/재생 관련 글로벌
recording = False
record_events = []  # list of (t_ms, type, params...)
playback_stop_event = threading.Event()
playback_thread = None
# 전역 컨트롤러와 이벤트
controller = Controller()
stop_event = threading.Event()
listener = None
worker_thread = None
# callback set by App to notify UI when worker finishes
on_worker_finished = None

# ============ 글로벌 키 핸들러 ============
def on_press_global(key):
    """글로벌 키 핸들러"""
    try:
        name = key_to_name(key)
        # ignore global handling when synthetic events are being injected
        if globals().get('SUPPRESS_HOTKEY', False):
            return
        # playback 중에는 핫키 무시
        if hasattr(playback_engine, '_suppress_hotkey') and playback_engine._suppress_hotkey:
            return
        # record stop hotkey (default ESC)
        rstop = globals().get('RECORD_STOP_HOTKEY', 'esc')
        if rstop and name == rstop:
            print("[LOG] 녹화 중지/ESC 감지: 즉시 중지합니다.")
            stop_event.set()
            playback_stop_event.set()
            return
        hot = globals().get('HOTKEY', 'f5')
        if hot and name == hot:
            print(f"[LOG] {hot.upper()} 감지: 시작 시도 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    # main thread에서 안전하게 start 호출
                    app.root.after(0, app.hotkey_start)
                except Exception:
                    pass
        play_hot = globals().get('PLAY_HOTKEY', 'f6')
        if play_hot and name == play_hot:
            print(f"[LOG] {play_hot.upper()} 감지: 재생 토글 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    app.root.after(0, app.play_hotkey_toggle)
                except Exception:
                    pass
        rstart = globals().get('RECORD_START_HOTKEY', 'f7')
        if rstart and name == rstart:
            print(f"[LOG] {rstart.upper()} 감지: 녹화 시작 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    app.root.after(0, app.start_recording)
                except Exception:
                    pass
    except Exception:
        pass

# ============ Worker & Helper Functions ============
# 단순 반복 매크로는 workers.simple_macro에서 import됨

# GUI 애플리케이션
class App(RecordingPlaybackMixin, JsonEditorMixin):
    def __init__(self, root):
        """
        App 클래스 초기화
        
        모든 UI 설정은 ui.ui_setup 모듈의 setup_ui() 함수에서 처리됩니다.
        """
        global on_worker_finished
        self.root = root
        
        # UI 설정 (모든 UI 초기화 로직을 ui_setup 모듈로 분리)
        setup_ui(self)
        
        # worker 완료 콜백 설정
        on_worker_finished = self._on_worker_finished

    # --------------------- end JSON Editor (moved to ui/json_editor_mixin.py) ---------------------

    def validate_inputs(self):
        d = self.entry_duration.get().strip()
        k = self.entry_key.get().strip()
        itv = self.entry_interval.get().strip()
        script = getattr(self, 'entry_script', None)
        script_path = script.get().strip() if script else ''
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
        # 시작 버튼 활성화: 입력 필드가 유효하거나 스크립트 파일이 선택된 경우
        can_start = (ok and worker_thread is None) or (script_path and worker_thread is None)
        self.btn_start.config(state='normal' if can_start else 'disabled')
        # 배속 유효성 (스크립트 재생용) - 드롭다운에서 선택된 값 사용
        speed_ok = True
        speed_val = 1.0
        if hasattr(self, 'speed_var'):
            try:
                speed_val = float(self.speed_var.get())
                speed_ok = 0.5 <= speed_val <= 3.0
            except Exception:
                speed_ok = False
        # 반복 횟수 유효성
        repeat_ok = True
        repeat_val = 1
        if hasattr(self, 'entry_repeat'):
            try:
                repeat_val = int(self.entry_repeat.get().strip())
                repeat_ok = repeat_val >= 1
            except Exception:
                repeat_ok = False
        # 샘플링 유효성
        sample_ok = True
        sample_val = 0
        if hasattr(self, 'entry_sample_ms'):
            try:
                sample_val = int(self.entry_sample_ms.get().strip())
                sample_ok = sample_val >= 0
            except Exception:
                sample_ok = False
        # 별도 스크립트 시작 버튼: 스크립트가 선택되어 있고 재생/작업이 없을 때만 활성화, 배속 및 반복/샘플 유효 필요
        script_ok = bool(script_path) and (worker_thread is None) and (globals().get('playback_thread') is None) and speed_ok and repeat_ok and sample_ok
        if hasattr(self, 'btn_start_script'):
            self.btn_start_script.config(state='normal' if script_ok else 'disabled')
        # 이어서 녹화 버튼: 스크립트가 선택되어 있고 녹화 중이 아닐 때 활성화
        append_record_ok = bool(script_path) and not globals().get('recording', False)
        if hasattr(self, 'btn_append_record'):
            self.btn_append_record.config(state='normal' if append_record_ok else 'disabled')

    def hotkey_start(self):
        # 핫키로 호출되는 토글 (main thread에서 호출됨)
        # F5: 자동 키 입력 시작/중지, F6: 스크립트 재생 토글 (별도 메소드)
        global playback_thread, worker_thread, stop_event, playback_stop_event
        
        if worker_thread is not None:
            # 실행 중이면 중지
            self.stop()
            return
        if playback_thread is not None:
            # 재생 중이면 중지
            playback_stop_event.set()
            globals()['playback_thread'] = None
            self.status.config(text='재생 중지')
            self.btn_start.config(state='normal')
            self.btn_stop.config(state='disabled')
            return
        
        # 입력값 검증 및 자동 키 입력 시작
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
        
        # 자동 키 입력 시작 (스크립트 파일은 무시하고 순수 자동 입력)
        self.start_auto_presser()

    def start_auto_presser(self):
        """순수 자동 키 입력 시작 (스크립트 재생 제외)"""
        global stop_event, worker_thread, controller, playback_stop_event, on_worker_finished
        
        # 이미 실행 중인 worker가 있으면 중지
        if worker_thread is not None:
            messagebox.showwarning('경고', '매크로가 이미 실행 중입니다.')
            return
        
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

        # 상태 업데이트 (모든 이벤트 플래그 초기화)
        stop_event.clear()
        playback_stop_event.clear()
        
        # worker 스레드 생성 및 전역 변수 업데이트
        worker_thread = threading.Thread(
            target=worker, 
            args=(duration_s, interval_ms, key_val, controller, stop_event, playback_stop_event, on_worker_finished), 
            daemon=True
        )
        
        # 전역 변수에 스레드 할당 (중요: globals() 사용)
        globals()['worker_thread'] = worker_thread
        worker_thread.start()

        self.status.config(text='실행 중')
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')

    def start(self):
        """시작 버튼 클릭 시: 스크립트 파일이 있으면 재생, 없으면 자동 키 입력"""
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if script_path:
            # 스크립트 파일이 선택되어 있으면 재생 시작
            self.start_playback()
        else:
            # 스크립트가 없으면 자동 키 입력 시작
            self.start_auto_presser()

    def stop(self):
        global stop_event, worker_thread
        stop_event.set()
        globals()['worker_thread'] = None
        self.status.config(text='중지')
        self.btn_stop.config(state='disabled')
        self.btn_start.config(state='normal' if self.entry_duration.get().strip() and self.entry_key.get().strip() and self.entry_interval.get().strip() else 'disabled')

    def cleanup_resources(self):
        """Comprehensive cleanup of all resources to prevent memory leaks."""
        print('리소스 정리 시작...')
        
        # 1. Stop all global events and threads
        global stop_event, playback_stop_event, worker_thread, playback_thread, global_hot_listener, recording, record_events
        try:
            stop_event.set()
            playback_stop_event.set()
        except Exception:
            pass
        
        # 2. Stop global hotkey listener
        try:
            if globals().get('global_hot_listener'):
                globals()['global_hot_listener'].stop()
                globals()['global_hot_listener'] = None
        except Exception:
            pass
        
        # 3. Clear recording data
        try:
            recording = False
            record_events.clear()
        except Exception:
            pass
        
        # 4. Wait for threads to finish (with timeout)
        try:
            if worker_thread and worker_thread.is_alive():
                worker_thread.join(timeout=0.5)
            worker_thread = None
        except Exception:
            pass
        
        try:
            if playback_thread and playback_thread.is_alive():
                playback_thread.join(timeout=0.5)
            playback_thread = None
        except Exception:
            pass
        
        # 5. Clear editor resources
        try:
            for row in self.editor_rows:
                self._unbind_row_events(row)
                try:
                    row['t'].destroy()
                    row['type'].destroy()
                    row['params'].destroy()
                except Exception:
                    pass
            self.editor_rows.clear()
        except Exception:
            pass
        
        # 6. Clear undo/redo stacks
        try:
            self._undo_stack.clear()
            self._redo_stack.clear()
        except Exception:
            pass
        
        # 7. Unbind all root-level event handlers
        try:
            self.root.unbind('<Control-z>')
            self.root.unbind('<Control-y>')
        except Exception:
            pass
        
        print('리소스 정리 완료')

    def exit_app(self):
        # 프로그램 종료 시 모든 리소스 정리
        self.status.config(text='종료 중...')
        self.cleanup_resources()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            pass

# playback_from_file는 playback.playback_engine에서 import됨


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

