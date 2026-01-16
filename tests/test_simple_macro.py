import threading

from tests.stubs import StubKeyboardController

from script.moverecord.workers.simple_macro import worker as simple_worker


def test_simple_macro_runs(monkeypatch):
    # show_exit_message 모킹 (팝업 방지)
    monkeypatch.setattr('script.moverecord.workers.simple_macro.show_exit_message', lambda: None)

    controller = StubKeyboardController()
    stop_event = threading.Event()
    playback_stop_event = threading.Event()

    # 매우 짧게 실행: 0.1초 동안 10ms 간격
    simple_worker(duration_s=0.1, interval_ms=10, key_val='a', controller=controller,
                  stop_event=stop_event, playback_stop_event=playback_stop_event,
                  on_finished_callback=lambda: None)

    # 최소 1회 이상 press/release 호출 확인
    assert any(ev[0] == 'press' for ev in controller.events)
    assert any(ev[0] == 'release' for ev in controller.events)
