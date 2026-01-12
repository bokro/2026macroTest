# 📁 프로젝트 아키텍처

## 폴더 및 파일 구조

```
e:\PythonProject\2026macroTest\script\moverecord/
│
├── 📄 moveRecord.py              (메인 진입점 & GUI 애플리케이션)
├── 📄 moveRecord_backup.py       (원본 백업)
├── 📄 __init__.py
│
├── 📁 config/                    (설정 & 상수)
│   ├── 📄 __init__.py
│   └── 📄 constants.py          (전역 상수)
│       ├── RECORDER_VERSION
│       ├── HOTKEY, PLAY_HOTKEY
│       ├── RECORD_START_HOTKEY, RECORD_STOP_HOTKEY
│       ├── SPECIAL_KEYS
│       └── DID_DISABLE_UNDO_REDO_ONCE
│
├── 📁 utils/                     (유틸리티 함수)
│   ├── 📄 __init__.py
│   ├── 📄 key_utils.py          (키 처리)
│   │   ├── key_to_name()
│   │   ├── parse_hotkey_str()
│   │   └── parse_key()
│   │
│   ├── 📄 file_utils.py         (파일 & PC 정보)
│   │   ├── collect_pc_meta()
│   │   ├── escape_html()
│   │   ├── path_to_href()
│   │   └── get_base_dir()
│   │
│   ├── 📄 html_utils.py         (HTML 생성)
│   │   ├── format_datetime()
│   │   ├── create_meta_row()
│   │   ├── build_summary_rows()
│   │   ├── build_pc_meta_rows()
│   │   ├── build_imgcheck_rows()
│   │   └── generate_html()
│   │
│   ├── 📄 logging.py            (로깅)
│   │   └── write_test_log()
│   │
│   └── 📄 imgcheck_utils.py     (이미지 체크)
│       └── perform_imgcheck()
│
├── 📁 recording/                 (녹화 관련)
│   ├── 📄 __init__.py
│   ├── 📄 save_events.py        (이벤트 저장)
│   │   ├── save_events_to_file()
│   │   └── migrate_txt_to_json()
│   │
│   └── 📄 record_actions.py     (녹화 실행)
│       └── record_actions()
│
├── 📁 playback/                  (재생 관련)
│   ├── 📄 __init__.py
│   └── 📄 playback_engine.py    (재생 엔진)
│       ├── playback_from_file()
│       ├── play_event()
│       └── _suppress_hotkey (모듈 플래그)
│
├── 📁 ui/                        (UI 관련)
│   ├── 📄 __init__.py
│   └── 📄 hotkey.py             (글로벌 핫키)
│       ├── on_press_global()
│       └── create_global_hotkey_listener()
│
└── 📁 workers/                   (워커 스레드)
    ├── 📄 __init__.py
    └── 📄 simple_macro.py        (반복 매크로)
        ├── worker()
        └── show_exit_message()
```

---

## 모듈 책임 분담

| 모듈 | 목적 | 주요 함수 |
|------|------|---------|
| **config** | 전역 설정 관리 | 상수 정의 |
| **utils** | 범용 헬퍼 함수 | 키 처리, 파일 I/O, HTML 생성, 로깅 |
| **recording** | 액션 녹화 | 마우스/키 감지, 이벤트 저장 |
| **playback** | 이벤트 재생 | 녹화된 액션 재생, imgcheck 실행 |
| **ui** | 사용자 인터페이스 | 글로벌 핫키 처리 |
| **workers** | 백그라운드 작업 | 반복 매크로 실행 |

---

## 프로세스 흐름도

### 1. 프로그램 시작
```
moveRecord.py
├── 모듈 임포트 (config, utils, recording, playback, ui, workers)
├── 글로벌 변수 초기화 (stop_event, playback_stop_event, 스레드)
├── App 클래스 생성
├── 3개 탭 UI 구성
│  ├─ Tab 1: 반복 매크로 (simple macro)
│  ├─ Tab 2: 녹화/재생 (recording/playback)
│  └─ Tab 3: JSON 편집기 (script editor)
└── 글로벌 핫키 리스너 시작
```

### 2. Tab 1: 반복 매크로 실행
```
App.start()
└── worker(duration_s, interval_ms, key_val, ...)
    ├── 설정된 시간 동안 반복
    ├── 설정된 간격으로 키 입력
    ├── ESC 또는 stop_event로 중지 가능
    └── 완료 시 show_exit_message()
        ├── MB_SYSTEMMODAL 플래그로 항상 위에 표시
        └── 콜백: on_worker_finished() → _finish_ui_update()
```

### 3. Tab 2: 녹화
```
App.start_recording()
└── record_actions(duration_s, sample_ms, ...)
    ├── 마우스 움직임 감지 (on_move)
    ├── 마우스 클릭 감지 (on_click)
    ├── 마우스 스크롤 감지 (on_scroll)
    ├── 키보드 입력 감지 (on_press/on_release)
    └── save_events_to_file(event_list)
        └── JSON 파일로 저장 (메타 정보 포함)
```

### 4. Tab 2: 재생
```
App.start_playback()
└── playback_from_file(fpath, speed, repeat, ...)
    ├── 파일에서 이벤트 읽기
    ├── 배속 적용 (0.5x ~ 3.0x)
    ├── 반복 횟수만큼 재생
    ├── play_event() 루프 (각 이벤트)
    │  ├── mouse_move: 마우스 이동
    │  ├── mouse_click: 마우스 클릭
    │  ├── mouse_scroll: 마우스 스크롤
    │  ├── string: 문자열 입력
    │  ├── key_down/key_up: 키 입력
    │  └── imgcheck: 이미지 검증
    │     └── perform_imgcheck()
    │        └── 템플릿 매칭 후 결과 반환
    ├── 로그 수집 및 HTML 생성
    │  └── write_test_log()
    │     ├── generate_html()
    │     └── CSV 저장
    ├── _suppress_hotkey 플래그 관리 (ESC 오작동 방지)
    └── 브라우저에서 로그 자동 열기
```

### 5. Tab 3: JSON 편집기
```
App 메서드들
├── load_script_to_editor() - 파일 로드
├── _add_editor_row() - 행 추가
├── _insert_row_after_selected() - 행 삽입
├── _open_row_editor() - 모달 편집
├── _delete_selected_row() - 행 삭제
├── save_edited_script() - 파일 저장
└── 되돌리기/다시하기 기능
    ├── _undo_editor()
    └── _redo_editor()
```

---

## 데이터 흐름

### 녹화 데이터 구조
```json
{
  "meta": {
    "recorder_version": "2.0.0",
    "timestamp": "2026-01-12T10:30:00",
    "screen_width": 1920,
    "screen_height": 1080
  },
  "events": [
    {
      "t_ms": 0,
      "type": "mouse_move",
      "params": [100, 200]
    },
    {
      "t_ms": 50,
      "type": "mouse_click",
      "params": ["Button.left", "press", 100, 200]
    },
    {
      "t_ms": 100,
      "type": "key_down",
      "params": ["a"]
    },
    ...
  ]
}
```

### 재생 로그 구조
```json
{
  "summary": {
    "total_events": 100,
    "success_count": 95,
    "failed_count": 5,
    "status": "completed"
  },
  "pc_meta": {
    "pc_name": "USER-PC",
    "username": "User"
  },
  "imgcheck_results": [
    {
      "filename": "template.png",
      "result": "PASS",
      "match_score": 0.95
    }
  ]
}
```

---

## 스레딩 모델

### 전역 변수
```python
stop_event = threading.Event()              # 워커 중지 신호
playback_stop_event = threading.Event()     # 재생 중지 신호
worker_thread = None                        # 워커 스레드
playback_thread = None                      # 재생 스레드
```

### 스레드 라이프사이클
```
시작
├─ worker_thread 생성 (워커 실행)
│  └─ 종료 → on_worker_finished() 콜백
│     └─ _finish_ui_update()
│        ├─ playback_thread = None
│        ├─ worker_thread = None
│        ├─ stop_event.clear()
│        └─ playback_stop_event.clear()
│
└─ playback_thread 생성 (재생 실행)
   └─ 종료 → on_worker_finished() 콜백
      └─ _finish_ui_update()
         ├─ playback_thread = None
         ├─ worker_thread = None
         ├─ stop_event.clear()
         └─ playback_stop_event.clear()
```

**중요**: 스레드 종료 후 반드시 event 플래그를 초기화해야 다음 실행이 가능합니다.

---

## 핫키 처리 메커니즘

### 글로벌 핫키
```
F5: 반복 매크로 시작/중지 (토글)
F6: 스크립트 재생 시작/중지 (토글)
F7: 녹화 시작
ESC: 즉시 중지 (워커/재생 모두)
```

### ESC 처리 로직
```
on_press_global(key)
├─ key == ESC?
│  ├─ playback_engine._suppress_hotkey == True?
│  │  └─ YES: 무시 (매크로 내 ESC 키)
│  └─ NO: stop_event.set() / playback_stop_event.set()
└─ 다른 핫키 처리
```

**_suppress_hotkey**: 매크로 재생 중 합성 입력(synthetic input)이 글로벌 핫키로 인식되지 않도록 방지

---

## 임포트 구조

### moveRecord.py에서의 임포트
```python
# 설정
from config.constants import HOTKEY, PLAY_HOTKEY, RECORDER_VERSION, ...

# 유틸리티
from utils.key_utils import parse_key, parse_hotkey_str, key_to_name
from utils.file_utils import collect_pc_meta, escape_html
from utils.imgcheck_utils import perform_imgcheck
from utils.logging import write_test_log

# 기능 모듈
from recording.record_actions import record_actions
from recording.save_events import save_events_to_file, migrate_txt_to_json
from playback.playback_engine import playback_from_file
from ui.hotkey import on_press_global, create_listener
from workers.simple_macro import worker, show_exit_message
```

---

## 에러 처리 및 복구

### imgCheck 임포트
```python
# utils/imgcheck_utils.py
try:
    from imgCheck import capture_window, match_templates, find_windows_for_name
except ModuleNotFoundError:
    # 동적 경로 추가 후 재시도
    sys.path.insert(0, str(IMGCHECK_DIR))
    from imgCheck import ...
```

### 이벤트 재생 중 오류
```python
try:
    play_event(...)
except Exception as e:
    # 로그 기록
    # 계속 진행 또는 중지
```

---

## 성능 고려사항

### 녹화 샘플링
- `sample_ms`: 마우스 움직임 샘플링 간격 (기본: 50ms)
- 작은 값 → 더 많은 이벤트 → 더 큰 파일, 더 부드러운 재생
- 큰 값 → 더 적은 이벤트 → 더 작은 파일, 뚝뚝한 재생

### 이미지 매칭
- 템플릿 크기: 작을수록 빠름
- 스케일 탐색: 0.5x ~ 2.0x (121 단계)
- 업샘플링: 작은 템플릿에 대해 자동 적용

### 재생 배속
- 0.5x: 느림 (시간이 2배)
- 1.0x: 정상
- 3.0x: 빠름 (시간이 1/3)

---

## 확장 포인트

### 새 이벤트 타입 추가
```python
# playback/playback_engine.py에서
elif event_type == 'new_type':
    # 처리 로직
    pass
```

### 새 유틸 함수 추가
```python
# utils/new_module.py 생성
def new_function():
    ...

# moveRecord.py에서 임포트
from utils.new_module import new_function
```

### 새 워커 타입 추가
```python
# workers/new_worker.py 생성
def new_worker(params):
    ...
    on_worker_finished()  # 콜백 호출

# moveRecord.py에서 사용
new_worker_thread = threading.Thread(target=new_worker, ...)
```

---

## 주요 개선사항

### 리팩토링 전후 비교

| 항목 | 리팩토링 전 | 리팩토링 후 |
|------|-----------|----------|
| **파일 수** | 1 | 14+ |
| **파일 크기** | 2,588줄 | 50-400줄 |
| **모듈 수** | 1 | 6 |
| **폴더 수** | 0 | 6 |
| **재사용성** | 낮음 | 높음 |
| **가독성** | 낮음 | 높음 |
| **유지보수성** | 낮음 | 높음 |
| **테스트 가능성** | 낮음 | 높음 |

---

## 참고 문서

- [README.md](README.md) - 프로젝트 개요 및 사용법
- [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md) - 마이그레이션 및 개발 가이드
- 각 모듈 파일의 docstring 참고
