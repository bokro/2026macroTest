import json
from pathlib import Path
import threading

from tests.stubs import StubKeyboardController, StubMouseController, StubApp

from script.moverecord.playback.playback_engine import playback_from_file


def test_playback_minimal(tmp_artifacts, test_session_dir):
    # 최소 이벤트 JSON 생성
    sample = {
        "meta": {"recorder_version": "test", "timestamp": "2026-01-16T00:00:00Z"},
        "events": [
            {"t_ms": 0, "type": "mouse_move", "params": [100, 100]},
            {"t_ms": 50, "type": "mouse_click", "params": ["Button.left", "press", 100, 100]},
            {"t_ms": 60, "type": "mouse_click", "params": ["Button.left", "release", 100, 100]},
            {"t_ms": 80, "type": "string", "params": ["abc"]},
            {"t_ms": 100, "type": "key_down", "params": ["Key.enter"]},
            {"t_ms": 110, "type": "key_up", "params": ["Key.enter"]},
        ]
    }
    fpath = tmp_artifacts / "sample_recording.json"
    fpath.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    kbd = StubKeyboardController()
    mouse = StubMouseController()
    app = StubApp()
    stop_evt = threading.Event()

    # 빠르게 실행되도록 speed를 높임
    playback_from_file(str(fpath), speed=5.0, repeat=1, app=app,
                       playback_stop_event=stop_evt, controller=kbd, mouse_controller=mouse,
                       on_worker_finished=lambda: None)

    # 호출 검증
    # 키보드: type('abc') 1회, press/release enter 각 1회
    assert ("type", "abc") in kbd.events
    assert any(ev[0] == "press" for ev in kbd.events)
    assert any(ev[0] == "release" for ev in kbd.events)

    # 마우스 이동/클릭 이벤트 기록
    assert any(ev[0] == "move" for ev in mouse.events)
    assert any(ev[0] == "mpress" for ev in mouse.events)
    assert any(ev[0] == "mrelease" for ev in mouse.events)

    # 로그 파일 생성 확인 (HTML/CSV)
    # 로그는 세션별 디렉터리에 저장됨
    log_dir = test_session_dir
    assert log_dir.exists()
    assert any(p.suffix == ".html" for p in log_dir.iterdir())
    assert any(p.suffix == ".csv" for p in log_dir.iterdir())
