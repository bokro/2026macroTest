# 📊 프로젝트 코드 통계

**생성일**: 2026년 1월 16일  
**총 파일**: 37개  
**총 코드 라인**: 4,945줄

---

## 🎯 모듈별 분류

### UI 모듈 (1,132줄)
| 파일 | 줄 수 |
|------|-------|
| [script/moverecord/ui/json_editor.py](script/moverecord/ui/json_editor.py) | 768 |
| [script/moverecord/ui/ui_setup.py](script/moverecord/ui/ui_setup.py) | 332 |
| [script/moverecord/ui/dialogs/mouse_help.py](script/moverecord/ui/dialogs/mouse_help.py) | 29 |
| [script/moverecord/ui/__init__.py](script/moverecord/ui/__init__.py) | 1 |
| [script/moverecord/ui/dialogs/__init__.py](script/moverecord/ui/dialogs/__init__.py) | 1 |

### 녹화/재생 모듈 (1,215줄)
| 파일 | 줄 수 |
|------|-------|
| [script/moverecord/recording/record_play.py](script/moverecord/recording/record_play.py) | 632 |
| [script/moverecord/playback/playback_engine.py](script/moverecord/playback/playback_engine.py) | 257 |
| [script/moverecord/recording/save_events.py](script/moverecord/recording/save_events.py) | 117 |
| [script/moverecord/recording/record_actions.py](script/moverecord/recording/record_actions.py) | 106 |
| [script/moverecord/playback/event_player.py](script/moverecord/playback/event_player.py) | 103 |
| [script/moverecord/recording/__init__.py](script/moverecord/recording/__init__.py) | 1 |
| [script/moverecord/playback/__init__.py](script/moverecord/playback/__init__.py) | 1 |

### 유틸리티 모듈 (479줄)
| 파일 | 줄 수 |
|------|-------|
| [script/moverecord/utils/imgcheck_utils.py](script/moverecord/utils/imgcheck_utils.py) | 146 |
| [script/moverecord/utils/html_utils.py](script/moverecord/utils/html_utils.py) | 136 |
| [script/moverecord/utils/logging.py](script/moverecord/utils/logging.py) | 101 |
| [script/moverecord/utils/file_utils.py](script/moverecord/utils/file_utils.py) | 51 |
| [script/moverecord/utils/key_utils.py](script/moverecord/utils/key_utils.py) | 45 |
| [script/moverecord/utils/__init__.py](script/moverecord/utils/__init__.py) | 1 |

### 테스트 코드 (598줄)
| 파일 | 줄 수 |
|------|-------|
| [tests/test_moverecord_e2e.py](tests/test_moverecord_e2e.py) | 317 |
| [tests/stubs.py](tests/stubs.py) | 64 |
| [tests/test_json_editor.py](tests/test_json_editor.py) | 61 |
| [tests/test_playback_basic.py](tests/test_playback_basic.py) | 52 |
| [tests/test_record_save_play.py](tests/test_record_save_play.py) | 44 |
| [tests/conftest.py](tests/conftest.py) | 37 |
| [tests/test_simple_macro.py](tests/test_simple_macro.py) | 23 |

### 메인 앱 & 워커 (1,521줄)
| 파일 | 줄 수 |
|------|-------|
| [script/imgcheck/imgCheck.py](script/imgcheck/imgCheck.py) | 609 |
| [script/moverecord/moveRecord.py](script/moverecord/moveRecord.py) | 434 |
| [python.py](python.py) | 336 |
| [script/moverecord/workers/simple_macro.py](script/moverecord/workers/simple_macro.py) | 77 |
| [script/moverecord/config/constants.py](script/moverecord/config/constants.py) | 31 |
| [script/moverecord/config/__init__.py](script/moverecord/config/__init__.py) | 22 |
| [run.py](run.py) | 5 |
| [script/imgcheck/__init__.py](script/imgcheck/__init__.py) | 1 |
| [script/moverecord/workers/__init__.py](script/moverecord/workers/__init__.py) | 1 |
| [script/__init__.py](script/__init__.py) | 1 |
| [script/moverecord/__init__.py](script/moverecord/__init__.py) | 1 |
| [__init__.py](__init__.py) | 1 |

---

## 📈 구성 비율

```
메인 앱 & 워커:  1,521줄 (30.7%)
녹화/재생 모듈:  1,215줄 (24.6%)
UI 모듈:        1,132줄 (22.9%)
테스트 코드:      598줄 (12.1%)
유틸리티:        479줄  (9.7%)
```

---

## 🔝 TOP 10 파일 (코드 라인 기준)

1. **json_editor.py** - 768줄 (JSON 편집기 UI)
2. **record_play.py** - 632줄 (녹화/재생 믹스인)
3. **imgCheck.py** - 609줄 (이미지 매칭 기능)
4. **moveRecord.py** - 434줄 (메인 애플리케이션)
5. **python.py** - 336줄 (레거시 코드)
6. **ui_setup.py** - 332줄 (UI 초기화 및 설정)
7. **test_moverecord_e2e.py** - 317줄 (E2E 테스트)
8. **playback_engine.py** - 257줄 (재생 엔진)
9. **imgcheck_utils.py** - 146줄 (이미지 체크 유틸리티)
10. **html_utils.py** - 136줄 (HTML 생성 유틸리티)

---

## 📝 테스트 커버리지

- **단위/통합 테스트**: 4개 (240줄)
  - `test_playback_basic.py`: 재생 엔진 기본 테스트
  - `test_record_save_play.py`: 녹화→저장→재생 워크플로우
  - `test_json_editor.py`: JSON 편집기 저장 기능
  - `test_simple_macro.py`: 단순 매크로 동작

- **E2E 테스트**: 1개 (317줄)
  - `test_moverecord_e2e.py`: moveRecord 앱 전체 시나리오

- **테스트 인프라**: 101줄
  - `conftest.py`: pytest 픽스처 및 설정
  - `stubs.py`: 스텁 컨트롤러

**테스트 실행 시간**: ~2-8초  
**테스트 통과율**: 5/5 (100%)

---

## 🏗️ 아키텍처 특징

- **모듈화 설계**: UI, 녹화, 재생, 유틸리티가 명확히 분리
- **믹스인 패턴**: `RecordingPlay`, `JsonEditor` 믹스인으로 기능 조합
- **이벤트 기반**: 키보드/마우스 이벤트를 JSON 형태로 저장 및 재생
- **테스트 자동화**: pytest 기반 단위/통합/E2E 테스트 구축
- **로깅 시스템**: HTML/CSV 형식의 상세한 실행 로그 생성

---

## 📚 주요 의존성

- **pynput**: 키보드/마우스 제어
- **tkinter**: GUI 프레임워크
- **opencv-python** (cv2): 이미지 매칭
- **numpy**: 이미지 처리
- **pytest**: 테스트 프레임워크

---

*이 문서는 자동 생성되었습니다.*
