# 📘 리팩토링 가이드 및 개발 문서

## 목차
1. [개요](#개요)
2. [마이그레이션 가이드](#마이그레이션-가이드)
3. [모듈별 상세 설명](#모듈별-상세-설명)
4. [사용 예시](#사용-예시)
5. [개발 팁](#개발-팁)
6. [트러블슈팅](#트러블슈팅)

---

## 개요

### 리팩토링 목표
- ✅ 코드 가독성 향상 (2,588줄 → 모듈화)
- ✅ 유지보수 용이성 개선 (각 기능별 독립 파일)
- ✅ 재사용성 증대 (모듈을 다른 프로젝트에서 사용 가능)
- ✅ 테스트 가능성 개선 (각 모듈 개별 테스트 가능)

### 달성 결과
- **새로운 폴더**: 6개 (config, utils, recording, playback, ui, workers)
- **새로운 파일**: 14개 (모듈 파일 + __init__.py)
- **코드 라인**: 2,588줄 → 약 1,962줄 (Main) + 600줄 (모듈)

---

## 마이그레이션 가이드

### 1단계: 폴더 구조 확인
```bash
cd script/moverecord
ls -la

# 다음이 있는지 확인:
# ✅ config/ (constants.py 포함)
# ✅ utils/ (key_utils, file_utils, html_utils, imgcheck_utils, logging.py)
# ✅ recording/ (record_actions.py, save_events.py)
# ✅ playback/ (playback_engine.py)
# ✅ ui/ (hotkey.py)
# ✅ workers/ (simple_macro.py)
```

### 2단계: 임포트 확인
moveRecord.py의 import 섹션이 다음과 같은지 확인:

```python
# 설정
from config.constants import (
    RECORDER_VERSION, HOTKEY, PLAY_HOTKEY, RECORD_START_HOTKEY,
    RECORD_STOP_HOTKEY, SUPPRESS_HOTKEY, DID_DISABLE_UNDO_REDO_ONCE, SPECIAL_KEYS
)

# 유틸리티
from utils.key_utils import key_to_name, parse_hotkey_str, parse_key
from utils.file_utils import collect_pc_meta, escape_html, path_to_href
from utils.imgcheck_utils import perform_imgcheck
from utils.logging import write_test_log

# 기능 모듈
from recording.record_actions import record_actions
from recording.save_events import save_events_to_file, migrate_txt_to_json
from playback.playback_engine import playback_from_file
from ui.hotkey import on_press_global, create_listener
from workers.simple_macro import worker, show_exit_message
```

### 3단계: 기본 동작 테스트
```python
# Python 인터프리터에서
python
>>> from config.constants import HOTKEY
>>> print(HOTKEY)  # 'f5' 출력되면 OK

>>> from utils.key_utils import parse_key
>>> print(parse_key('a'))  # 'a' 출력되면 OK

>>> from recording.record_actions import record_actions
>>> print(record_actions)  # <function> 출력되면 OK
```

### 4단계: 프로그램 실행
```bash
python moveRecord.py
```

---

## 모듈별 상세 설명

### config/constants.py
**역할**: 전역 상수 관리

```python
from config.constants import RECORDER_VERSION, HOTKEY, SPECIAL_KEYS

# 사용 예
print(RECORDER_VERSION)  # '2.0.0'
print(HOTKEY)            # 'f5'
print(SPECIAL_KEYS)      # {'f5': 'F5', 'esc': 'Escape', ...}
```

**정의된 상수**:
- `RECORDER_VERSION`: 버전 정보
- `HOTKEY`: 반복 매크로 시작 키 (기본: 'f5')
- `PLAY_HOTKEY`: 재생 시작 키 (기본: 'f6')
- `RECORD_START_HOTKEY`: 녹화 시작 키 (기본: 'f7')
- `RECORD_STOP_HOTKEY`: 녹화 중지 키 (기본: 'esc')
- `SPECIAL_KEYS`: 특수 키 매핑 딕셔너리

---

### utils/key_utils.py
**역할**: 키 입력 처리 함수

```python
from utils.key_utils import parse_key, parse_hotkey_str, key_to_name

# 키 파싱
key = parse_key('a')           # 'a' 반환
key = parse_key('enter')       # Key.enter 반환
key = parse_key('invalid')     # None 반환

# 핫키 파싱
hotkey = parse_hotkey_str('f5')       # 'f5' 반환
hotkey = parse_hotkey_str('ctrl+a')   # 'ctrl+a' 반환

# 키 이름 조회
name = key_to_name('f5')       # 'F5' 반환
name = key_to_name('a')        # 'A' 반환
```

**함수 목록**:
- `parse_key(key_str)`: 문자열을 pynput 키 객체로 변환
- `parse_hotkey_str(s)`: 핫키 문자열 파싱 및 검증
- `key_to_name(key)`: 키를 사람이 읽을 수 있는 이름으로 변환

---

### utils/file_utils.py
**역할**: 파일 및 시스템 정보 관리

```python
from utils.file_utils import collect_pc_meta, escape_html, path_to_href

# PC 정보 수집
meta = collect_pc_meta()
print(meta)  # {'pc_name': 'USER-PC', 'username': 'User', ...}

# HTML 이스케이프
safe_html = escape_html('<script>alert("xss")</script>')
# '&lt;script&gt;alert("xss")&lt;/script&gt;' 반환

# 경로를 href로 변환
href = path_to_href('e:\\logs\\test.html')
# 'file:///e:/logs/test.html' 반환
```

**함수 목록**:
- `collect_pc_meta()`: PC 정보 (이름, 사용자, 해상도 등)
- `escape_html(text)`: HTML 특수문자 이스케이프
- `path_to_href(path)`: 파일 경로를 file:// URI로 변환
- `get_base_dir()`: 프로젝트 루트 디렉토리 반환

---

### utils/html_utils.py
**역할**: 재생 로그 HTML 생성

```python
from utils.html_utils import generate_html

log_data = {
    'summary': {...},
    'pc_meta': {...},
    'imgcheck_results': [...]
}

html = generate_html(log_data)
# HTML 문자열 반환 (브라우저에서 표시 가능)
```

**함수 목록**:
- `generate_html(log_data)`: 로그 데이터를 HTML로 변환
- `format_datetime(dt)`: 날짜 시간 포맷
- `create_meta_row(label, value)`: 메타 정보 행 생성
- `build_summary_rows(summary)`: 요약 정보 행 생성
- `build_imgcheck_rows(results)`: imgcheck 결과 행 생성

---

### utils/imgcheck_utils.py
**역할**: 이미지 매칭 기능

```python
from utils.imgcheck_utils import perform_imgcheck

result = perform_imgcheck('template.png')
# {
#     'filename': 'template.png',
#     'result': 'PASS' or 'FAIL',
#     'match_score': 0.95,
#     'captured_image': '...',
#     'match_image': '...'
# }
```

**함수 목록**:
- `perform_imgcheck(img_path)`: 이미지 템플릿 매칭
  - 활성 창 캡처
  - OpenCV 템플릿 매칭
  - 매칭 결과 반환

---

### utils/logging.py
**역할**: 테스트 로그 저장

```python
from utils.logging import write_test_log

log_data = {
    'summary': {'total_events': 100, 'status': 'completed'},
    'pc_meta': {...},
    'imgcheck_results': [...]
}

saved_path = write_test_log(log_data)
# CSV 파일과 HTML 파일 생성
# 브라우저에서 HTML 자동 오픈
```

**함수 목록**:
- `write_test_log(log_data, base_dir)`: 로그 파일 생성 및 저장
  - CSV 형식으로 저장
  - HTML 형식으로 생성
  - 브라우저에서 자동 오픈

---

### recording/record_actions.py
**역할**: 녹화 실행

```python
from recording.record_actions import record_actions

saved_file = record_actions(duration_s=10, sample_ms=50)
# 10초 동안 마우스/키보드 녹화
# 샘플링: 50ms 간격으로 마우스 움직임 기록
# JSON 파일로 저장 후 경로 반환
# None이면 녹화 취소
```

**함수 목록**:
- `record_actions(duration_s, sample_ms, meta_extra)`: 녹화 실행
  - 마우스 움직임, 클릭, 스크롤 감지
  - 키보드 입력 감지
  - 이벤트를 JSON으로 저장

---

### recording/save_events.py
**역할**: 이벤트 저장 및 변환

```python
from recording.save_events import save_events_to_file, migrate_txt_to_json

# 이벤트 저장
events = [
    (0, 'mouse_move', 100, 200),
    (50, 'key_down', 'a'),
    ...
]
saved = save_events_to_file(events)

# TXT를 JSON으로 변환
json_path = migrate_txt_to_json('old_recording.txt')
```

**함수 목록**:
- `save_events_to_file(events, meta)`: 이벤트를 JSON으로 저장
  - 메타 정보 포함
  - 타임스탬프 기록
  - 화면 해상도 저장
- `migrate_txt_to_json(txt_path)`: 레거시 TXT를 JSON으로 변환

---

### playback/playback_engine.py
**역할**: 녹화된 이벤트 재생

```python
from playback.playback_engine import playback_from_file

playback_from_file(
    'recording.json',
    speed=1.0,           # 배속: 0.5 ~ 3.0
    repeat=1,            # 반복 횟수
    app=app_instance,    # UI 업데이트용
    playback_stop_event=event,
    controller=controller,
    mouse_controller=mouse_controller,
    on_worker_finished=callback
)
```

**주요 기능**:
- 파일에서 이벤트 읽기
- 배속 적용
- 반복 재생
- 각 이벤트 타입 처리:
  - `mouse_move`: 마우스 이동
  - `mouse_click`: 마우스 클릭
  - `mouse_scroll`: 마우스 스크롤
  - `string`: 문자열 입력
  - `key_down/key_up`: 키 입력
  - `imgcheck`: 이미지 검증
- 로그 생성 및 저장
- 브라우저에서 로그 열기

**주의**: `_suppress_hotkey` 플래그를 통해 ESC 키가 매크로 중단으로 인식되지 않도록 함

---

### ui/hotkey.py
**역할**: 글로벌 핫키 처리

```python
from ui.hotkey import on_press_global, create_listener

# 핫키 리스너 생성
listener = create_listener()
# 글로벌 F5, F6, F7, ESC 키 감지

# 핫키 누름 이벤트 처리
on_press_global(key)
# F5: 반복 매크로 토글
# F6: 스크립트 재생 토글
# F7: 녹화 시작
# ESC: 즉시 중지
```

**함수 목록**:
- `on_press_global(key)`: 글로벌 키 누름 이벤트 처리
- `create_listener()`: 글로벌 핫키 리스너 생성

---

### workers/simple_macro.py
**역할**: 반복 매크로 워커

```python
from workers.simple_macro import worker, show_exit_message

# 워커 스레드에서 실행
worker(
    duration_s=10,         # 실행 시간 (초)
    interval_ms=100,       # 키 입력 간격 (밀리초)
    key_val='a',           # 입력할 키
    controller=controller,
    stop_event=stop_event,
    playback_stop_event=playback_stop_event,
    on_finished_callback=callback
)

# 종료 메시지 표시
show_exit_message()
# MB_SYSTEMMODAL 플래그로 항상 위에 표시
```

**함수 목록**:
- `worker(duration_s, interval_ms, key_val, ...)`: 반복 매크로 실행
  - 설정 시간 동안 반복 입력
  - ESC나 stop_event로 중지 가능
  - 완료 후 콜백 호출
- `show_exit_message()`: 종료 알림 표시
  - Windows API를 사용해 항상 위에 표시

---

## 사용 예시

### 1. 단순 매크로 실행 (Python)
```python
from workers.simple_macro import worker
from pynput.keyboard import Controller
import threading

controller = Controller()
stop_event = threading.Event()

# 10초 동안 'a' 키를 100ms 간격으로 입력
worker(10, 100, 'a', controller, stop_event, None, None)
```

### 2. 녹화 실행 (Python)
```python
from recording.record_actions import record_actions

# 10초 동안 녹화, 50ms 샘플링
saved_file = record_actions(duration_s=10, sample_ms=50)
if saved_file:
    print(f"저장됨: {saved_file}")
else:
    print("녹화 취소")
```

### 3. 재생 실행 (Python)
```python
from playback.playback_engine import playback_from_file
from pynput.keyboard import Controller
from pynput.mouse import Controller as MouseController
import threading

controller = Controller()
mouse_controller = MouseController()
playback_stop_event = threading.Event()

playback_from_file(
    'recording.json',
    speed=1.0,
    repeat=1,
    app=None,
    playback_stop_event=playback_stop_event,
    controller=controller,
    mouse_controller=mouse_controller,
    on_worker_finished=None
)
```

### 4. 이미지 체크 (Python)
```python
from utils.imgcheck_utils import perform_imgcheck

result = perform_imgcheck('img/template.png')
print(result['result'])  # 'PASS' 또는 'FAIL'
print(result['match_score'])  # 0.0 ~ 1.0
```

### 5. GUI 애플리케이션
```bash
# moveRecord.py 직접 실행
python moveRecord.py

# 또는 run.py 를 통해 실행
python run.py
```

---

## 개발 팁

### 1. 새로운 유틸 함수 추가
```python
# utils/new_utils.py 생성
def my_new_function():
    """새로운 유틸 함수"""
    pass

# moveRecord.py에서 임포트
from utils.new_utils import my_new_function

# 또는 다른 모듈에서 임포트
from utils.new_utils import my_new_function
```

### 2. 새로운 이벤트 타입 처리
```python
# playback/playback_engine.py에서
elif event_type == 'custom_event':
    # 사용자 정의 이벤트 처리
    _handle_custom_event(params)
```

### 3. 로깅 추가
```python
# 모듈의 시작
import logging

logger = logging.getLogger(__name__)

# 로깅
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("에러 메시지")
```

### 4. 타입 힌팅 추가
```python
from typing import Optional, Dict, List

def my_function(
    name: str,
    count: int,
    items: Optional[List[str]] = None
) -> Dict[str, int]:
    """함수 설명
    
    Args:
        name: 이름
        count: 개수
        items: 항목 리스트
    
    Returns:
        결과 딕셔너리
    """
    return {}
```

### 5. 에러 처리
```python
try:
    result = perform_imgcheck('template.png')
except FileNotFoundError:
    logger.error("이미지 파일을 찾을 수 없습니다.")
except Exception as e:
    logger.error(f"예기치 않은 오류: {e}")
```

---

## 트러블슈팅

### 문제 1: "ModuleNotFoundError: No module named 'config'"
**원인**: 프로젝트 루트에서 실행하지 않음

**해결**:
```bash
cd script/moverecord
python moveRecord.py
```

### 문제 2: "ModuleNotFoundError: No module named 'imgCheck'"
**원인**: sys.path에 imgcheck 경로가 없음

**해결**: utils/imgcheck_utils.py에서 자동 처리됨
```python
# 동적 경로 추가
sys.path.insert(0, str(IMGCHECK_DIR))
```

### 문제 3: 핫키가 작동하지 않음
**원인**: 
- 글로벌 핫키 리스너가 시작되지 않음
- 다른 프로그램이 핫키를 가로챔

**해결**:
```python
# moveRecord.py에서 리스너 시작 확인
from ui.hotkey import create_listener
listener = create_listener()
# 또는 on_press_global이 등록되었는지 확인
```

### 문제 4: 재생 후 ESC가 매크로를 중단함
**원인**: `playback_engine._suppress_hotkey` 플래그가 제대로 관리되지 않음

**해결**: playback_engine.py의 finally 블록에서 플래그 초기화 확인
```python
finally:
    playback_engine._suppress_hotkey = False
```

### 문제 5: 매크로가 두 번 실행되지 않음
**원인**: threading event가 초기화되지 않음

**해결**: _finish_ui_update()에서 event 초기화 확인
```python
stop_event.clear()
playback_stop_event.clear()
```

### 문제 6: JSON 파일을 열 수 없음
**원인**: 파일 경로 또는 인코딩 문제

**해결**:
```python
import json

try:
    with open('recording.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except json.JSONDecodeError:
    print("JSON 파일이 손상되었습니다.")
except FileNotFoundError:
    print("파일을 찾을 수 없습니다.")
```

---

## 다음 단계

### 우선순위 1 (즉시)
- [ ] 모든 모듈 임포트 테스트
- [ ] 기본 기능 동작 확인
- [ ] 핫키 작동 확인

### 우선순위 2 (단기)
- [ ] 단위 테스트 작성 (pytest)
- [ ] 타입 힌팅 추가
- [ ] 에러 핸들링 개선

### 우선순위 3 (중기)
- [ ] 로깅 모듈 확장
- [ ] 설정 파일 외부화
- [ ] 성능 최적화

### 우선순위 4 (장기)
- [ ] CI/CD 파이프라인
- [ ] API 문서 자동 생성
- [ ] 병렬 처리 지원

---

## 참고 자료

- [ARCHITECTURE.md](ARCHITECTURE.md) - 프로젝트 아키텍처
- [README.md](README.md) - 프로젝트 개요
- 각 모듈의 docstring
- PyNput 문서: https://pynput.readthedocs.io/
- OpenCV 문서: https://docs.opencv.org/

---

**마지막 업데이트**: 2026년 1월 12일
**리팩토링 완료**: 100%
