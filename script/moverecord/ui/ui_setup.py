"""
UI 초기화 및 설정 모듈

moveRecord.py의 __init__ 메서드에서 UI 설정 로직을 분리한 모듈입니다.
"""

import tkinter as tk
from tkinter import ttk

from ui.dialogs.mouse_help import show_mouse_help


def setup_ui(app):
    """
    App 인스턴스의 모든 UI를 초기화합니다.
    
    Args:
        app (App): UI를 설정할 App 인스턴스
    """
    root = app.root
    
    # 기본 설정
    root.title('Please Use Only QA')
    root.resizable(True, True)
    
    pad = 8
    
    # ===== 노트북 (탭 생성) =====
    notebook = ttk.Notebook(root)
    tab1 = tk.Frame(notebook)
    tab2 = tk.Frame(notebook)
    tab3 = tk.Frame(notebook)
    
    notebook.add(tab1, text='단순 반복 매크로')
    notebook.add(tab2, text='녹화 / 스크립트')
    notebook.add(tab3, text='JSON 편집기')
    notebook.pack(fill='both', expand=True)
    
    frm1 = tk.Frame(tab1, padx=pad, pady=pad)
    frm1.pack()
    frm2 = tk.Frame(tab2, padx=pad, pady=pad)
    frm2.pack()
    frm3 = tk.Frame(tab3, padx=pad, pady=pad)
    frm3.pack(fill='both', expand=True)
    
    # Tab 3 그리드 설정
    for c in range(4):
        frm3.columnconfigure(c, weight=1)
    frm3.rowconfigure(6, weight=1)
    
    # ===== Tab 3: JSON 편집기 =====
    _setup_tab3_editor(app, frm3)
    
    # ===== Tab 1: 단순 반복 매크로 =====
    _setup_tab1_simple_macro(app, frm1)
    
    # ===== Tab 2: 녹화 / 스크립트 =====
    _setup_tab2_recording_playback(app, frm2)
    
    # ===== 초기화 =====
    app._hotkeys_prev = {
        'HOTKEY': globals().get('HOTKEY', 'f5'),
        'PLAY_HOTKEY': globals().get('PLAY_HOTKEY', 'f6'),
        'RECORD_START_HOTKEY': globals().get('RECORD_START_HOTKEY', 'f7'),
        'RECORD_STOP_HOTKEY': globals().get('RECORD_STOP_HOTKEY', 'esc'),
    }
    
    app.validate_inputs()
    
    # 초기 핫키 설정
    app._on_hotkey_change()
    app._on_playhotkey_change()
    app._on_record_start_hotkey_change()
    app._on_record_stop_hotkey_change()


def _setup_tab3_editor(app, frm3):
    """Tab 3: JSON 편집기 UI 설정"""
    
    # 에디터 제어 버튼
    app.btn_editor_load = tk.Button(frm3, text='불러오기', width=10, command=app.load_script_to_editor)
    app.btn_editor_load.grid(row=0, column=0, pady=(6,0), sticky='w')
    app.btn_editor_save = tk.Button(frm3, text='저장', width=10, command=app.save_edited_script, state='disabled')
    app.btn_editor_save.grid(row=0, column=1, pady=(6,0), sticky='w')
    app.btn_editor_clear = tk.Button(frm3, text='초기화', width=10, command=app._clear_editor)
    app.btn_editor_clear.grid(row=0, column=2, pady=(6,0), sticky='w')
    app.btn_editor_help = tk.Button(frm3, text='?', width=3, command=show_mouse_help)
    app.btn_editor_help.grid(row=0, column=3, pady=(6,0), sticky='e')
    
    # 메타 필드
    tk.Label(frm3, text='메타 (수정 가능)').grid(row=1, column=0, sticky='w', pady=(8,0))
    
    tk.Label(frm3, text='recorder_version').grid(row=2, column=0, sticky='w')
    app.meta_version = tk.Entry(frm3, width=20)
    app.meta_version.grid(row=2, column=1, sticky='w')
    
    tk.Label(frm3, text='timestamp').grid(row=2, column=2, sticky='w')
    app.meta_timestamp = tk.Entry(frm3, width=30)
    app.meta_timestamp.grid(row=2, column=3, sticky='w')
    
    tk.Label(frm3, text='screen_width').grid(row=3, column=0, sticky='w')
    app.meta_width = tk.Entry(frm3, width=10)
    app.meta_width.grid(row=3, column=1, sticky='w')
    
    tk.Label(frm3, text='screen_height').grid(row=3, column=2, sticky='w')
    app.meta_height = tk.Entry(frm3, width=10)
    app.meta_height.grid(row=3, column=3, sticky='w')
    
    # Active window meta fields
    tk.Label(frm3, text='active_window_title').grid(row=4, column=0, sticky='w')
    app.meta_active_title = tk.Entry(frm3, width=40)
    app.meta_active_title.grid(row=4, column=1, columnspan=3, sticky='w')
    
    tk.Label(frm3, text='active_window_pid').grid(row=5, column=0, sticky='w')
    app.meta_active_pid = tk.Entry(frm3, width=10)
    app.meta_active_pid.grid(row=5, column=1, sticky='w')
    
    tk.Label(frm3, text='active_process_name').grid(row=5, column=2, sticky='w')
    app.meta_active_process = tk.Entry(frm3, width=20)
    app.meta_active_process.grid(row=5, column=3, sticky='w')
    
    tk.Label(frm3, text='(Params는 JSON 배열 형식으로 입력하세요, 예: ["a"])', fg='gray').grid(row=6, column=0, columnspan=4, sticky='w')
    
    # 에디터 헤더
    app.editor_header = tk.Frame(frm3)
    app.editor_header.grid(row=7, column=0, columnspan=4, sticky='we', pady=(6,0))
    tk.Label(app.editor_header, text='시간(ms)', width=12, anchor='w').grid(row=0, column=0, sticky='w')
    tk.Label(app.editor_header, text='타입', width=20, anchor='w').grid(row=0, column=1, sticky='w')
    tk.Label(app.editor_header, text='파라미터 (JSON 배열)', width=60, anchor='w').grid(row=0, column=2, sticky='w')
    
    # 에디터 캔버스 영역
    app.editor_canvas_container = tk.Frame(frm3)
    app.editor_canvas_container.grid(row=8, column=0, columnspan=4, sticky='nsew')
    app.editor_canvas = tk.Canvas(app.editor_canvas_container, height=320)
    app.editor_canvas.pack(side='left', fill='both', expand=True)
    app.editor_vsb = tk.Scrollbar(app.editor_canvas_container, orient='vertical', command=app.editor_canvas.yview)
    app.editor_vsb.pack(side='right', fill='y')
    
    app.editor_hsb = tk.Scrollbar(frm3, orient='horizontal', command=app.editor_canvas.xview)
    app.editor_hsb.grid(row=9, column=0, columnspan=4, sticky='we')
    
    app.editor_canvas.configure(yscrollcommand=app.editor_vsb.set, xscrollcommand=app.editor_hsb.set)
    app.editor_inner = tk.Frame(app.editor_canvas)
    app.editor_inner_window = app.editor_canvas.create_window((0,0), window=app.editor_inner, anchor='nw')
    
    app.editor_inner.bind('<Configure>', app._update_editor_scrollregion)
    app.editor_canvas.bind('<Configure>', app._sync_editor_canvas_width)
    app.editor_canvas.bind_all('<MouseWheel>', app._on_mousewheel_editor)
    
    # 에디터 행 컨테이너 초기화
    app.editor_rows = []
    app.selected_row_indices = set()
    app.selection_anchor = None
    app._undo_stack = []
    app._redo_stack = []
    app._edit_baseline_state = None
    app._edit_baseline_label = ''
    app._edit_baseline_committed = False
    app._restoring_editor_state = False
    
    app.root.bind('<Control-z>', app._undo_editor)
    app.root.bind('<Control-y>', app._redo_editor)
    
    # 에디터 행 관리 버튼
    app.btn_add_row = tk.Button(frm3, text='행 추가(끝)', width=12, command=lambda: app._add_editor_row())
    app.btn_add_row.grid(row=10, column=0, pady=(6,0), sticky='w')
    app.btn_insert_row = tk.Button(frm3, text='행 삽입(중간)', width=12, command=app._insert_row_after_selected)
    app.btn_insert_row.grid(row=10, column=1, pady=(6,0), sticky='w')
    app.btn_time_offset = tk.Button(frm3, text='시간 추가', width=10, command=app._add_time_offset)
    app.btn_time_offset.grid(row=10, column=2, pady=(6,0), sticky='w')
    app.btn_delete_row = tk.Button(frm3, text='행 삭제', width=10, command=app._delete_selected_row)
    app.btn_delete_row.grid(row=10, column=3, pady=(6,0), sticky='w')
    
    app.btn_exit_tab3 = tk.Button(frm3, text='프로그램 종료', width=14, command=app.exit_app, bg='#ffcccc')
    app.btn_exit_tab3.grid(row=11, column=3, sticky='e', padx=(0, 0), pady=(10,0))
    
    # 되돌리기/다시하기 메뉴 설정
    app._menu_hover_bg = '#d9e8ff'
    
    app.btn_undo = tk.Button(frm3, text='되돌리기 (Ctrl+Z)', width=16, command=lambda: app._undo_editor())
    app.btn_undo.grid(row=11, column=0, pady=(4,0), sticky='w')
    app.btn_undo_menu = tk.Menubutton(frm3, text='▼', width=3, relief='raised')
    app.btn_undo_menu.grid(row=11, column=1, pady=(4,0), sticky='w')
    app.undo_menu = tk.Menu(app.btn_undo_menu, tearoff=0)
    app.btn_undo_menu.configure(menu=app.undo_menu)
    
    app.btn_redo = tk.Button(frm3, text='다시하기 (Ctrl+Y)', width=16, command=lambda: app._redo_editor())
    app.btn_redo.grid(row=11, column=2, pady=(4,0), sticky='w')
    app.btn_redo_menu = tk.Menubutton(frm3, text='▼', width=3, relief='raised')
    app.btn_redo_menu.grid(row=11, column=3, pady=(4,0), sticky='w')
    app.redo_menu = tk.Menu(app.btn_redo_menu, tearoff=0)
    app.btn_redo_menu.configure(menu=app.redo_menu)
    
    # 임시: 요청에 따라 되돌리기/다시하기 UI 비활성화
    if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
        try:
            app.btn_undo.config(state='disabled')
            app.btn_undo_menu.config(state='disabled')
            app.btn_redo.config(state='disabled')
            app.btn_redo_menu.config(state='disabled')
        except Exception:
            pass
    
    app._menu_default_bg = app.undo_menu.cget('background')
    app._menu_last_hover = {'undo': None, 'redo': None}
    
    app.undo_menu.bind('<<MenuSelect>>', lambda e: app._on_history_menu_hover(app.undo_menu, app._undo_stack, 'undo'))
    app.redo_menu.bind('<<MenuSelect>>', lambda e: app._on_history_menu_hover(app.redo_menu, app._redo_stack, 'redo'))
    app.undo_menu.bind('<Unmap>', lambda e: app._reset_menu_highlight(app.undo_menu, 'undo'))
    app.redo_menu.bind('<Unmap>', lambda e: app._reset_menu_highlight(app.redo_menu, 'redo'))
    app.undo_menu.bind('<Leave>', lambda e: app._reset_menu_highlight(app.undo_menu, 'undo'))
    app.redo_menu.bind('<Leave>', lambda e: app._reset_menu_highlight(app.redo_menu, 'redo'))
    app.undo_menu.bind('<ButtonRelease-1>', lambda e: app._reset_menu_highlight(app.undo_menu, 'undo'))
    app.redo_menu.bind('<ButtonRelease-1>', lambda e: app._reset_menu_highlight(app.redo_menu, 'redo'))
    
    app._refresh_history_menus()


def _setup_tab1_simple_macro(app, frm1):
    """Tab 1: 단순 반복 매크로 UI 설정"""
    
    # 실행 시간
    tk.Label(frm1, text='실행 시간 (초)').grid(row=0, column=0, sticky='w')
    app.entry_duration = tk.Entry(frm1, width=20)
    app.entry_duration.grid(row=0, column=1)
    
    # 키 입력
    tk.Label(frm1, text='입력할 키').grid(row=1, column=0, sticky='w')
    app.entry_key = tk.Entry(frm1, width=20)
    app.entry_key.grid(row=1, column=1)
    
    # 간격(ms)
    tk.Label(frm1, text='간격 (ms)').grid(row=2, column=0, sticky='w')
    app.entry_interval = tk.Entry(frm1, width=20)
    app.entry_interval.grid(row=2, column=1)
    
    # 시작 키(핫키)
    tk.Label(frm1, text='시작 키 (핫키)').grid(row=3, column=0, sticky='w')
    app.entry_hotkey = tk.Entry(frm1, width=20)
    app.entry_hotkey.grid(row=3, column=1)
    app.entry_hotkey.insert(0, 'F5')
    app.entry_hotkey.bind('<KeyRelease>', lambda e: app._on_hotkey_change())
    
    # 시작/중지 버튼
    app.btn_start = tk.Button(frm1, text='시작', width=10, command=app.start)
    app.btn_start.grid(row=4, column=0, pady=(10,0))
    app.btn_stop = tk.Button(frm1, text='중지', width=10, command=app.stop, state='disabled')
    app.btn_stop.grid(row=4, column=1, pady=(10,0))
    
    # 종료 버튼
    app.btn_exit_tab1 = tk.Button(frm1, text='프로그램 종료', width=14, command=app.exit_app, bg='#ffcccc')
    app.btn_exit_tab1.grid(row=4, column=2, columnspan=1, sticky='e', padx=(50, 0), pady=(10,0))
    
    # 입력 변경 시 검증
    app.entry_duration.bind('<KeyRelease>', lambda e: app.validate_inputs())
    app.entry_key.bind('<KeyRelease>', lambda e: app.validate_inputs())
    app.entry_interval.bind('<KeyRelease>', lambda e: app.validate_inputs())


def _setup_tab2_recording_playback(app, frm2):
    """Tab 2: 녹화 / 스크립트 UI 설정"""
    
    # 재생 핫키
    tk.Label(frm2, text='재생 핫키').grid(row=0, column=0, sticky='w')
    app.entry_playhotkey = tk.Entry(frm2, width=20)
    app.entry_playhotkey.grid(row=0, column=1)
    app.entry_playhotkey.insert(0, 'F6')
    app.entry_playhotkey.bind('<KeyRelease>', lambda e: app._on_playhotkey_change())
    
    # 녹화 시작 키
    tk.Label(frm2, text='녹화 시작 키').grid(row=0, column=2, sticky='w')
    app.entry_record_start = tk.Entry(frm2, width=15)
    app.entry_record_start.grid(row=0, column=3)
    app.entry_record_start.insert(0, 'F7')
    app.entry_record_start.bind('<KeyRelease>', lambda e: app._on_record_start_hotkey_change())
    
    # 녹화 종료 키
    tk.Label(frm2, text='녹화 종료 키').grid(row=1, column=2, sticky='w')
    app.entry_record_stop = tk.Entry(frm2, width=15)
    app.entry_record_stop.grid(row=1, column=3)
    app.entry_record_stop.insert(0, 'ESC')
    app.entry_record_stop.bind('<KeyRelease>', lambda e: app._on_record_stop_hotkey_change())
    
    # 버튼들
    app.btn_record = tk.Button(frm2, text='녹화', width=10, command=app.start_recording)
    app.btn_record.grid(row=2, column=0, pady=(10,0))
    app.btn_append_record = tk.Button(frm2, text='이어서 녹화', width=12, command=app.start_append_recording, state='disabled')
    app.btn_append_record.grid(row=2, column=1, pady=(10,0))
    app.btn_start_script = tk.Button(frm2, text='스크립트 시작', width=12, command=app.start_playback, state='disabled')
    app.btn_start_script.grid(row=2, column=2, pady=(10,0))
    app.btn_stop_play = tk.Button(frm2, text='재생 중지', width=10, command=lambda: app.play_hotkey_toggle(), state='disabled')
    app.btn_stop_play.grid(row=2, column=3, pady=(10,0))
    
    # 스크립트 선택
    tk.Label(frm2, text='스크립트 파일').grid(row=3, column=0, sticky='w')
    app.entry_script = tk.Entry(frm2, width=40)
    app.entry_script.grid(row=3, column=1, columnspan=2, sticky='we')
    app.entry_script.bind('<KeyRelease>', lambda e: app.validate_inputs())
    app.btn_browse = tk.Button(frm2, text='선택', width=8, command=app.choose_script)
    app.btn_browse.grid(row=3, column=3, padx=(6,0))
    
    # 배속 드롭다운
    tk.Label(frm2, text='배속 (x)').grid(row=4, column=0, sticky='w')
    app.speed_var = tk.StringVar(value='1.0')
    speed_options = ['0.5', '0.8', '1.0', '1.2', '1.5', '2', '3']
    app.opt_speed = tk.OptionMenu(frm2, app.speed_var, *speed_options, command=lambda _: app.validate_inputs())
    app.opt_speed.config(width=6)
    app.opt_speed.grid(row=4, column=1)
    
    # 반복 횟수
    tk.Label(frm2, text='반복 횟수').grid(row=4, column=2, sticky='w')
    app.entry_repeat = tk.Entry(frm2, width=8)
    app.entry_repeat.grid(row=4, column=3)
    app.entry_repeat.insert(0, '1')
    
    # 샘플링 옵션
    tk.Label(frm2, text='마우스 샘플링(ms, 0=비활성)').grid(row=5, column=0, sticky='w')
    app.entry_sample_ms = tk.Entry(frm2, width=10)
    app.entry_sample_ms.grid(row=5, column=1)
    app.entry_sample_ms.insert(0, '50')
    
    # 상태 라벨
    app.status = tk.Label(frm2, text='대기 중', anchor='w')
    app.status.grid(row=6, column=0, columnspan=4, sticky='we', pady=(8,0))
    
    # 재생 타이머/배속 표시
    app.play_timer = tk.Label(frm2, text='재생 시간: 0.0/0.0 초 @1.0x', anchor='w')
    app.play_timer.grid(row=7, column=0, columnspan=4, sticky='we', pady=(6,0))
    
    # 종료 버튼
    app.btn_exit_tab2 = tk.Button(frm2, text='프로그램 종료', width=14, command=app.exit_app, bg='#ffcccc')
    app.btn_exit_tab2.grid(row=8, column=3, sticky='e', padx=(0, 0), pady=(10,0))
