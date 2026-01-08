# 자동 키 입력 GUI (테스트/QA용)
# - GUI로 실행 시간을, 입력할 키, 키 입력 간격(ms)를 입력받아 동작합니다.
# - 모든 입력칸이 채워져 있어야 '시작' 버튼이 활성화됩니다.
# - ESC(글로벌)를 누르거나 '중지' 버튼을 누르면 즉시 중지됩니다.

import time
import threading
import sys
import ctypes
import tkinter as tk
from tkinter import messagebox, filedialog, ttk, simpledialog
import json
import os
import platform
import socket
import getpass
import webbrowser
import csv
from datetime import datetime

# recorder version for metadata
RECORDER_VERSION = '1.0'

# playback hotkey (separate from main HOTKEY)
PLAY_HOTKEY = 'f6'
# record hotkeys
RECORD_START_HOTKEY = 'f7'
RECORD_STOP_HOTKEY = 'esc'
# suppress handling of global hotkeys while synthetic (script) inputs are sent
SUPPRESS_HOTKEY = False
DID_DISABLE_UNDO_REDO_ONCE = False  # 이번 테스트용 임시 비활성화 플래그


try:
    from pynput.keyboard import Controller, Key, Listener
    from pynput.mouse import Listener as MouseListener, Controller as MouseController, Button as MouseButton
except ImportError:
    print("필수 패키지 'pynput'이 설치되어 있지 않습니다.")
    print("설치: pip install pynput")
    sys.exit(1)

# imgCheck 기능 import
try:
    import cv2
    import numpy as np
    from imgCheck import capture_window, match_templates, find_windows_for_name
except ImportError:
    print("경고: imgCheck 기능을 사용하려면 opencv-python, numpy가 필요합니다.")
    print("설치: pip install opencv-python numpy")
    # 계속 실행은 가능하도록 (imgcheck 타입만 사용 불가)

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
        # ignore global handling when synthetic events are being injected
        if globals().get('SUPPRESS_HOTKEY', False):
            return
        # record stop hotkey (default ESC)
        rstop = globals().get('RECORD_STOP_HOTKEY', 'esc')
        if rstop and name == rstop:
            print("녹화 중지/ESC 감지: 즉시 중지합니다.")
            stop_event.set()
            playback_stop_event.set()
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
        play_hot = globals().get('PLAY_HOTKEY', 'f6')
        if play_hot and name == play_hot:
            print(f"{play_hot.upper()} 감지: 재생 토글 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    app.root.after(0, app.play_hotkey_toggle)
                except Exception:
                    pass
        rstart = globals().get('RECORD_START_HOTKEY', 'f7')
        if rstart and name == rstart:
            print(f"{rstart.upper()} 감지: 녹화 시작 (글로벌)")
            app = globals().get('app_instance')
            if app:
                try:
                    app.root.after(0, app.start_recording)
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


def _collect_pc_meta():
    """Collect basic PC metadata for logging."""
    info = {
        'host': socket.gethostname(),
        'user': getpass.getuser(),
        'os': platform.platform(),
        'python': sys.version.split()[0],
    }
    try:
        app = globals().get('app_instance')
        if app and getattr(app, 'root', None):
            info['screen_width'] = app.root.winfo_screenwidth()
            info['screen_height'] = app.root.winfo_screenheight()
        else:
            tmp = tk.Tk()
            tmp.withdraw()
            info['screen_width'] = tmp.winfo_screenwidth()
            info['screen_height'] = tmp.winfo_screenheight()
            tmp.destroy()
    except Exception:
        pass
    return info


def _escape_html(text):
    try:
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    except Exception:
        return str(text)


def _path_to_href(path):
    if not path:
        return ''
    try:
        norm = os.path.abspath(path).replace('\\', '/').replace(' ', '%20')
        return 'file:///' + norm
    except Exception:
        return ''

# 녹화 헬퍼: 이벤트와 메타를 JSON 객체로 저장
def _save_events_to_file(events, default_name='recording.json', meta_extra=None):
    # Ask for filename (JSON)
    try:
        fpath = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON Files','*.json')], initialfile=default_name)
    except Exception:
        fpath = None
    if not fpath:
        return None
    try:
        # build events list
        json_events = []
        for ev in events:
            t_ms = int(ev[0])
            etype = ev[1]
            params = list(ev[2:])
            json_events.append({'t_ms': t_ms, 'type': etype, 'params': params})
        # gather screen size from app if available else create temp root
        screen_w = None
        screen_h = None
        app = globals().get('app_instance')
        try:
            if app and getattr(app, 'root', None):
                screen_w = app.root.winfo_screenwidth()
                screen_h = app.root.winfo_screenheight()
            else:
                root_tmp = tk.Tk()
                root_tmp.withdraw()
                screen_w = root_tmp.winfo_screenwidth()
                screen_h = root_tmp.winfo_screenheight()
                root_tmp.destroy()
        except Exception:
            screen_w = None
            screen_h = None
        meta = {
            'recorder_version': RECORDER_VERSION,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'screen_width': screen_w,
            'screen_height': screen_h
        }
        if meta_extra:
            try:
                meta.update(meta_extra)
            except Exception:
                pass
        payload = {'meta': meta, 'events': json_events}
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return fpath
    except Exception as e:
        print('파일 저장 실패:', e)
        return None

# 녹화 함수
def _migrate_txt_to_json(txt_path):
    try:
        events = []
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                try:
                    t_ms = int(parts[0])
                except Exception:
                    continue
                etype = parts[1]
                params = []
                for p in parts[2:]:
                    # try numeric conversion
                    try:
                        if '.' in p:
                            params.append(float(p))
                        else:
                            params.append(int(p))
                    except Exception:
                        params.append(p)
                events.append({'t_ms': t_ms, 'type': etype, 'params': params})
        # write json sidecar
        base = os.path.splitext(txt_path)[0]
        out = base + '.json'
        meta = {'recorder_version': RECORDER_VERSION, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        payload = {'meta': meta, 'events': events}
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out
    except Exception as e:
        print('마이그레이션 실패:', e)
        return None


def record_actions(duration_s: float = None, sample_ms: int = 0, meta_extra=None, time_offset_ms: int = 0):
    global recording, record_events
    if recording:
        return None
    recording = True
    record_events = []
    start = time.time()
    last_move_ms = -9999

    def _now_ms():
        return int((time.time() - start) * 1000) + time_offset_ms

    def on_move(x, y):
        nonlocal last_move_ms
        now = _now_ms()
        if sample_ms and (now - last_move_ms) < int(sample_ms):
            return
        last_move_ms = now
        record_events.append((now, 'mouse_move', x, y))

    def on_click(x, y, button, pressed):
        record_events.append((_now_ms(), 'mouse_click', str(button), 'press' if pressed else 'release', x, y))

    def on_scroll(x, y, dx, dy):
        record_events.append((_now_ms(), 'mouse_scroll', dx, dy, x, y))

    def on_press(k):
        try:
            ch = k.char
        except Exception:
            ch = str(k)
        record_events.append((_now_ms(), 'key_down', ch))

    def on_release(k):
        try:
            ch = k.char
        except Exception:
            ch = str(k)
        record_events.append((_now_ms(), 'key_up', ch))

    # start listeners
    m_listener = MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    k_listener = Listener(on_press=on_press, on_release=on_release)
    m_listener.start()
    k_listener.start()

    # wait duration or until stop_event is set
    if duration_s is None:
        # record until ESC (global stop_event)
        while not globals().get('stop_event', threading.Event()).is_set():
            time.sleep(0.05)
    else:
        t_end = time.time() + duration_s
        while time.time() < t_end and not globals().get('stop_event', threading.Event()).is_set():
            time.sleep(0.05)

    # stop listeners
    try:
        m_listener.stop()
    except Exception:
        pass
    try:
        k_listener.stop()
    except Exception:
        pass

    recording = False
    # Save file dialog (JSON)
    saved = _save_events_to_file(record_events, default_name='recording.json', meta_extra=meta_extra)
    return saved

# worker: duration(s), interval_ms, key
def worker(duration_s: float, interval_ms: int, key_val):
    start = time.time()
    interval_s = interval_ms / 1000.0
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


def _write_test_log(log_data):
    """Write playback/test results to HTML and CSV, and open the HTML."""
    log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = f'test_log_{ts}'
    html_path = os.path.join(log_dir, base + '.html')
    csv_path = os.path.join(log_dir, base + '.csv')

    started_at = log_data.get('started_at')
    ended_at = log_data.get('ended_at')
    duration_s = log_data.get('duration_s', '')
    status = log_data.get('status', 'unknown')
    overall = log_data.get('overall_result', 'unknown')
    script_path = log_data.get('script_path', '')
    pc_meta = log_data.get('pc_meta', {}) or {}
    img_results = log_data.get('imgcheck_results', []) or []
    error_message = log_data.get('error_message', '')

    # CSV output for Excel-friendly view
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['idx', 'template', 'passed', 'score', 'saved_image', 'message', 'played_at_ms'])
            for idx, ev in enumerate(img_results, 1):
                writer.writerow([
                    idx,
                    ev.get('input_image', ''),
                    ev.get('passed', False),
                    ev.get('score', ''),
                    ev.get('saved_path', ''),
                    ev.get('message', ''),
                    ev.get('elapsed_ms', ''),
                ])
    except Exception:
        pass

    def _fmt_dt(dt_obj):
        if not dt_obj:
            return ''
        try:
            return dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(dt_obj)

    def _meta_row(label, value):
        return f'<tr><th>{_escape_html(label)}</th><td>{_escape_html(value)}</td></tr>'

    summary_rows = [
        _meta_row('스크립트 파일', os.path.basename(script_path) if script_path else ''),
        _meta_row('상태', status),
        _meta_row('전체 결과', overall),
        _meta_row('시작', _fmt_dt(started_at)),
        _meta_row('종료', _fmt_dt(ended_at)),
        _meta_row('소요(초)', f"{duration_s:.2f}" if isinstance(duration_s, (int, float)) else duration_s),
        _meta_row('로그 디렉터리', log_dir),
    ]
    target_meta = log_data.get('target_meta', {}) or {}
    if target_meta:
        summary_rows.extend([
            _meta_row('대상 PID', target_meta.get('active_window_pid', '')),
            _meta_row('대상 프로세스', target_meta.get('active_process_name', '')),
            _meta_row('대상 창 제목', target_meta.get('active_window_title', '')),
        ])
    if error_message:
        summary_rows.append(_meta_row('에러', error_message))

    pc_rows = []
    for k in ('host', 'user', 'os', 'python', 'screen_width', 'screen_height'):
        if k in pc_meta:
            pc_rows.append(_meta_row(k, pc_meta.get(k, '')))

    img_rows = []
    for idx, ev in enumerate(img_results, 1):
        href = _path_to_href(ev.get('saved_path', ''))
        link_html = f"<a href='{href}'>열기</a>" if href else ''
        img_rows.append(
            '<tr>'
            f'<td>{idx}</td>'
            f'<td>{_escape_html(ev.get("input_image", ""))}</td>'
            f'<td>{"PASS" if ev.get("passed") else "FAIL"}</td>'
            f'<td>{_escape_html(ev.get("score", ""))}</td>'
            f'<td>{_escape_html(ev.get("message", ""))}</td>'
            f'<td>{_escape_html(ev.get("elapsed_ms", ""))}</td>'
            f'<td>{link_html}</td>'
            '</tr>'
        )

    html_body = f"""
<!DOCTYPE html>
<html lang='ko'>
<head>
  <meta charset='utf-8'>
  <title>테스트 로그</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ margin-bottom: 0; }}
    .meta-table th {{ text-align: left; width: 140px; padding: 4px; background: #f0f0f0; }}
    .meta-table td {{ padding: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    table, th, td {{ border: 1px solid #ccc; }}
    th, td {{ padding: 6px; text-align: left; }}
    .pass {{ color: green; font-weight: bold; }}
    .fail {{ color: red; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>테스트 로그</h1>
  <table class='meta-table'>
    {''.join(summary_rows)}
  </table>

  <h2>PC 메타정보</h2>
  <table class='meta-table'>
    {''.join(pc_rows) if pc_rows else '<tr><td>정보 없음</td></tr>'}
  </table>

  <h2>imgcheck 결과</h2>
  <table>
    <tr><th>#</th><th>템플릿</th><th>결과</th><th>점수</th><th>메시지</th><th>재생 시점(ms)</th><th>이미지</th></tr>
    {''.join(img_rows) if img_rows else '<tr><td colspan="7">imgcheck 이벤트 없음</td></tr>'}
  </table>

  <p>CSV: {os.path.basename(csv_path)}</p>
</body>
</html>
"""

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_body)
    except Exception:
        pass

    try:
        webbrowser.open(_path_to_href(html_path))
    except Exception:
        pass

    return html_path, csv_path

# GUI 애플리케이션
class App:
    def __init__(self, root):
        self.root = root
        # 프로그램 이름 (원하는 이름으로 변경하세요)
        root.title('Please Use Only QA')
        
        # 아이콘 설정 (ico 또는 png 파일 경로 지정)
        # 예시: root.iconbitmap('icon.ico')  # Windows .ico 파일
        # 또는: root.iconphoto(True, tk.PhotoImage(file='icon.png'))  # PNG 파일
        # root.iconphoto(True, tk.PhotoImage(file='testicon.png'))
        
        root.resizable(True, True)

        pad = 8
        # Notebook with two tabs
        notebook = ttk.Notebook(root)
        tab1 = tk.Frame(notebook)
        tab2 = tk.Frame(notebook)
        notebook.add(tab1, text='단순 반복 매크로')
        notebook.add(tab2, text='녹화 / 스크립트')
        notebook.pack(fill='both', expand=True)

        frm1 = tk.Frame(tab1, padx=pad, pady=pad)
        frm1.pack()
        frm2 = tk.Frame(tab2, padx=pad, pady=pad)
        frm2.pack()
        # --- Tab 3: JSON editor ---
        tab3 = tk.Frame(notebook)
        notebook.add(tab3, text='JSON 편집기')
        frm3 = tk.Frame(tab3, padx=pad, pady=pad)
        frm3.pack(fill='both', expand=True)
        # allow grid children to stretch when window is resized
        for c in range(4):
            frm3.columnconfigure(c, weight=1)
        frm3.rowconfigure(6, weight=1)  # canvas row

        # Editor control buttons
        self.btn_editor_load = tk.Button(frm3, text='불러오기', width=10, command=self.load_script_to_editor)
        self.btn_editor_load.grid(row=0, column=0, pady=(6,0), sticky='w')
        self.btn_editor_save = tk.Button(frm3, text='저장', width=10, command=self.save_edited_script, state='disabled')
        self.btn_editor_save.grid(row=0, column=1, pady=(6,0), sticky='w')
        self.btn_editor_clear = tk.Button(frm3, text='초기화', width=10, command=self._clear_editor)
        self.btn_editor_clear.grid(row=0, column=2, pady=(6,0), sticky='w')
        self.btn_editor_help = tk.Button(frm3, text='?', width=3, command=self._show_mouse_help)
        self.btn_editor_help.grid(row=0, column=3, pady=(6,0), sticky='e')

        # Meta fields
        tk.Label(frm3, text='메타 (수정 가능)').grid(row=1, column=0, sticky='w', pady=(8,0))
        tk.Label(frm3, text='recorder_version').grid(row=2, column=0, sticky='w')
        self.meta_version = tk.Entry(frm3, width=20)
        self.meta_version.grid(row=2, column=1, sticky='w')
        tk.Label(frm3, text='timestamp').grid(row=2, column=2, sticky='w')
        self.meta_timestamp = tk.Entry(frm3, width=30)
        self.meta_timestamp.grid(row=2, column=3, sticky='w')
        tk.Label(frm3, text='screen_width').grid(row=3, column=0, sticky='w')
        self.meta_width = tk.Entry(frm3, width=10)
        self.meta_width.grid(row=3, column=1, sticky='w')
        tk.Label(frm3, text='screen_height').grid(row=3, column=2, sticky='w')
        self.meta_height = tk.Entry(frm3, width=10)
        self.meta_height.grid(row=3, column=3, sticky='w')
        tk.Label(frm3, text='(Params는 JSON 배열 형식으로 입력하세요, 예: ["a"])', fg='gray').grid(row=4, column=0, columnspan=4, sticky='w')

        # Events editor - header row
        self.editor_header = tk.Frame(frm3)
        self.editor_header.grid(row=5, column=0, columnspan=4, sticky='we', pady=(6,0))
        tk.Label(self.editor_header, text='시간(ms)', width=12, anchor='w').grid(row=0, column=0, sticky='w')
        tk.Label(self.editor_header, text='타입', width=20, anchor='w').grid(row=0, column=1, sticky='w')
        tk.Label(self.editor_header, text='파라미터 (JSON 배열)', width=60, anchor='w').grid(row=0, column=2, sticky='w')

        # Events editor area
        self.editor_canvas_container = tk.Frame(frm3)
        self.editor_canvas_container.grid(row=6, column=0, columnspan=4, sticky='nsew')
        self.editor_canvas = tk.Canvas(self.editor_canvas_container, height=320)
        self.editor_canvas.pack(side='left', fill='both', expand=True)
        self.editor_vsb = tk.Scrollbar(self.editor_canvas_container, orient='vertical', command=self.editor_canvas.yview)
        self.editor_vsb.pack(side='right', fill='y')
        self.editor_hsb = tk.Scrollbar(frm3, orient='horizontal', command=self.editor_canvas.xview)
        self.editor_hsb.grid(row=7, column=0, columnspan=4, sticky='we')
        self.editor_canvas.configure(yscrollcommand=self.editor_vsb.set, xscrollcommand=self.editor_hsb.set)
        self.editor_inner = tk.Frame(self.editor_canvas)
        self.editor_inner_window = self.editor_canvas.create_window((0,0), window=self.editor_inner, anchor='nw')
        self.editor_inner.bind('<Configure>', self._update_editor_scrollregion)
        self.editor_canvas.bind('<Configure>', self._sync_editor_canvas_width)
        # mouse wheel scroll for editor
        self.editor_canvas.bind_all('<MouseWheel>', self._on_mousewheel_editor)

        # editor rows container (rows inside editor_inner)
        self.editor_rows = []  # list of dicts {t_entry,type_entry,params_entry}
        self.selected_row_indices = set()  # track multi-selection
        self.selection_anchor = None
        self._undo_stack = []  # list of {'state': ..., 'label': ...}
        self._redo_stack = []
        self._edit_baseline_state = None
        self._edit_baseline_label = ''
        self._edit_baseline_committed = False
        self._restoring_editor_state = False
        self.root.bind('<Control-z>', self._undo_editor)
        self.root.bind('<Control-y>', self._redo_editor)
        self.btn_add_row = tk.Button(frm3, text='행 추가(끝)', width=12, command=lambda: self._add_editor_row())
        self.btn_add_row.grid(row=8, column=0, pady=(6,0), sticky='w')
        self.btn_insert_row = tk.Button(frm3, text='행 삽입(중간)', width=12, command=self._insert_row_after_selected)
        self.btn_insert_row.grid(row=8, column=1, pady=(6,0), sticky='w')
        self.btn_time_offset = tk.Button(frm3, text='시간 추가', width=10, command=self._add_time_offset)
        self.btn_time_offset.grid(row=8, column=2, pady=(6,0), sticky='w')
        self.btn_delete_row = tk.Button(frm3, text='행 삭제', width=10, command=self._delete_selected_row)
        self.btn_delete_row.grid(row=8, column=3, pady=(6,0), sticky='w')
        # Exit button at bottom-right of Tab 3
        self.btn_exit_tab3 = tk.Button(frm3, text='프로그램 종료', width=14, command=self.exit_app, bg='#ffcccc')
        self.btn_exit_tab3.grid(row=9, column=3, sticky='e', padx=(0, 0), pady=(10,0))
        self._menu_hover_bg = '#d9e8ff'
        self.btn_undo = tk.Button(frm3, text='되돌리기 (Ctrl+Z)', width=16, command=lambda: self._undo_editor())
        self.btn_undo.grid(row=9, column=0, pady=(4,0), sticky='w')
        self.btn_undo_menu = tk.Menubutton(frm3, text='▼', width=3, relief='raised')
        self.btn_undo_menu.grid(row=9, column=1, pady=(4,0), sticky='w')
        self.undo_menu = tk.Menu(self.btn_undo_menu, tearoff=0)
        self.btn_undo_menu.configure(menu=self.undo_menu)
        self.btn_redo = tk.Button(frm3, text='다시하기 (Ctrl+Y)', width=16, command=lambda: self._redo_editor())
        self.btn_redo.grid(row=9, column=2, pady=(4,0), sticky='w')
        self.btn_redo_menu = tk.Menubutton(frm3, text='▼', width=3, relief='raised')
        self.btn_redo_menu.grid(row=9, column=3, pady=(4,0), sticky='w')
        self.redo_menu = tk.Menu(self.btn_redo_menu, tearoff=0)
        self.btn_redo_menu.configure(menu=self.redo_menu)
        # 임시: 요청에 따라 되돌리기/다시하기 UI 비활성화
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            try:
                self.btn_undo.config(state='disabled')
                self.btn_undo_menu.config(state='disabled')
                self.btn_redo.config(state='disabled')
                self.btn_redo_menu.config(state='disabled')
            except Exception:
                pass
        self._menu_default_bg = self.undo_menu.cget('background')
        self._menu_last_hover = {'undo': None, 'redo': None}
        self.undo_menu.bind('<<MenuSelect>>', lambda e: self._on_history_menu_hover(self.undo_menu, self._undo_stack, 'undo'))
        self.redo_menu.bind('<<MenuSelect>>', lambda e: self._on_history_menu_hover(self.redo_menu, self._redo_stack, 'redo'))
        self.undo_menu.bind('<Unmap>', lambda e: self._reset_menu_highlight(self.undo_menu, 'undo'))
        self.redo_menu.bind('<Unmap>', lambda e: self._reset_menu_highlight(self.redo_menu, 'redo'))
        self.undo_menu.bind('<Leave>', lambda e: self._reset_menu_highlight(self.undo_menu, 'undo'))
        self.redo_menu.bind('<Leave>', lambda e: self._reset_menu_highlight(self.redo_menu, 'redo'))
        self.undo_menu.bind('<ButtonRelease-1>', lambda e: self._reset_menu_highlight(self.undo_menu, 'undo'))
        self.redo_menu.bind('<ButtonRelease-1>', lambda e: self._reset_menu_highlight(self.redo_menu, 'redo'))
        self._refresh_history_menus()

        # --- Tab 1: simple auto presser ---
        # 실행 시간
        tk.Label(frm1, text='실행 시간 (초)').grid(row=0, column=0, sticky='w')
        self.entry_duration = tk.Entry(frm1, width=20)
        self.entry_duration.grid(row=0, column=1)

        # 키 입력 (예: s 또는 enter, space)
        tk.Label(frm1, text='입력할 키').grid(row=1, column=0, sticky='w')
        self.entry_key = tk.Entry(frm1, width=20)
        self.entry_key.grid(row=1, column=1)

        # 간격(ms)
        tk.Label(frm1, text='간격 (ms)').grid(row=2, column=0, sticky='w')
        self.entry_interval = tk.Entry(frm1, width=20)
        self.entry_interval.grid(row=2, column=1)

        # 시작 키(핫키)
        tk.Label(frm1, text='시작 키 (핫키)').grid(row=3, column=0, sticky='w')
        self.entry_hotkey = tk.Entry(frm1, width=20)
        self.entry_hotkey.grid(row=3, column=1)
        self.entry_hotkey.insert(0, 'F5')
        self.entry_hotkey.bind('<KeyRelease>', lambda e: self._on_hotkey_change())

        # Buttons: start / stop
        self.btn_start = tk.Button(frm1, text='시작', width=10, command=self.start)
        self.btn_start.grid(row=4, column=0, pady=(10,0))
        self.btn_stop = tk.Button(frm1, text='중지', width=10, command=self.stop, state='disabled')
        self.btn_stop.grid(row=4, column=1, pady=(10,0))
        # Exit button at bottom-right
        self.btn_exit_tab1 = tk.Button(frm1, text='프로그램 종료', width=14, command=self.exit_app, bg='#ffcccc')
        self.btn_exit_tab1.grid(row=4, column=2, columnspan=1, sticky='e', padx=(50, 0), pady=(10,0))

        # --- Tab 2: recording & playback ---
        # 재생 핫키
        tk.Label(frm2, text='재생 핫키').grid(row=0, column=0, sticky='w')
        self.entry_playhotkey = tk.Entry(frm2, width=20)
        self.entry_playhotkey.grid(row=0, column=1)
        self.entry_playhotkey.insert(0, 'F6')
        self.entry_playhotkey.bind('<KeyRelease>', lambda e: self._on_playhotkey_change())
        # 녹화 시작 키
        tk.Label(frm2, text='녹화 시작 키').grid(row=0, column=2, sticky='w')
        self.entry_record_start = tk.Entry(frm2, width=15)
        self.entry_record_start.grid(row=0, column=3)
        self.entry_record_start.insert(0, 'F7')
        self.entry_record_start.bind('<KeyRelease>', lambda e: self._on_record_start_hotkey_change())
        # 녹화 종료 키 (기본 ESC)
        tk.Label(frm2, text='녹화 종료 키').grid(row=1, column=2, sticky='w')
        self.entry_record_stop = tk.Entry(frm2, width=15)
        self.entry_record_stop.grid(row=1, column=3)
        self.entry_record_stop.insert(0, 'ESC')
        self.entry_record_stop.bind('<KeyRelease>', lambda e: self._on_record_stop_hotkey_change())

        # Buttons: record, start script, stop
        self.btn_record = tk.Button(frm2, text='녹화', width=10, command=self.start_recording)
        self.btn_record.grid(row=2, column=0, pady=(10,0))
        self.btn_append_record = tk.Button(frm2, text='이어서 녹화', width=12, command=self.start_append_recording, state='disabled')
        self.btn_append_record.grid(row=2, column=1, pady=(10,0))
        self.btn_start_script = tk.Button(frm2, text='스크립트 시작', width=12, command=self.start_playback, state='disabled')
        self.btn_start_script.grid(row=2, column=2, pady=(10,0))
        self.btn_stop_play = tk.Button(frm2, text='재생 중지', width=10, command=lambda: self.play_hotkey_toggle(), state='disabled')
        self.btn_stop_play.grid(row=2, column=3, pady=(10,0))

        # 스크립트 선택
        tk.Label(frm2, text='스크립트 파일').grid(row=3, column=0, sticky='w')
        self.entry_script = tk.Entry(frm2, width=40)
        self.entry_script.grid(row=3, column=1, columnspan=2, sticky='we')
        self.entry_script.bind('<KeyRelease>', lambda e: self.validate_inputs())
        self.btn_browse = tk.Button(frm2, text='선택', width=8, command=self.choose_script)
        self.btn_browse.grid(row=3, column=3, padx=(6,0))

        # 배속 드롭다운
        tk.Label(frm2, text='배속 (x)').grid(row=4, column=0, sticky='w')
        self.speed_var = tk.StringVar(value='1.0')
        speed_options = ['0.5', '0.8', '1.0', '1.2', '1.5', '2', '3']
        self.opt_speed = tk.OptionMenu(frm2, self.speed_var, *speed_options, command=lambda _: self.validate_inputs())
        self.opt_speed.config(width=6)
        self.opt_speed.grid(row=4, column=1)

        # 반복 횟수
        tk.Label(frm2, text='반복 횟수').grid(row=4, column=2, sticky='w')
        self.entry_repeat = tk.Entry(frm2, width=8)
        self.entry_repeat.grid(row=4, column=3)
        self.entry_repeat.insert(0, '1')

        # 샘플링 옵션
        tk.Label(frm2, text='마우스 샘플링(ms, 0=비활성)').grid(row=5, column=0, sticky='w')
        self.entry_sample_ms = tk.Entry(frm2, width=10)
        self.entry_sample_ms.grid(row=5, column=1)
        self.entry_sample_ms.insert(0, '50')

        # 상태 라벨
        self.status = tk.Label(frm2, text='대기 중', anchor='w')
        self.status.grid(row=6, column=0, columnspan=4, sticky='we', pady=(8,0))

        # 재생 타이머/배속 표시
        self.play_timer = tk.Label(frm2, text='재생 시간: 0.0/0.0 초 @1.0x', anchor='w')
        self.play_timer.grid(row=7, column=0, columnspan=4, sticky='we', pady=(6,0))

        # 입력 변경 시 검증
        self.entry_duration.bind('<KeyRelease>', lambda e: self.validate_inputs())
        self.entry_key.bind('<KeyRelease>', lambda e: self.validate_inputs())
        self.entry_interval.bind('<KeyRelease>', lambda e: self.validate_inputs())

        # Exit button at bottom-right of Tab 2
        self.btn_exit_tab2 = tk.Button(frm2, text='프로그램 종료', width=14, command=self.exit_app, bg='#ffcccc')
        self.btn_exit_tab2.grid(row=8, column=3, sticky='e', padx=(0, 0), pady=(10,0))

        # previous hotkey values (for revert on conflict)
        self._hotkeys_prev = {
            'HOTKEY': globals().get('HOTKEY', 'f5'),
            'PLAY_HOTKEY': globals().get('PLAY_HOTKEY', 'f6'),
            'RECORD_START_HOTKEY': globals().get('RECORD_START_HOTKEY', ''),
            'RECORD_STOP_HOTKEY': globals().get('RECORD_STOP_HOTKEY', 'esc'),
        }

        self.validate_inputs()
        # worker 종료 시 UI 갱신을 위한 콜백 등록
        global on_worker_finished
        on_worker_finished = self._on_worker_finished
        # 초기 핫키 설정
        self._on_hotkey_change()
        self._on_playhotkey_change()
        # ensure record hotkey entries are synced
        self._on_record_start_hotkey_change()
        self._on_record_stop_hotkey_change()
        self._on_record_stop_hotkey_change()

    def _on_hotkey_change(self):
        raw = self.entry_hotkey.get().strip()
        parsed = parse_hotkey_str(raw)
        if parsed:
            # check duplicates
            conflicts = []
            for name in ('PLAY_HOTKEY','RECORD_START_HOTKEY','RECORD_STOP_HOTKEY'):
                val = globals().get(name, '')
                if val and val == parsed:
                    conflicts.append(name)
            if conflicts:
                messagebox.showwarning('핫키 충돌', f"{raw.upper()} 키가 이미 다른 핫키로 사용 중입니다: {', '.join(conflicts)}")
                prev = globals().get('HOTKEY', '')
                self.entry_hotkey.delete(0, tk.END)
                self.entry_hotkey.insert(0, prev.upper() if prev else '')
                return
            globals()['HOTKEY'] = parsed
            # 상태 메시지에 핫키 반영
            self.status.config(text=f'시작: {raw.upper()}')
        else:
            globals()['HOTKEY'] = ''
            self.status.config(text='핫키 무효')

    def _hotkey_conflict(self, new_key, own_keyname):
        # check against other hotkeys
        names = {
            'HOTKEY': globals().get('HOTKEY', ''),
            'PLAY_HOTKEY': globals().get('PLAY_HOTKEY', ''),
            'RECORD_START_HOTKEY': globals().get('RECORD_START_HOTKEY', ''),
            'RECORD_STOP_HOTKEY': globals().get('RECORD_STOP_HOTKEY', ''),
        }
        for n, v in names.items():
            if n == own_keyname:
                continue
            if v and v == new_key:
                return n
        return None

    def _set_hotkey_with_check(self, entry_widget, raw, global_name, own_name):
        parsed = parse_hotkey_str(raw)
        if not parsed:
            globals()[global_name] = ''
            self.status.config(text=f'{entry_widget.get().upper()} 핫키 무효')
            return
        conflict = self._hotkey_conflict(parsed, own_name)
        if conflict:
            messagebox.showwarning('핫키 중복', f'핫키 "{parsed.upper()}" 은 이미 {conflict}에 사용되고 있습니다. 다른 키를 선택하세요.')
            # revert to previous
            prev = self._hotkeys_prev.get(global_name, '')
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, prev.upper() if prev else '')
            return
        # accept
        globals()[global_name] = parsed
        self._hotkeys_prev[global_name] = parsed
        # update entry text to uppercase for clarity
        try:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, parsed.upper())
        except Exception:
            pass
        self.status.config(text=f'{entry_widget.get().upper()} 핫키: {parsed.upper()}')

    def _on_playhotkey_change(self):
        raw = self.entry_playhotkey.get().strip()
        self._set_hotkey_with_check(self.entry_playhotkey, raw, 'PLAY_HOTKEY', 'PLAY_HOTKEY')
        # ensure entry displays uppercase version of current
        cur = globals().get('PLAY_HOTKEY','')
        if cur:
            self.entry_playhotkey.delete(0, tk.END)
            self.entry_playhotkey.insert(0, cur.upper())

    def _on_record_start_hotkey_change(self):
        raw = self.entry_record_start.get().strip()
        self._set_hotkey_with_check(self.entry_record_start, raw, 'RECORD_START_HOTKEY', 'RECORD_START_HOTKEY')

    def _on_record_stop_hotkey_change(self):
        raw = self.entry_record_stop.get().strip()
        self._set_hotkey_with_check(self.entry_record_stop, raw, 'RECORD_STOP_HOTKEY', 'RECORD_STOP_HOTKEY')

    def _on_hotkey_change(self):
        raw = self.entry_hotkey.get().strip()
        self._set_hotkey_with_check(self.entry_hotkey, raw, 'HOTKEY', 'HOTKEY')

    def start_playback(self):
        # explicit playback start triggered by '녹화시작' 버튼
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if not script_path:
            messagebox.showerror('오류', '재생할 스크립트를 선택하세요.')
            return
        if playback_thread is not None:
            messagebox.showinfo('정보', '이미 재생 중입니다.')
            return
        # read playback speed (from dropdown)
        speed = 1.0
        try:
            if hasattr(self, 'speed_var'):
                speed = float(self.speed_var.get())
                if not (0.5 <= speed <= 3.0):
                    raise ValueError('invalid speed')
        except Exception:
            speed = 1.0
        # get repeat and sample values
        repeat = 1
        try:
            if hasattr(self, 'entry_repeat'):
                repeat = int(self.entry_repeat.get().strip())
                if repeat < 1:
                    repeat = 1
        except Exception:
            repeat = 1
        self.status.config(text=f'재생 중: {script_path} ({speed}x)')
        # initialize timer display
        try:
            # compute total seconds from file if possible
            with open(script_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    evs = data.get('events', [])
                else:
                    evs = data
                total_ms = int(evs[-1].get('t_ms', 0)) if evs else 0
                total_s = (total_ms / 1000.0) / float(max(1e-9, speed)) * max(1, int(repeat))
        except Exception:
            total_s = 0.0
        if hasattr(self, 'play_timer'):
            self.play_timer.config(text=f'재생 시간: 0.0/{total_s:.1f} 초 @{speed}x')
        self.btn_start.config(state='disabled')
        if hasattr(self, 'btn_start_script'):
            self.btn_start_script.config(state='disabled')
        self.btn_record.config(state='disabled')
        # enable playback stop button
        if hasattr(self, 'btn_stop_play'):
            self.btn_stop_play.config(state='normal')
        self.btn_stop.config(state='normal')
        playback_stop_event.clear()
        # get repeat and sample values
        repeat = 1
        try:
            if hasattr(self, 'entry_repeat'):
                repeat = int(self.entry_repeat.get().strip())
                if repeat < 1:
                    repeat = 1
        except Exception:
            repeat = 1
        sample_ms = 0
        try:
            if hasattr(self, 'entry_sample_ms'):
                sample_ms = int(self.entry_sample_ms.get().strip())
                if sample_ms < 0:
                    sample_ms = 0
        except Exception:
            sample_ms = 0
        self._start_playback_thread(script_path, speed, repeat)

    def play_hotkey_toggle(self):
        # toggle playback via play hotkey
        global playback_thread
        if playback_thread is not None:
            playback_stop_event.set()
            playback_thread = None
            self.status.config(text='재생 중지')
            self.btn_stop.config(state='disabled')
            if hasattr(self, 'btn_stop_play'):
                self.btn_stop_play.config(state='disabled')
            # re-enable record button if not recording
            if hasattr(self, 'btn_record'):
                self.btn_record.config(state='normal' if not globals().get('recording', False) else 'disabled')
            # refresh buttons
            self.validate_inputs()
            return
        # otherwise start if script selected
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if script_path:
            self.start_playback()

    def _on_worker_finished(self):
        # worker 스레드에서 호출될 수 있으므로 메인 스레드에서 UI 업데이트 실행
        self.root.after(0, self._finish_ui_update)

    def _finish_ui_update(self):
        self.status.config(text='대기 중')
        self.btn_stop.config(state='disabled')
        # re-enable record button if not recording
        if hasattr(self, 'btn_record'):
            self.btn_record.config(state='normal' if not globals().get('recording', False) else 'disabled')
        # disable playback stop button
        if hasattr(self, 'btn_stop_play'):
            self.btn_stop_play.config(state='disabled')
        # reset play timer
        if hasattr(self, 'play_timer'):
            self.play_timer.config(text='재생 시간: 0.0/0.0 초 @1.0x')
        # 입력값이 유효하면 시작 버튼 및 스크립트 시작 버튼 활성화
        self.validate_inputs()

    def _update_playback_status(self, elapsed_s: float, total_s: float, speed: float):
        # Update timer label
        try:
            if hasattr(self, 'play_timer'):
                self.play_timer.config(text=f'재생 시간: {elapsed_s:.1f}/{total_s:.1f} 초 @{speed}x')
            # also update status with a brief message
            self.status.config(text=f'재생 중 - {elapsed_s:.1f}/{total_s:.1f} 초 @{speed}x')
        except Exception:
            pass

    def _build_active_window_meta(self):
        """Capture active window info (pid, title, process name) for metadata."""
        info = {}
        try:
            import win32gui
            import win32process
            try:
                import psutil
            except Exception:
                psutil = None

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                info['active_window_hwnd'] = int(hwnd)
                try:
                    info['active_window_title'] = win32gui.GetWindowText(hwnd)
                except Exception:
                    pass
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    info['active_window_pid'] = int(pid)
                    if psutil:
                        try:
                            info['active_process_name'] = psutil.Process(pid).name()
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            # pywin32가 없는 경우 무시
            pass
        return info

    def _get_primary_selected_index(self):
        if not self.selected_row_indices:
            return None
        return min(self.selected_row_indices)

    def _show_mouse_help(self):
        # Show help popup for mouse_click and mouse_scroll parameters
        help_text = (
            "mouse_click\n"
            "  [btn, action, x, y]\n"
            "  btn: Button.left | Button.right\n"
            "  action: press | release (클릭은 press와 release 두 이벤트)\n"
            "  x, y: 화면 좌표\n\n"
            "mouse_scroll\n"
            "  [dx, dy, x, y]\n"
            "  dx: 가로 스크롤 (주로 0)\n"
            "  dy: 세로 스크롤 (+위/-아래)\n"
            "  x, y: 스크롤할 위치 좌표"
        )
        messagebox.showinfo('마우스 이벤트 도움말', help_text)

    # --------------------- JSON Editor Related Methods ---------------------
    def load_script_to_editor(self):
        path = filedialog.askopenfilename(filetypes=[('JSON Files','*.json'),('Text Files','*.txt')])
        if not path:
            return
        # if txt, try migrate
        if path.lower().endswith('.txt'):
            migrated = _migrate_txt_to_json(path)
            if not migrated:
                messagebox.showerror('오류', '마이그레이션 실패')
                return
            path = migrated
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror('오류', f'파일 읽기 실패: {e}')
            return
        # populate UI
        self._populate_editor_from_payload(data)
        self.current_editor_path = path
        self.btn_editor_save.config(state='normal')

    def _open_row_editor(self, index):
        # detailed modal editor for a single row (bigger params textbox)
        if index < 0 or index >= len(self.editor_rows):
            return
        row = self.editor_rows[index]
        t_val = row['t'].get().strip()
        type_val = row['type'].get().strip()
        params_val = row['params'].get().strip()

        modal = tk.Toplevel(self.root)
        modal.title('행 편집')
        modal.transient(self.root)
        modal.grab_set()

        tk.Label(modal, text='시간(ms)').grid(row=0, column=0, sticky='w')
        t_entry = tk.Entry(modal, width=20)
        t_entry.grid(row=0, column=1, sticky='we')
        t_entry.insert(0, t_val)

        tk.Label(modal, text='타입').grid(row=1, column=0, sticky='w')
        type_options = ['key_down', 'key_up', 'mouse_move', 'mouse_click', 'mouse_scroll', 'imgcheck', 'string']
        type_entry = ttk.Combobox(modal, values=type_options, width=37, state='normal')
        type_entry.grid(row=1, column=1, sticky='we')
        type_entry.set(type_val)

        tk.Label(modal, text='파라미터 (JSON 배열)').grid(row=2, column=0, sticky='nw')
        params_text = tk.Text(modal, width=80, height=12)
        params_text.grid(row=2, column=1, sticky='we')
        params_text.insert('1.0', params_val)

        # Store original type for comparison
        original_type = type_val

        def _on_type_change(event=None):
            """Fill default params when type changes and params are empty or type is different."""
            selected_type = type_entry.get().strip()
            current_params = params_text.get('1.0', 'end').strip()
            
            # Default parameters for each type
            defaults = {
                'key_down': '["a"]',
                'key_up': '["a"]',
                'mouse_move': '[100, 100]',
                'mouse_click': '["Button.left", "press", 100, 100]',
                'mouse_scroll': '[0, 1, 100, 100]',
                'imgcheck': '["img/template.png"]',
                'string': '["텍스트를 입력하세요"]'
            }
            
            # Fill default if params empty or type changed from original
            if selected_type in defaults:
                if not current_params or (selected_type != original_type and original_type):
                    params_text.delete('1.0', 'end')
                    params_text.insert('1.0', defaults[selected_type])

        # Bind type selection change
        type_entry.bind('<<ComboboxSelected>>', _on_type_change)

        def _save_and_close():
            self._push_snapshot('행 내용 수정')
            # write back to row entries
            row['t'].delete(0, tk.END)
            row['t'].insert(0, t_entry.get().strip())
            row['type'].delete(0, tk.END)
            row['type'].insert(0, type_entry.get().strip())
            txt = params_text.get('1.0', 'end').strip()
            row['params'].delete(0, tk.END)
            row['params'].insert(0, txt)
            self.btn_editor_save.config(state='normal')
            try:
                modal.grab_release()
            except Exception:
                pass
            modal.destroy()

        btn_frame = tk.Frame(modal)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(8,0))
        tk.Button(btn_frame, text='저장', width=10, command=_save_and_close).pack(side='left', padx=(0,6))
        tk.Button(btn_frame, text='취소', width=10, command=lambda: (modal.grab_release(), modal.destroy())).pack(side='left')
        t_entry.focus_set()

    def _update_editor_scrollregion(self, _event=None):
        bbox = self.editor_canvas.bbox('all')
        if bbox:
            self.editor_canvas.configure(scrollregion=bbox)

    def _sync_editor_canvas_width(self, event):
        # allow horizontal scrolling when content exceeds visible width
        try:
            req_width = self.editor_inner.winfo_reqwidth()
            new_width = max(req_width, event.width)
            self.editor_canvas.itemconfig(self.editor_inner_window, width=new_width)
        except Exception:
            pass

    def _on_mousewheel_editor(self, event):
        try:
            delta = int(-1 * (event.delta / 120))
        except Exception:
            delta = 0
        if delta:
            self.editor_canvas.yview_scroll(delta, 'units')
        return 'break'

    def _populate_editor_from_payload(self, data):
        # meta
        meta = data.get('meta', {}) if isinstance(data, dict) else {}
        self.meta_version.delete(0, tk.END)
        self.meta_version.insert(0, meta.get('recorder_version', ''))
        self.meta_timestamp.delete(0, tk.END)
        self.meta_timestamp.insert(0, meta.get('timestamp', ''))
        self.meta_width.delete(0, tk.END)
        self.meta_width.insert(0, str(meta.get('screen_width', '') or ''))
        self.meta_height.delete(0, tk.END)
        self.meta_height.insert(0, str(meta.get('screen_height', '') or ''))
        # events
        self._clear_editor(skip_snapshot=True)
        raw = data.get('events', data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            return
        for ev in raw:
            if isinstance(ev, dict):
                t_ms = ev.get('t_ms', 0)
                etype = ev.get('type', '')
                params = ev.get('params', [])
            else:
                # legacy list-format
                t_ms = int(ev[0])
                etype = ev[1]
                params = ev[2:]
            # show params as json text
            try:
                params_text = json.dumps(params, ensure_ascii=False)
            except Exception:
                params_text = str(params)
            self._add_editor_row((t_ms, etype, params_text), allow_snapshot=False, defer_regrid=True)
        self._regrid_all_rows()
        self.btn_editor_save.config(state='normal')

    def _add_editor_row(self, ev=None, insert_at=None, allow_snapshot=True, defer_regrid=False):
        """Add or insert a row. If insert_at is None, append to end."""
        if allow_snapshot:
            label = '행 삽입' if insert_at is not None else '행 추가'
            self._push_snapshot(label)
        if insert_at is None:
            idx = len(self.editor_rows)
        else:
            idx = insert_at
        t_val = ''
        type_val = ''
        params_val = ''
        if ev:
            t_val = str(ev[0])
            type_val = str(ev[1])
            params_val = str(ev[2])
        t_entry = tk.Entry(self.editor_inner, width=12)
        t_entry.insert(0, t_val)
        type_entry = tk.Entry(self.editor_inner, width=20)
        type_entry.insert(0, type_val)
        params_entry = tk.Entry(self.editor_inner, width=80)
        params_entry.insert(0, params_val)
        
        new_row = {'t': t_entry, 'type': type_entry, 'params': params_entry, '_bound': False}
        self._bind_row_events(new_row, idx)
        if insert_at is None:
            self.editor_rows.append(new_row)
        else:
            self.editor_rows.insert(insert_at, new_row)
        if not defer_regrid:
            self._regrid_all_rows()

    def _unbind_row_events(self, row):
        """Remove all event bindings from a row to prevent memory leaks."""
        try:
            for w in (row['t'], row['type'], row['params']):
                w.unbind('<KeyRelease>')
                w.unbind('<FocusIn>')
                w.unbind('<FocusOut>')
                w.unbind('<Button-1>')
                w.unbind('<B1-Motion>')
            row['params'].unbind('<Double-Button-1>')
        except Exception:
            pass

    def _bind_row_events(self, row, idx):
        # Skip if already bound to prevent duplicate handlers
        if row.get('_bound', False):
            return
        for w in (row['t'], row['type'], row['params']):
            w.bind('<KeyRelease>', lambda e, lbl='행 내용 수정': self._on_entry_change(e, lbl))
            w.bind('<FocusIn>', lambda e, lbl='행 내용 수정': self._on_entry_focus_in(e, lbl))
            w.bind('<FocusOut>', self._on_entry_focus_out)
            w.bind('<Button-1>', lambda e, i=idx: self._on_row_press(e, i))
            w.bind('<B1-Motion>', lambda e, i=idx: self._on_row_drag(e, i))
        row['params'].bind('<Double-Button-1>', lambda e, i=idx: self._open_row_editor(i))
        row['_bound'] = True

    def _on_row_press(self, event, index):
        """Handle row press with multi-selection (Ctrl-toggle, Shift-range)."""
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        if shift and self.selection_anchor is not None:
            start = min(self.selection_anchor, index)
            end = max(self.selection_anchor, index)
            self.selected_row_indices = set(range(start, end + 1))
        elif ctrl:
            if index in self.selected_row_indices:
                self.selected_row_indices.remove(index)
            else:
                self.selected_row_indices.add(index)
            self.selection_anchor = index
        else:
            self.selected_row_indices = {index}
            self.selection_anchor = index
        self._update_row_selection_display()
        # ensure this row has focus for keyboard shortcuts
        try:
            self.editor_inner.focus_set()
        except Exception:
            pass

    def _on_row_drag(self, event, index):
        """Drag selection: extend range from anchor to current row while dragging."""
        if self.selection_anchor is None:
            self.selection_anchor = index
        start = min(self.selection_anchor, index)
        end = max(self.selection_anchor, index)
        self.selected_row_indices = set(range(start, end + 1))
        self._update_row_selection_display()

    def _push_snapshot(self, label='변경', state=None):
        # 임시: 되돌리기/다시하기 비활성화 시 스냅샷 저장 안 함
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return
        if self._restoring_editor_state:
            return
        snap_state = state if state is not None else self._capture_editor_state()
        if snap_state is None:
            return
        self._undo_stack.append({'state': snap_state, 'label': label or '변경'})
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._refresh_history_menus()

    def _refresh_history_menus(self):
        # 임시: 메뉴 전체 비활성화 표시
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            try:
                self.undo_menu.delete(0, 'end')
                self.undo_menu.add_command(label='비활성화됨(테스트)', state='disabled')
                self.btn_undo.config(state='disabled')
                self.btn_undo_menu.config(state='disabled')
            except Exception:
                pass
            try:
                self.redo_menu.delete(0, 'end')
                self.redo_menu.add_command(label='비활성화됨(테스트)', state='disabled')
                self.btn_redo.config(state='disabled')
                self.btn_redo_menu.config(state='disabled')
            except Exception:
                pass
            return
        self._reset_menu_highlight(self.undo_menu, 'undo')
        self._reset_menu_highlight(self.redo_menu, 'redo')
        try:
            self.undo_menu.delete(0, 'end')
            if not self._undo_stack:
                self.undo_menu.add_command(label='기록 없음', state='disabled')
            else:
                for idx, entry in enumerate(reversed(self._undo_stack)):
                    steps = idx + 1
                    lbl = f'{steps}단계: {entry.get("label", "변경")}'
                    self.undo_menu.add_command(label=lbl, command=lambda c=steps: self._undo_editor(count=c))
        except Exception:
            pass
        try:
            self.redo_menu.delete(0, 'end')
            if not self._redo_stack:
                self.redo_menu.add_command(label='기록 없음', state='disabled')
            else:
                for idx, entry in enumerate(reversed(self._redo_stack)):
                    steps = idx + 1
                    lbl = f'{steps}단계: {entry.get("label", "변경")}'
                    self.redo_menu.add_command(label=lbl, command=lambda c=steps: self._redo_editor(count=c))
        except Exception:
            pass

    def _reset_menu_highlight(self, menu, key=None):
        try:
            end = menu.index('end')
            if end is None:
                return
            for i in range(end + 1):
                menu.entryconfig(i, background=self._menu_default_bg)
            if key:
                self._menu_last_hover[key] = None
                try:
                    menu.selection_clear(0, 'end')
                except Exception:
                    pass
        except Exception:
            pass

    def _on_history_menu_hover(self, menu, stack, key):
        try:
            idx = menu.index('active')
        except Exception:
            idx = None
        # 기록없음 상태이거나 비활성화된 항목이면 아무 동작 안함
        if idx is None or not stack:
            return
        # 항목이 disabled 상태인지 확인
        try:
            state = menu.entrycget(idx, 'state')
            if state == 'disabled':
                return
        except Exception:
            pass
        if self._menu_last_hover.get(key) == idx:
            return
        self._reset_menu_highlight(menu, key)
        try:
            for i in range(idx + 1):
                menu.entryconfig(i, background=self._menu_hover_bg)
            self._menu_last_hover[key] = idx
        except Exception:
            pass

    def _on_entry_focus_in(self, _event=None, label='행 내용 수정'):
        if self._restoring_editor_state:
            return
        if self._edit_baseline_state is None:
            self._edit_baseline_state = self._capture_editor_state()
            self._edit_baseline_label = label
            self._edit_baseline_committed = False

    def _on_entry_change(self, _event=None, label='행 내용 수정'):
        self.btn_editor_save.config(state='normal')
        if self._restoring_editor_state:
            return
        if self._edit_baseline_state is not None and not self._edit_baseline_committed:
            label_to_use = self._edit_baseline_label or label
            self._push_snapshot(label_to_use, state=self._edit_baseline_state)
            self._edit_baseline_committed = True

    def _on_entry_focus_out(self, _event=None):
        self._edit_baseline_state = None
        self._edit_baseline_label = ''
        self._edit_baseline_committed = False

    def _capture_editor_state(self):
        try:
            meta = {
                'recorder_version': self.meta_version.get().strip(),
                'timestamp': self.meta_timestamp.get().strip(),
                'screen_width': self.meta_width.get().strip(),
                'screen_height': self.meta_height.get().strip(),
            }
            events = []
            for r in self.editor_rows:
                ttxt = r['t'].get().strip()
                typ = r['type'].get().strip()
                ptxt = r['params'].get().strip()
                events.append({'t_ms': ttxt, 'type': typ, 'params': ptxt})
            return {'meta': meta, 'events': events}
        except Exception:
            return None

    def _restore_editor_state(self, state):
        if not state:
            return
        self._on_entry_focus_out()
        self._restoring_editor_state = True
        try:
            self._clear_editor(skip_snapshot=True)
            meta = state.get('meta', {}) or {}
            try:
                self.meta_version.insert(0, meta.get('recorder_version', ''))
                self.meta_timestamp.insert(0, meta.get('timestamp', ''))
                self.meta_width.insert(0, meta.get('screen_width', ''))
                self.meta_height.insert(0, meta.get('screen_height', ''))
            except Exception:
                pass
            events = state.get('events', []) or []
            for ev in events:
                try:
                    t_ms = ev.get('t_ms', '')
                    typ = ev.get('type', '')
                    params = ev.get('params', '')
                    self._add_editor_row((t_ms, typ, params), allow_snapshot=False, defer_regrid=True)
                except Exception:
                    pass
            self._regrid_all_rows()
            self.btn_editor_save.config(state='normal')
        finally:
            self._restoring_editor_state = False
            self._update_row_selection_display()

    def _undo_editor(self, event=None, count=1):
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return 'break'
        if not self._undo_stack:
            return 'break'
        steps = min(max(1, count), len(self._undo_stack))
        # 현재 상태 저장
        cur = self._capture_editor_state()
        # 모든 단계를 pop하고 redo 스택에 push
        final_state = None
        for i in range(steps):
            entry = self._undo_stack.pop()
            if i == 0 and cur:  # 처음에만 현재 상태 저장
                self._redo_stack.append({'state': cur, 'label': entry.get('label', '변경')})
                if len(self._redo_stack) > 10:
                    self._redo_stack.pop(0)
            else:
                self._redo_stack.append({'state': entry.get('state'), 'label': entry.get('label', '변경')})
                if len(self._redo_stack) > 10:
                    self._redo_stack.pop(0)
            final_state = entry.get('state')
        # 최종 상태로 한 번만 restore
        if final_state:
            self._restore_editor_state(final_state)
        self._refresh_history_menus()
        return 'break'

    def _redo_editor(self, event=None, count=1):
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return 'break'
        if not self._redo_stack:
            return 'break'
        steps = min(max(1, count), len(self._redo_stack))
        # 현재 상태 저장
        cur = self._capture_editor_state()
        # 모든 단계를 pop하고 undo 스택에 push
        final_state = None
        for i in range(steps):
            entry = self._redo_stack.pop()
            if i == 0 and cur:  # 처음에만 현재 상태 저장
                self._undo_stack.append({'state': cur, 'label': entry.get('label', '변경')})
                if len(self._undo_stack) > 10:
                    self._undo_stack.pop(0)
            else:
                self._undo_stack.append({'state': entry.get('state'), 'label': entry.get('label', '변경')})
                if len(self._undo_stack) > 10:
                    self._undo_stack.pop(0)
            final_state = entry.get('state')
        # 최종 상태로 한 번만 restore
        if final_state:
            self._restore_editor_state(final_state)
        self._refresh_history_menus()
        return 'break'

    def _update_row_selection_display(self):
        for i, r in enumerate(self.editor_rows):
            bg = 'lightyellow' if i in self.selected_row_indices else 'white'
            for w in (r['t'], r['type'], r['params']):
                try:
                    w.config(bg=bg)
                except Exception:
                    pass
        try:
            # keep selection visible after updates
            self.editor_canvas.update_idletasks()
        except Exception:
            pass

    def _regrid_all_rows(self):
        """Re-grid all rows after insert or delete."""
        for i, r in enumerate(self.editor_rows):
            r['t'].grid(row=i, column=0, sticky='we')
            r['type'].grid(row=i, column=1, sticky='we')
            r['params'].grid(row=i, column=2, sticky='we')
            # Unbind and rebind with correct index to update event handlers
            self._unbind_row_events(r)
            r['_bound'] = False
            self._bind_row_events(r, i)
        self._update_row_selection_display()
        try:
            self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox('all'))
        except Exception:
            pass

    def _insert_row_after_selected(self):
        """Insert a new empty row after the selected row."""
        target = self._get_primary_selected_index()
        if target is None:
            messagebox.showinfo('정보', '먼저 행을 클릭하여 선택하세요.')
            return
        self._push_snapshot('행 삽입')
        insert_pos = target + 1
        self._add_editor_row(ev=None, insert_at=insert_pos, allow_snapshot=False)
        self.btn_editor_save.config(state='normal')

    def _add_time_offset(self):
        """Add time offset (ms) to all rows after the selected row."""
        target = self._get_primary_selected_index()
        if target is None:
            messagebox.showinfo('정보', '먼저 기준이 될 행을 클릭하여 선택하세요.')
            return
        offset_str = tk.simpledialog.askstring('시간 추가', '추가할 시간(ms)을 입력하세요:', parent=self.root)
        if not offset_str:
            return
        try:
            offset_ms = int(float(offset_str))
        except Exception:
            messagebox.showerror('오류', '유효한 숫자를 입력하세요.')
            return
        # add offset to all rows after selected
        self._push_snapshot('시간 오프셋 추가')
        for i in range(target + 1, len(self.editor_rows)):
            r = self.editor_rows[i]
            try:
                current_t = int(float(r['t'].get().strip()))
                new_t = current_t + offset_ms
                r['t'].delete(0, tk.END)
                r['t'].insert(0, str(new_t))
            except Exception:
                pass
        self.btn_editor_save.config(state='normal')
        messagebox.showinfo('완료', f'선택된 행({target}) 이후의 {len(self.editor_rows) - target - 1}개 행에\n{offset_ms}ms가 추가되었습니다.')

    def _remove_editor_row(self, index, allow_snapshot=True, defer_regrid=False):
        if index < 0 or index >= len(self.editor_rows):
            return
        if allow_snapshot:
            self._push_snapshot('행 삭제')
        row = self.editor_rows.pop(index)
        try:
            # Unbind events before destroying to prevent memory leaks
            self._unbind_row_events(row)
            row['t'].destroy()
            row['type'].destroy()
            row['params'].destroy()
        except Exception:
            pass
        if not defer_regrid:
            self._regrid_all_rows()
        self.btn_editor_save.config(state='normal')

    def _delete_selected_row(self):
        """Delete the currently selected row in the JSON editor."""
        if not self.selected_row_indices:
            messagebox.showinfo('정보', '삭제할 행을 먼저 선택하세요.')
            return
        # delete in descending order to keep indices valid
        label = f'선택 행 삭제 ({len(self.selected_row_indices)}개)'
        self._push_snapshot(label)
        indices = sorted(self.selected_row_indices, reverse=True)
        for idx in indices:
            self._remove_editor_row(idx, allow_snapshot=False, defer_regrid=True)
        self._regrid_all_rows()
        self.selected_row_indices = set()
        self.selection_anchor = None
        self._update_row_selection_display()
        self.btn_editor_save.config(state='normal')

    def _clear_editor(self, skip_snapshot=False):
        if not skip_snapshot:
            self._push_snapshot('초기화')
        self._on_entry_focus_out()
        for r in list(self.editor_rows):
            try:
                r['t'].destroy()
                r['type'].destroy()
                r['params'].destroy()
            except Exception:
                pass
        self.editor_rows = []
        self.selected_row_indices = set()
        self.selection_anchor = None
        self.meta_version.delete(0, tk.END)
        self.meta_timestamp.delete(0, tk.END)
        self.meta_width.delete(0, tk.END)
        self.meta_height.delete(0, tk.END)
        self.btn_editor_save.config(state='disabled')

    def save_edited_script(self):
        # ask for path
        try:
            fpath = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON Files','*.json')], initialfile='edited_recording.json')
        except Exception:
            fpath = None
        if not fpath:
            return
        # gather meta
        meta = {
            'recorder_version': self.meta_version.get().strip(),
            'timestamp': self.meta_timestamp.get().strip(),
        }
        try:
            w = int(self.meta_width.get().strip()) if self.meta_width.get().strip() else None
            h = int(self.meta_height.get().strip()) if self.meta_height.get().strip() else None
            meta['screen_width'] = w
            meta['screen_height'] = h
        except Exception:
            pass
        # events
        events = []
        for r in self.editor_rows:
            ttxt = r['t'].get().strip()
            typ = r['type'].get().strip()
            ptxt = r['params'].get().strip()
            try:
                t_ms = int(float(ttxt))
            except Exception:
                t_ms = 0
            # parse params: try json.loads, fallback to '|' split
            params = None
            try:
                params = json.loads(ptxt) if ptxt else []
                if not isinstance(params, list):
                    params = [params]
            except Exception:
                # fallback split
                parts = [p.strip() for p in ptxt.split('|')] if ptxt else []
                # try to convert numeric
                def conv(x):
                    if x == '':
                        return ''
                    try:
                        if '.' in x:
                            return float(x)
                        else:
                            return int(x)
                    except Exception:
                        return x
                params = [conv(p) for p in parts]
            events.append({'t_ms': t_ms, 'type': typ, 'params': params})
        payload = {'meta': meta, 'events': events}
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('저장 완료', f'파일을 저장했습니다: {fpath}')
            self.status.config(text=f'저장: {fpath}')
            self.btn_editor_save.config(state='disabled')
            self.current_editor_path = fpath
        except Exception as e:
            messagebox.showerror('저장 실패', f'파일 저장 실패: {e}')

    # --------------------- end JSON Editor ---------------------

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

    def choose_script(self):
        path = filedialog.askopenfilename(filetypes=[('JSON Files','*.json'),('Text Files','*.txt')])
        if path:
            # if txt, auto-migrate to json sidecar
            if path.lower().endswith('.txt'):
                migrated = _migrate_txt_to_json(path)
                if migrated:
                    self.entry_script.delete(0, tk.END)
                    self.entry_script.insert(0, migrated)
                    self.status.config(text=f'마이그레이션 및 선택: {migrated}')
                else:
                    messagebox.showerror('오류', '마이그레이션 실패')
            else:
                self.entry_script.delete(0, tk.END)
                self.entry_script.insert(0, path)
                self.status.config(text=f'스크립트: {path}')
        self.validate_inputs()

    def start_recording(self):
        # disable UI while recording; recording now continues until ESC or stop
        self.btn_record.config(state='disabled')
        self.status.config(text='녹화 중... (ESC로 중지)')
        # ensure stop_event is cleared so recording won't immediately stop
        globals()['stop_event'].clear()

        meta_extra = self._build_active_window_meta()

        def _rec():
            # get sample ms
            sample_ms = 0
            try:
                if hasattr(self, 'entry_sample_ms'):
                    sample_ms = int(self.entry_sample_ms.get().strip())
                    if sample_ms < 0:
                        sample_ms = 0
            except Exception:
                sample_ms = 0
            saved = record_actions(None, sample_ms, meta_extra=meta_extra)
            # clear stop_event to reset global stop state after recording
            try:
                globals()['stop_event'].clear()
            except Exception:
                pass
            if saved:
                self.status.config(text=f'녹화 저장: {saved}')
            else:
                self.status.config(text='녹화 취소')
            # re-enable record button
            self.btn_record.config(state='normal')
            # refresh inputs/buttons
            self.validate_inputs()
        t = threading.Thread(target=_rec, daemon=True)
        t.start()

    def start_append_recording(self):
        # 선택된 스크립트 파일에 이어서 녹화
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if not script_path:
            messagebox.showerror('오류', '이어서 녹화할 스크립트 파일을 먼저 선택하세요.')
            return
        if not os.path.isfile(script_path):
            messagebox.showerror('오류', '선택한 스크립트 파일이 존재하지 않습니다.')
            return
        
        # 기존 파일 읽기
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            messagebox.showerror('오류', f'스크립트 파일 읽기 실패: {e}')
            return
        
        # 마지막 이벤트 시간 가져오기
        if isinstance(existing_data, dict):
            existing_events = existing_data.get('events', [])
            existing_meta = existing_data.get('meta', {})
        else:
            existing_events = existing_data if isinstance(existing_data, list) else []
            existing_meta = {}
        
        time_offset_ms = 0
        if existing_events:
            try:
                last_event = existing_events[-1]
                if isinstance(last_event, dict):
                    time_offset_ms = int(last_event.get('t_ms', 0))
                else:
                    time_offset_ms = int(last_event[0])
            except Exception:
                time_offset_ms = 0
        
        # disable UI while recording
        self.btn_append_record.config(state='disabled')
        self.btn_record.config(state='disabled')
        self.status.config(text=f'이어서 녹화 중... (마지막 시간: {time_offset_ms}ms, ESC로 중지)')
        globals()['stop_event'].clear()

        meta_extra = self._build_active_window_meta()

        def _append_rec():
            # get sample ms
            sample_ms = 0
            try:
                if hasattr(self, 'entry_sample_ms'):
                    sample_ms = int(self.entry_sample_ms.get().strip())
                    if sample_ms < 0:
                        sample_ms = 0
            except Exception:
                sample_ms = 0
            
            # 녹화 수행 (시간 오프셋 적용)
            new_events = []
            saved_path = self._record_and_append(script_path, existing_data, time_offset_ms, sample_ms, meta_extra)
            
            # clear stop_event
            try:
                globals()['stop_event'].clear()
            except Exception:
                pass
            
            if saved_path:
                self.status.config(text=f'이어서 녹화 저장: {saved_path}')
                # 스크립트 경로가 바뀌었을 수 있으므로 업데이트
                self.entry_script.delete(0, tk.END)
                self.entry_script.insert(0, saved_path)
            else:
                self.status.config(text='이어서 녹화 취소')
            
            # re-enable buttons
            self.btn_append_record.config(state='normal')
            self.btn_record.config(state='normal')
            self.validate_inputs()
        
        t = threading.Thread(target=_append_rec, daemon=True)
        t.start()

    def _record_and_append(self, script_path, existing_data, time_offset_ms, sample_ms, meta_extra):
        """Record new events with time offset and append to existing script."""
        global recording, record_events
        if recording:
            return None
        
        recording = True
        record_events = []
        start = time.time()
        last_move_ms = -9999

        def _now_ms():
            return int((time.time() - start) * 1000) + time_offset_ms

        def on_move(x, y):
            nonlocal last_move_ms
            now = _now_ms()
            if sample_ms and (now - last_move_ms - time_offset_ms) < int(sample_ms):
                return
            last_move_ms = now
            record_events.append((now, 'mouse_move', x, y))

        def on_click(x, y, button, pressed):
            record_events.append((_now_ms(), 'mouse_click', str(button), 'press' if pressed else 'release', x, y))

        def on_scroll(x, y, dx, dy):
            record_events.append((_now_ms(), 'mouse_scroll', dx, dy, x, y))

        def on_press(k):
            try:
                ch = k.char
            except Exception:
                ch = str(k)
            record_events.append((_now_ms(), 'key_down', ch))

        def on_release(k):
            try:
                ch = k.char
            except Exception:
                ch = str(k)
            record_events.append((_now_ms(), 'key_up', ch))

        # start listeners
        m_listener = MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        k_listener = Listener(on_press=on_press, on_release=on_release)
        m_listener.start()
        k_listener.start()

        # wait until stop_event is set
        while not globals().get('stop_event', threading.Event()).is_set():
            time.sleep(0.05)

        # stop listeners
        try:
            m_listener.stop()
        except Exception:
            pass
        try:
            k_listener.stop()
        except Exception:
            pass

        recording = False
        
        # 녹화 취소 체크
        if not record_events:
            return None
        
        # 기존 이벤트에 새 이벤트 추가
        if isinstance(existing_data, dict):
            existing_events = existing_data.get('events', [])
            meta = existing_data.get('meta', {})
        else:
            existing_events = existing_data if isinstance(existing_data, list) else []
            meta = {}
        
        # 메타 업데이트
        if meta_extra:
            meta.update(meta_extra)
        meta['recorder_version'] = RECORDER_VERSION
        meta['timestamp'] = datetime.now().isoformat()
        try:
            from tkinter import Tk
            root = Tk()
            root.withdraw()
            meta['screen_width'] = root.winfo_screenwidth()
            meta['screen_height'] = root.winfo_screenheight()
            root.destroy()
        except Exception:
            pass
        
        # 새 이벤트를 JSON 형식으로 변환
        for ev in record_events:
            t_ms = ev[0]
            etype = ev[1]
            params = list(ev[2:])
            existing_events.append({'t_ms': t_ms, 'type': etype, 'params': params})
        
        # 저장
        payload = {'meta': meta, 'events': existing_events}
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return script_path
        except Exception as e:
            messagebox.showerror('저장 실패', f'파일 저장 실패: {e}')
            return None

    def _start_playback_thread(self, fpath, speed=1.0, repeat=1):
        global playback_thread
        playback_thread = threading.Thread(target=playback_from_file, args=(fpath, speed, repeat), daemon=True)
        playback_thread.start()

    def start(self):
        # If script file selected, run playback; otherwise run auto presser
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if script_path:
            # start playback using the existing flow (centralized in start_playback)
            self.start_playback()
            return

        # 기존 시작 동작 (자동 키 입력)
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
        global playback_thread
        if worker_thread is not None:
            # 실행 중이면 중지
            self.stop()
            return
        if playback_thread is not None:
            # 재생 중이면 중지
            playback_stop_event.set()
            playback_thread = None
            self.status.config(text='재생 중지')
            self.btn_start.config(state='normal')
            self.btn_stop.config(state='disabled')
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
        # if script selected, start playback
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if script_path:
            self.start()
            return
        self.start()

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

# imgcheck helper function for playback
def _perform_imgcheck(img_path):
    """Perform imgcheck during playback: find active window and match template."""
    result = {'input_image': img_path, 'passed': False}
    if not os.path.isfile(img_path):
        msg = f'imgcheck: 파일을 찾을 수 없습니다: {img_path}'
        result['message'] = msg
        print(msg)
        return result

    try:
        import cv2
        import numpy as np
        from imgCheck import capture_window, match_templates, find_windows_for_name
    except ImportError:
        msg = 'imgcheck: opencv 또는 imgCheck 모듈이 없습니다.'
        result['message'] = msg
        print(msg)
        return result

    hwnd = None
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            try:
                result['window_title'] = win32gui.GetWindowText(hwnd)
            except Exception:
                pass
            result['window_hwnd'] = int(hwnd)
    except Exception:
        hwnd = None

    if not hwnd:
        msg = 'imgcheck: 활성 창을 찾을 수 없습니다.'
        result['message'] = msg
        print(msg)
        return result

    screen = capture_window(hwnd)
    if screen is None:
        msg = 'imgcheck: 화면 캡처 실패'
        result['message'] = msg
        print(msg)
        return result

    temp_dir = os.path.join(os.getcwd(), 'temp_imgcheck')
    debug_dir = os.path.join(os.getcwd(), 'debugimg')
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(debug_dir, exist_ok=True)
    saved_path = None
    try:
        import shutil
        temp_img = os.path.join(temp_dir, os.path.basename(img_path))
        shutil.copy(img_path, temp_img)
        ok, info = match_templates(screen, temp_dir, threshold=0.8)
        ts = time.strftime('%Y%m%d_%H%M%S')

        if ok:
            tpl = info.get('template') if isinstance(info, dict) else None
            score = info.get('score') if isinstance(info, dict) else None
            loc = info.get('location') if isinstance(info, dict) else None
            size = info.get('size') if isinstance(info, dict) else None
            w_t, h_t = size if size else (0, 0)
            score_text = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
            print(f'imgcheck PASS: {os.path.basename(img_path)} 발견 (score={score_text})')
            vis = screen.copy()
            if loc and size:
                top_left = loc
                bottom_right = (top_left[0] + w_t, top_left[1] + h_t)
                cv2.rectangle(vis, top_left, bottom_right, (0, 255, 0), 2)
            vis_fname = os.path.join(debug_dir, f'imgcheck_pass_{os.path.splitext(os.path.basename(img_path))[0]}_{ts}.png')
            cv2.imwrite(vis_fname, vis)
            saved_path = vis_fname
            result.update({'passed': True, 'score': score, 'saved_path': vis_fname, 'matched_template': tpl, 'message': '템플릿 일치'})
        else:
            best_score = None
            if info and isinstance(info, dict):
                best_raw = info.get('best_score')
                if best_raw and isinstance(best_raw, (list, tuple)) and len(best_raw) > 1:
                    best_score = best_raw[1]
            msg = f'imgcheck FAIL: {os.path.basename(img_path)} 찾지 못함'
            print(msg)
            fail_fname = os.path.join(debug_dir, f'imgcheck_fail_{os.path.splitext(os.path.basename(img_path))[0]}_{ts}.png')
            cv2.imwrite(fail_fname, screen)
            saved_path = fail_fname
            result.update({'passed': False, 'score': best_score, 'saved_path': fail_fname, 'message': '일치 없음'})
    except Exception as e:
        msg = f'imgcheck 실행 중 오류: {e}'
        result['message'] = msg
        print(msg)
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

    result['timestamp'] = datetime.utcnow().isoformat() + 'Z'
    if saved_path:
        result['saved_path'] = saved_path
    return result

def playback_from_file(fpath, speed=1.0, repeat=1):
    global playback_stop_event, playback_thread, on_worker_finished
    target_meta = {}
    app = globals().get('app_instance')
    try:
        if app and hasattr(app, '_build_active_window_meta'):
            target_meta = app._build_active_window_meta()
    except Exception:
        target_meta = {}
    log_data = {
        'script_path': fpath,
        'started_at': datetime.now(),
        'pc_meta': _collect_pc_meta(),
        'imgcheck_results': [],
        'status': 'running',
        'target_meta': target_meta,
    }
    events = []
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # support two formats: top-level list or {'meta':..., 'events':[...]}
            if isinstance(data, dict):
                raw_events = data.get('events', [])
            else:
                raw_events = data
            for ev in raw_events:
                # each ev is dict {'t_ms':..., 'type':..., 'params':[...]} 
                t_ms = int(ev.get('t_ms', 0)) if isinstance(ev, dict) else int(ev[0])
                etype = ev.get('type') if isinstance(ev, dict) else ev[1]
                params = ev.get('params', []) if isinstance(ev, dict) else ev[2:]
                events.append((t_ms, etype, params))
    except Exception as e:
        print('재생 파일 읽기 실패:', e)
        log_data.update({'status': 'error', 'error_message': str(e)})
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        log_data['overall_result'] = 'error'
        _write_test_log(log_data)
        playback_thread = None
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
                pass
        return
    if not events:
        print('재생할 이벤트가 없습니다.')
        log_data.update({'status': 'error', 'error_message': '재생할 이벤트가 없습니다.'})
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        log_data['overall_result'] = 'error'
        _write_test_log(log_data)
        playback_thread = None
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
                pass
        return
    # run playback using absolute scheduling scaled by speed and repeat count
    playback_stop_event.clear()
    base_total_ms = events[-1][0]
    total_s = (base_total_ms / 1000.0) / float(max(1e-9, float(speed))) * max(1, int(repeat))
    app = globals().get('app_instance')
    if app:
        try:
            app.root.after(0, lambda: app._update_playback_status(0.0, total_s, float(speed)))
        except Exception:
            pass
    start_time = time.time()
    try:
        for cycle in range(max(1, int(repeat))):
            cycle_start = start_time + (cycle * (base_total_ms / 1000.0)) / float(max(1e-9, float(speed)))
            for t_ms, etype, params in events:
                if playback_stop_event.is_set():
                    break
                target = cycle_start + (t_ms / 1000.0) / float(max(1e-9, float(speed)))
                sleep_time = target - time.time()
                # update UI while waiting
                if sleep_time > 0 and app:
                    try:
                        elapsed = time.time() - start_time
                        app.root.after(0, lambda e=elapsed, t=total_s, s=float(speed): app._update_playback_status(e, t, s))
                    except Exception:
                        pass
                    time.sleep(sleep_time)
                try:
                    # suppress global hotkey handling while injecting synthetic input
                    globals()['SUPPRESS_HOTKEY'] = True
                    if etype == 'mouse_move':
                        x, y = params
                        mouse_controller.position = (int(x), int(y))
                    elif etype == 'mouse_click':
                        btn = params[0]
                        action = params[1]
                        x = int(params[2])
                        y = int(params[3])
                        mouse_controller.position = (x, y)
                        btn_obj = MouseButton.left if 'left' in str(btn).lower() else MouseButton.right
                        if action == 'press':
                            mouse_controller.press(btn_obj)
                        else:
                            mouse_controller.release(btn_obj)
                    elif etype == 'mouse_scroll':
                        dx = float(params[0])
                        dy = float(params[1])
                        x = int(params[2])
                        y = int(params[3])
                        mouse_controller.position = (x, y)
                        mouse_controller.scroll(int(dx), int(dy))
                    elif etype == 'string':
                        try:
                            text = params[0]
                            controller.type(str(text))
                        except Exception as e:
                            print('string 입력 중 오류:', e)
                    elif etype == 'key_down':
                        k = params[0]
                        # special key names like Key.enter
                        if isinstance(k, str) and k.startswith('Key.'):
                            keyname = k.split('.',1)[1]
                            key_obj = getattr(Key, keyname, None)
                            if key_obj is not None:
                                controller.press(key_obj)
                        elif isinstance(k, str) and len(k) == 1:
                            controller.press(k)
                        else:
                            # fallback: press first char
                            controller.press(str(k)[0])
                    elif etype == 'key_up':
                        k = params[0]
                        if isinstance(k, str) and k.startswith('Key.'):
                            keyname = k.split('.',1)[1]
                            key_obj = getattr(Key, keyname, None)
                            if key_obj is not None:
                                controller.release(key_obj)
                        elif isinstance(k, str) and len(k) == 1:
                            controller.release(k)
                        else:
                            controller.release(str(k)[0])
                    elif etype == 'imgcheck':
                        img_path = params[0] if params else ''
                        result = {'input_image': img_path, 'passed': False}
                        if img_path:
                            print(f'imgcheck 실행: {img_path}')
                            result = _perform_imgcheck(img_path) or result
                        else:
                            print('imgcheck: 이미지 경로가 없습니다.')
                            result['message'] = '이미지 경로가 없습니다.'
                        result['elapsed_ms'] = int((time.time() - start_time) * 1000)
                        log_data['imgcheck_results'].append(result)
                except Exception as e:
                    log_data['status'] = 'error'
                    log_data['error_message'] = str(e)
                    print('재생 중 예외:', e)
                finally:
                    globals()['SUPPRESS_HOTKEY'] = False
                # update UI after event
                if app:
                    try:
                        elapsed = time.time() - start_time
                        app.root.after(0, lambda e=elapsed, t=total_s, s=float(speed): app._update_playback_status(e, t, s))
                    except Exception:
                        pass
            if playback_stop_event.is_set():
                break
    finally:
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        if log_data.get('status') == 'running':
            log_data['status'] = 'cancelled' if playback_stop_event.is_set() else 'completed'
        if log_data['status'] == 'completed':
            if any(not ev.get('passed', False) for ev in log_data.get('imgcheck_results', [])):
                log_data['overall_result'] = 'fail'
            else:
                log_data['overall_result'] = 'pass'
        elif log_data['status'] == 'cancelled':
            log_data['overall_result'] = 'cancelled'
        else:
            log_data.setdefault('overall_result', 'error')

        html_path, csv_path = _write_test_log(log_data)
        if app:
            try:
                app.root.after(0, lambda p=html_path: app.status.config(text=f'로그 생성: {p}'))
            except Exception:
                pass
        print('재생 종료')
        # 정리 및 UI 갱신
        playback_thread = None
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
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

