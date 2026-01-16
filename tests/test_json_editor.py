import json
from pathlib import Path

from tests.stubs import StubEntry

from script.moverecord.ui.json_editor import JsonEditor


class DummyEditor(JsonEditor):
    def __init__(self):
        # 루트/상태는 사용하지 않도록 최소 속성만 제공
        self.root = type("_R", (), {"winfo_screenwidth": lambda s: 1920, "winfo_screenheight": lambda s: 1080})()
        # 메타 항목
        self.meta_version = StubEntry("")
        self.meta_timestamp = StubEntry("2000-01-01T00:00:00Z")
        self.meta_width = StubEntry("1920")
        self.meta_height = StubEntry("1080")
        self.meta_active_title = StubEntry("")
        self.meta_active_pid = StubEntry("")
        self.meta_active_process = StubEntry("")
        # 에디터 행/컨트롤
        self.editor_rows = []
        self.btn_editor_save = type("_B", (), {"config": lambda s, **k: None})()
        self.status = type("_S", (), {"config": lambda s, **k: None})()

    # RecordingPlay 믹신에 있는 메타 기본값 함수의 테스트용 대체 구현
    def _recording_meta_defaults(self):
        return {
            'recorder_version': 'test',
            'timestamp': '2000-01-01T00:00:00Z',
            'screen_width': 1920,
            'screen_height': 1080,
        }


def test_json_editor_save(monkeypatch, tmp_artifacts):
    app = DummyEditor()

    # 행 2개 구성
    app.editor_rows = [
        {"t": StubEntry("0"), "type": StubEntry("string"), "params": StubEntry('["hello"]')},
        {"t": StubEntry("100"), "type": StubEntry("key_down"), "params": StubEntry('["Key.enter"]')},
    ]

    out_path = tmp_artifacts / "edited_recording.json"

    # 저장 파일 대화상자 모킹
    def _fake_asksaveasfilename(**_kwargs):
        return str(out_path)
    monkeypatch.setattr('script.moverecord.ui.json_editor.filedialog.asksaveasfilename', _fake_asksaveasfilename)

    app.save_edited_script()

    assert out_path.exists()

    data = json.loads(out_path.read_text(encoding='utf-8'))
    assert isinstance(data, dict)
    assert 'meta' in data and 'events' in data
    # 이벤트 카운트/내용 간단 검증
    assert len(data['events']) == 2
    assert data['events'][0]['type'] == 'string'
