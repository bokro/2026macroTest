import json
from pathlib import Path
import threading

from tests.stubs import StubKeyboardController, StubMouseController, StubApp

from script.moverecord.recording.save_events import save_events_to_file
from script.moverecord.playback.playback_engine import playback_from_file


def test_record_save_and_play(monkeypatch, tmp_artifacts, test_session_dir):
    # 합성 이벤트 (기존 레거시 튜플 형태)
    events = [
        (0, 'mouse_move', 50, 50),
        (10, 'mouse_click', 'Button.left', 'press', 50, 50),
        (20, 'mouse_click', 'Button.left', 'release', 50, 50),
        (30, 'string', 'hello'),
    ]

    out_path = tmp_artifacts / "saved_recording.json"

    # 파일 대화상자 모킹
    def _fake_asksaveasfilename(**_kwargs):
        return str(out_path)
    monkeypatch.setattr('script.moverecord.recording.save_events.filedialog.asksaveasfilename', _fake_asksaveasfilename)

    saved = save_events_to_file(events, default_name='recording.json', meta_extra={'test_flag': True})
    assert saved == str(out_path)
    assert out_path.exists()

    # 저장된 파일 재생
    kbd = StubKeyboardController()
    mouse = StubMouseController()
    app = StubApp()

    playback_from_file(str(out_path), speed=10.0, repeat=1, app=app,
                       playback_stop_event=threading.Event(), controller=kbd, mouse_controller=mouse,
                       on_worker_finished=lambda: None)

    # 재생으로 인한 로그 생성 확인
    # 로그는 세션별 디렉터리에 저장됨
    log_dir = test_session_dir
    assert log_dir.exists()
    assert any(p.suffix == ".html" for p in log_dir.iterdir())
