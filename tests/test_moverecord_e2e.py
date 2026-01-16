"""moveRecord 앱의 실제 E2E(End-to-End) 테스트"""
import time
import threading
import tkinter as tk
from pathlib import Path
import json
from pynput.keyboard import Controller as KeyController


def test_moverecord_simple_macro_e2e(test_session_dir):
    """단순 매크로 기능 E2E: GUI 설정 → 실행 → 샌드박스에서 입력 확인"""
    from script.moverecord.moveRecord import App
    
    result = {"sandbox_text": "", "app_closed": False, "sandbox_closed": False}
    app_instance = None
    
    def run_moverecord_app():
        nonlocal app_instance
        root = tk.Tk()
        app_instance = App(root)
        
        # 프로그래밍 방식으로 값 설정
        app_instance.entry_duration.delete(0, tk.END)
        app_instance.entry_duration.insert(0, "0.5")  # 0.5초만 실행
        app_instance.entry_key.delete(0, tk.END)
        app_instance.entry_key.insert(0, "a")
        app_instance.entry_interval.delete(0, tk.END)
        app_instance.entry_interval.insert(0, "50")  # 50ms 간격
        
        # 입력 검증 후 시작 버튼 활성화
        app_instance.validate_inputs()
        
        # 0.3초 후 시작 버튼 클릭 시뮬레이션
        def trigger_start():
            if app_instance.btn_start['state'] == 'normal':
                app_instance.start()
        root.after(300, trigger_start)
        
        # 2초 후 앱 종료
        def close_app():
            result["app_closed"] = True
            try:
                root.destroy()
            except:
                pass
        root.after(2000, close_app)
        
        root.mainloop()
    
    def run_sandbox():
        """입력을 받을 샌드박스 텍스트 박스"""
        sandbox = tk.Tk()
        sandbox.title("Macro Test Sandbox")
        sandbox.geometry("400x200")
        sandbox.attributes('-topmost', True)
        
        text_widget = tk.Text(sandbox, width=40, height=8)
        text_widget.pack(pady=20)
        text_widget.focus_set()
        
        def close_sandbox():
            result["sandbox_text"] = text_widget.get("1.0", "end-1c")
            result["sandbox_closed"] = True
            try:
                sandbox.destroy()
            except:
                pass
        
        # 2초 후 샌드박스 종료
        sandbox.after(2000, close_sandbox)
        sandbox.mainloop()
    
    # 백그라운드에서 moveRecord 앱 실행
    app_thread = threading.Thread(target=run_moverecord_app, daemon=True)
    app_thread.start()
    time.sleep(0.2)
    
    # 백그라운드에서 샌드박스 실행
    sandbox_thread = threading.Thread(target=run_sandbox, daemon=True)
    sandbox_thread.start()
    
    # 스레드 종료 대기
    app_thread.join(timeout=3.0)
    sandbox_thread.join(timeout=3.0)
    
    # 검증: 샌드박스에 'a'가 여러 번 입력되었는지
    assert result["sandbox_closed"], "샌드박스가 정상 종료되지 않음"
    assert result["app_closed"], "moveRecord 앱이 정상 종료되지 않음"
    # 0.5초 동안 50ms 간격이면 약 10회 입력
    assert result["sandbox_text"].count("a") >= 5, f"Expected multiple 'a' inputs, got: '{result['sandbox_text']}'"


def test_moverecord_record_and_playback_e2e(test_session_dir, monkeypatch):
    """녹화 → 저장 → 재생 E2E 워크플로우"""
    from script.moverecord.moveRecord import App
    
    result = {
        "recorded": False,
        "saved_path": None,
        "playback_text": "",
        "app_closed": False,
        "sandbox_closed": False
    }
    app_instance = None
    saved_json_path = test_session_dir / "artifacts" / "e2e_recording.json"
    
    # 파일 대화상자 모킹 (저장 경로 고정)
    def fake_asksaveasfilename(**kwargs):
        return str(saved_json_path)
    monkeypatch.setattr('script.moverecord.recording.save_events.filedialog.asksaveasfilename', fake_asksaveasfilename)
    
    def run_moverecord_app():
        nonlocal app_instance
        root = tk.Tk()
        app_instance = App(root)
        
        # 1단계: 녹화 시작 (0.2초 후)
        def start_recording():
            print("[E2E] 녹화 시작")
            app_instance.start_recording()
        root.after(200, start_recording)
        
        # 2단계: 샘플 입력 발생 (0.5초 후)
        def generate_input():
            print("[E2E] 입력 발생")
            kbd = KeyController()
            for char in "test":
                kbd.press(char)
                kbd.release(char)
                time.sleep(0.05)
        root.after(500, lambda: threading.Thread(target=generate_input, daemon=True).start())
        
        # 3단계: 녹화 중지 (1초 후 - ESC 시뮬레이션)
        def stop_recording():
            print("[E2E] 녹화 중지")
            import sys
            main = sys.modules.get('__main__')
            if main:
                main.stop_event.set()
            time.sleep(0.3)  # 저장 처리 대기
            if saved_json_path.exists():
                result["recorded"] = True
                result["saved_path"] = str(saved_json_path)
                print(f"[E2E] 녹화 저장 완료: {saved_json_path}")
        root.after(1000, lambda: threading.Thread(target=stop_recording, daemon=True).start())
        
        # 4단계: 재생 설정 및 실행 (1.5초 후)
        def setup_and_play():
            if result["recorded"]:
                print("[E2E] 재생 설정")
                app_instance.entry_script.delete(0, tk.END)
                app_instance.entry_script.insert(0, str(saved_json_path))
                app_instance.validate_inputs()
                time.sleep(0.1)
                print("[E2E] 재생 시작")
                app_instance.start_playback()
        root.after(1500, setup_and_play)
        
        # 5단계: 앱 종료 (3초 후)
        def close_app():
            result["app_closed"] = True
            try:
                root.destroy()
            except:
                pass
        root.after(3000, close_app)
        
        root.mainloop()
    
    def run_sandbox():
        """재생 입력을 받을 샌드박스"""
        sandbox = tk.Tk()
        sandbox.title("Playback Test Sandbox")
        sandbox.geometry("400x200")
        sandbox.attributes('-topmost', True)
        
        text_widget = tk.Text(sandbox, width=40, height=8)
        text_widget.pack(pady=20)
        text_widget.focus_set()
        
        def close_sandbox():
            result["playback_text"] = text_widget.get("1.0", "end-1c")
            result["sandbox_closed"] = True
            try:
                sandbox.destroy()
            except:
                pass
        
        sandbox.after(3000, close_sandbox)
        sandbox.mainloop()
    
    # 백그라운드에서 moveRecord 앱 실행
    app_thread = threading.Thread(target=run_moverecord_app, daemon=True)
    app_thread.start()
    time.sleep(0.3)
    
    # 백그라운드에서 샌드박스 실행
    sandbox_thread = threading.Thread(target=run_sandbox, daemon=True)
    sandbox_thread.start()
    
    # 스레드 종료 대기
    app_thread.join(timeout=4.0)
    sandbox_thread.join(timeout=4.0)
    
    # 검증
    assert result["app_closed"], "moveRecord 앱이 정상 종료되지 않음"
    assert result["sandbox_closed"], "샌드박스가 정상 종료되지 않음"
    assert result["recorded"], "녹화가 완료되지 않음"
    assert saved_json_path.exists(), f"녹화 파일이 생성되지 않음: {saved_json_path}"
    
    # JSON 파일 내용 검증
    with open(saved_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert 'events' in data, "JSON에 events 필드가 없음"
        assert len(data['events']) > 0, "녹화된 이벤트가 없음"
        print(f"[E2E] 녹화된 이벤트 수: {len(data['events'])}")
    
    # 재생 결과 검증 (샌드박스에 입력이 반영되었는지)
    # Note: 타이밍 이슈로 일부 문자만 입력될 수 있음
    assert len(result["playback_text"]) > 0, f"재생으로 인한 입력이 감지되지 않음"
    print(f"[E2E] 재생 입력 결과: '{result['playback_text']}'")


def test_moverecord_json_editor_e2e(test_session_dir, monkeypatch):
    """JSON 편집기 E2E: 파일 로드 → 편집 → 저장"""
    from script.moverecord.moveRecord import App
    
    result = {"saved": False, "app_closed": False}
    app_instance = None
    
    # 테스트용 JSON 파일 준비
    input_json = test_session_dir / "artifacts" / "editor_input.json"
    output_json = test_session_dir / "artifacts" / "editor_output.json"
    
    # artifacts 디렉터리 생성
    input_json.parent.mkdir(parents=True, exist_ok=True)
    
    test_data = {
        "meta": {"recorder_version": "test"},
        "events": [
            {"t_ms": 0, "type": "string", "params": ["original"]},
        ]
    }
    input_json.write_text(json.dumps(test_data, ensure_ascii=False), encoding="utf-8")
    
    # 파일 대화상자 모킹
    load_call_count = [0]
    def fake_askopenfilename(**kwargs):
        return str(input_json)
    def fake_asksaveasfilename(**kwargs):
        return str(output_json)
    
    monkeypatch.setattr('script.moverecord.ui.json_editor.filedialog.askopenfilename', fake_askopenfilename)
    monkeypatch.setattr('script.moverecord.ui.json_editor.filedialog.asksaveasfilename', fake_asksaveasfilename)
    
    def run_moverecord_app():
        nonlocal app_instance
        root = tk.Tk()
        app_instance = App(root)
        
        # 1단계: JSON 편집기에 파일 로드 (0.3초 후)
        def load_to_editor():
            print("[E2E] JSON 편집기에 파일 로드")
            app_instance.load_script_to_editor()
        root.after(300, load_to_editor)
        
        # 2단계: 첫 번째 행 수정 (0.6초 후)
        def edit_first_row():
            if app_instance.editor_rows:
                print("[E2E] 첫 번째 행 편집")
                row = app_instance.editor_rows[0]
                # params 수정
                row['params'].delete(0, tk.END)
                row['params'].insert(0, '["modified"]')
        root.after(600, edit_first_row)
        
        # 3단계: 저장 (1초 후)
        def save_editor():
            print("[E2E] 편집기 저장")
            app_instance.save_edited_script()
            # 저장 후 약간의 대기 시간
            time.sleep(0.2)
            if output_json.exists():
                result["saved"] = True
                print(f"[E2E] 저장 완료: {output_json}")
            else:
                print(f"[E2E] 저장 실패: {output_json} 파일이 없음")
        root.after(1000, lambda: threading.Thread(target=save_editor, daemon=True).start())
        
        # 4단계: 앱 종료 (1.5초 후)
        def close_app():
            result["app_closed"] = True
            try:
                root.destroy()
            except:
                pass
        root.after(1500, close_app)
        
        root.mainloop()
    
    # 백그라운드에서 moveRecord 앱 실행
    app_thread = threading.Thread(target=run_moverecord_app, daemon=True)
    app_thread.start()
    app_thread.join(timeout=2.5)
    
    # 검증
    assert result["app_closed"], "moveRecord 앱이 정상 종료되지 않음"
    assert result["saved"], "파일이 저장되지 않음"
    assert output_json.exists(), f"출력 파일이 생성되지 않음: {output_json}"
    
    # 저장된 파일 내용 검증
    with open(output_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert 'events' in data
        assert len(data['events']) == 1
        assert data['events'][0]['params'] == ["modified"], f"수정이 반영되지 않음: {data['events'][0]['params']}"
        print(f"[E2E] 편집 결과 검증 성공: {data['events'][0]['params']}")
