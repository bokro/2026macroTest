"""녹화/재생 관련 Mixin - moveRecord.py의 App 클래스에서 사용"""
import json
import os
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, timezone
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener


def _get_main_module():
    """메인 모듈(moveRecord)의 참조를 가져옴"""
    import sys
    return sys.modules.get('__main__')


class RecordingPlay:
    """
    녹화/재생 관련 메소드를 제공하는 Mixin 클래스
    
    이 클래스를 사용하는 클래스는 다음 속성들을 가지고 있어야 합니다:
    - self.root: tkinter root window
    - self.entry_hotkey, self.entry_playhotkey, self.entry_record_start, self.entry_record_stop: Entry 위젯
    - self.entry_script: 스크립트 파일 경로 Entry
    - self.entry_repeat, self.entry_sample_ms: 반복/샘플링 Entry
    - self.speed_var: 배속 StringVar
    - self.btn_start, self.btn_stop, self.btn_record: 버튼 위젯
    - self.btn_start_script, self.btn_stop_play, self.btn_append_record: 버튼 위젯
    - self.status: 상태 레이블
    - self.play_timer: 재생 타이머 레이블
    - self._hotkeys_prev: 이전 핫키 값 딕셔너리
    """
    
    #============ hotkey 관련 메서드 ============
    def _on_hotkey_change(self):
        raw = self.entry_hotkey.get().strip()
        parsed = self._parse_hotkey_str(raw)
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
        parsed = self._parse_hotkey_str(raw)
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

    # 중복 메소드 - 첫 번째 _on_hotkey_change와 동일
    def _on_hotkey_change_duplicate(self):
        """이 메소드는 253줄에 있던 중복 메소드입니다. 삭제 후보."""
        raw = self.entry_hotkey.get().strip()
        self._set_hotkey_with_check(self.entry_hotkey, raw, 'HOTKEY', 'HOTKEY')

    #============ hotkey 관련 메서드 ============

    def start_playback(self):
        # explicit playback start triggered by '녹화시작' 버튼
        from config.constants import RECORDER_VERSION
        
        script_path = self.entry_script.get().strip() if hasattr(self, 'entry_script') else ''
        if not script_path:
            messagebox.showerror('오류', '재생할 스크립트를 선택하세요.')
            return
        
        main = _get_main_module()
        if main and main.playback_thread is not None:
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
        
        main = _get_main_module()
        if main:
            main.playback_stop_event.clear()
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
        main = _get_main_module()
        if main and main.playback_thread is not None:
            main.playback_stop_event.set()
            main.playback_thread = None
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
        # 전역 변수 초기화 (중요: globals() 사용하여 실제 전역 변수 수정)
        import sys
        # moveRecord 모듈의 전역 변수에 접근
        moverecord_module = sys.modules.get('__main__')
        if moverecord_module:
            moverecord_module.playback_thread = None
            moverecord_module.worker_thread = None
            moverecord_module.stop_event.clear()
            moverecord_module.playback_stop_event.clear()
        
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
        
        print("[LOG] [_finish_ui_update] playback_thread, worker_thread 정리 및 이벤트 초기화 완료")

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

    def _recording_meta_defaults(self):
        """Return meta fields aligned with recording output."""
        from config.constants import RECORDER_VERSION
        
        meta = {
            'recorder_version': RECORDER_VERSION,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'screen_width': None,
            'screen_height': None,
        }
        try:
            meta['screen_width'] = self.root.winfo_screenwidth()
            meta['screen_height'] = self.root.winfo_screenheight()
        except Exception:
            pass
        return meta

    def choose_script(self):
        from recording.save_events import migrate_txt_to_json as _migrate_txt_to_json
        
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
        from recording.record_actions import record_actions
        
        main = _get_main_module()
        
        # disable UI while recording; recording now continues until ESC or stop
        self.btn_record.config(state='disabled')
        self.status.config(text='녹화 중... (ESC로 중지)')
        # ensure stop_event is cleared so recording won't immediately stop
        if main:
            main.stop_event.clear()

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
            try:
                events = record_actions(None, sample_ms, meta_extra=meta_extra)
                err = None
            except Exception as e:
                events = None
                err = e

            def _after_record(evts, error):
                # clear stop_event to reset global stop state after recording
                try:
                    main = _get_main_module()
                    if main:
                        main.stop_event.clear()
                except Exception:
                    pass

                if error:
                    print(f"[LOG] [녹화 에러] {error}")
                    messagebox.showerror('오류', f'녹화 실패: {error}')
                    self.status.config(text='녹화 실패')
                else:
                    print(f"[LOG] [녹화 완료] 이벤트 수: {len(evts) if evts else 0}")
                    saved = None
                    if evts:
                        try:
                            from recording.save_events import save_events_to_file
                            saved = save_events_to_file(evts, default_name='recording.json', meta_extra=meta_extra)
                            print(f"[LOG] [저장 결과] {saved}")
                        except Exception as e2:
                            print(f"[LOG] [저장 실패] {e2}")
                            messagebox.showerror('오류', f'녹화 저장 실패: {e2}')
                    else:
                        print("[LOG] [녹화] 이벤트가 없습니다")
                    
                    if saved:
                        self.status.config(text=f'녹화 저장: {saved}')
                    else:
                        self.status.config(text='녹화 취소')

                # re-enable record button
                self.btn_record.config(state='normal')
                # refresh inputs/buttons
                self.validate_inputs()

            # UI 업데이트 및 저장은 메인 스레드에서 실행
            self.root.after(0, lambda evts=events, error=err: _after_record(evts, error))
        t = threading.Thread(target=_rec, daemon=True)
        t.start()

    # 선택된 스크립트 파일에 이어서 녹화
    def start_append_recording(self):
        main = _get_main_module()
        
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
        if main:
            main.stop_event.clear()

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
                main = _get_main_module()
                if main:
                    main.stop_event.clear()
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
        from config.constants import RECORDER_VERSION
        
        main = _get_main_module()
        if not main:
            return None
        
        if main.recording:
            return None
        
        main.recording = True
        main.record_events = []
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
            main.record_events.append((now, 'mouse_move', x, y))

        def on_click(x, y, button, pressed):
            main.record_events.append((_now_ms(), 'mouse_click', str(button), 'press' if pressed else 'release', x, y))

        def on_scroll(x, y, dx, dy):
            main.record_events.append((_now_ms(), 'mouse_scroll', dx, dy, x, y))

        def on_press(k):
            try:
                ch = k.char
            except Exception:
                ch = str(k)
            main.record_events.append((_now_ms(), 'key_down', ch))

        def on_release(k):
            try:
                ch = k.char
            except Exception:
                ch = str(k)
            main.record_events.append((_now_ms(), 'key_up', ch))

        # start listeners
        m_listener = MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        k_listener = Listener(on_press=on_press, on_release=on_release)
        m_listener.start()
        k_listener.start()

        # wait until stop_event is set
        while not main.stop_event.is_set():
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

        main.recording = False
        
        # 녹화 취소 체크
        if not main.record_events:
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
        for ev in main.record_events:
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
        from playback.playback_engine import playback_from_file
        
        main = _get_main_module()
        if not main:
            return
        
        main.playback_thread = threading.Thread(
            target=playback_from_file, 
            args=(fpath, speed, repeat),
            kwargs={
                'app': self,
                'playback_stop_event': main.playback_stop_event,
                'controller': main.controller,
                'mouse_controller': main.mouse_controller,
                'on_worker_finished': main.on_worker_finished
            },
            daemon=True
        )
        main.playback_thread.start()

    def _parse_hotkey_str(self, raw):
        """핫키 문자열 파싱 - utils.key_utils에서 가져와야 함"""
        from utils.key_utils import parse_hotkey_str
        return parse_hotkey_str(raw)
