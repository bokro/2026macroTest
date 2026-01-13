"""재생 엔진 - 녹화된 이벤트 재생"""
import time
import json
import threading
import traceback
from datetime import datetime
from pynput.keyboard import Key
from pynput.mouse import Button as MouseButton
from utils.file_utils import collect_pc_meta
from utils.imgcheck_utils import perform_imgcheck
from utils.logging import write_test_log


# 재생 중 글로벌 핫키 억제를 위한 플래그
_suppress_hotkey = False


def playback_from_file(fpath, speed=1.0, repeat=1, app=None, playback_stop_event=None, 
                      controller=None, mouse_controller=None, on_worker_finished=None):
    """파일에서 이벤트를 재생"""
    global _suppress_hotkey
    
    target_meta = {}
    if app and hasattr(app, '_build_active_window_meta'):
        try:
            target_meta = app._build_active_window_meta()
        except Exception:
            target_meta = {}
    
    log_data = {
        'script_path': fpath,
        'started_at': datetime.now(),
        'pc_meta': collect_pc_meta(),
        'imgcheck_results': [],
        'status': 'running',
        'target_meta': target_meta,
    }
    
    events = []
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # support two formats: top-level list or {'meta':..., 'events':[...]}
            if isinstance(data, dict):
                raw_events = data.get('events', [])
            else:
                raw_events = data
            for ev in raw_events:
                # each ev is dict {'t_ms':..., 'type':..., 'params':[...]} 
                t_ms = int(ev.get('t_ms', 0)) if isinstance(ev, dict) else int(ev[0])
                etype = ev.get('type') if isinstance(ev, dict) else ev[1]
                params = ev.get('params', []) if isinstance(ev, dict) else ev[2:]
                events.append((t_ms, etype, params))
    except Exception as e:
        print('재생 파일 읽기 실패:', e)
        log_data.update({'status': 'error', 'error_message': str(e)})
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        log_data['overall_result'] = 'error'
        from pathlib import Path
        write_test_log(log_data, Path(fpath).parent)
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
                pass
        return
    
    if not events:
        print('재생할 이벤트가 없습니다.')
        log_data.update({'status': 'error', 'error_message': '재생할 이벤트가 없습니다.'})
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        log_data['overall_result'] = 'error'
        from pathlib import Path
        write_test_log(log_data, Path(fpath).parent)
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
                pass
        return
    
    # run playback using absolute scheduling scaled by speed and repeat count
    if playback_stop_event:
        playback_stop_event.clear()
    
    base_total_ms = events[-1][0]
    total_s = (base_total_ms / 1000.0) / float(max(1e-9, float(speed))) * max(1, int(repeat))
    
    if app:
        try:
            app.root.after(0, lambda: app._update_playback_status(0.0, total_s, float(speed)))
        except Exception:
            pass
    
    start_time = time.time()
    try:
        for cycle in range(max(1, int(repeat))):
            cycle_start = start_time + (cycle * (base_total_ms / 1000.0)) / float(max(1e-9, float(speed)))
            for t_ms, etype, params in events:
                if playback_stop_event and playback_stop_event.is_set():
                    break
                target = cycle_start + (t_ms / 1000.0) / float(max(1e-9, float(speed)))
                sleep_time = target - time.time()
                # update UI while waiting
                if sleep_time > 0 and app:
                    try:
                        elapsed = time.time() - start_time
                        app.root.after(0, lambda e=elapsed, t=total_s, s=float(speed): app._update_playback_status(e, t, s))
                    except Exception:
                        pass
                    time.sleep(sleep_time)
                try:
                    # suppress global hotkey handling while injecting synthetic input
                    _suppress_hotkey = True
                    if etype == 'mouse_move':
                        x, y = params
                        if mouse_controller:
                            mouse_controller.position = (int(x), int(y))
                    elif etype == 'mouse_click':
                        btn = params[0]
                        action = params[1]
                        x = int(params[2])
                        y = int(params[3])
                        if mouse_controller:
                            mouse_controller.position = (x, y)
                            btn_obj = MouseButton.left if 'left' in str(btn).lower() else MouseButton.right
                            if action == 'press':
                                mouse_controller.press(btn_obj)
                            else:
                                mouse_controller.release(btn_obj)
                    elif etype == 'mouse_scroll':
                        dx = float(params[0])
                        dy = float(params[1])
                        x = int(params[2])
                        y = int(params[3])
                        if mouse_controller:
                            mouse_controller.position = (x, y)
                            mouse_controller.scroll(int(dx), int(dy))
                    elif etype == 'string':
                        try:
                            text = params[0]
                            if controller:
                                controller.type(str(text))
                        except Exception as e:
                            print('string 입력 중 오류:', e)
                    elif etype == 'key_down':
                        k = params[0]
                        if controller:
                            # special key names like Key.enter
                            if isinstance(k, str) and k.startswith('Key.'):
                                keyname = k.split('.', 1)[1]
                                key_obj = getattr(Key, keyname, None)
                                if key_obj is not None:
                                    controller.press(key_obj)
                            elif isinstance(k, str) and len(k) == 1:
                                controller.press(k)
                            else:
                                # fallback: press first char
                                controller.press(str(k)[0])
                    elif etype == 'key_up':
                        k = params[0]
                        if controller:
                            if isinstance(k, str) and k.startswith('Key.'):
                                keyname = k.split('.', 1)[1]
                                key_obj = getattr(Key, keyname, None)
                                if key_obj is not None:
                                    controller.release(key_obj)
                            elif isinstance(k, str) and len(k) == 1:
                                controller.release(k)
                            else:
                                controller.release(str(k)[0])
                    elif etype == 'imgcheck':
                        img_path = params[0] if params else ''
                        result = {'input_image': img_path, 'passed': False, 'message': ''}
                        if img_path:
                            print(f'[imgcheck] 실행: {img_path}')
                            try:
                                check_result = perform_imgcheck(img_path)
                                if check_result:
                                    result.update(check_result)
                                    print(f'[imgcheck] 결과: {result.get("passed", False)} (score: {result.get("score", "N/A")})')
                                else:
                                    result['message'] = 'imgcheck 함수 실행 실패'
                                    print(f'[imgcheck] 실행 실패: {result["message"]}')
                            except Exception as img_err:
                                result['message'] = f'imgcheck 오류: {str(img_err)}'
                                print(f'[imgcheck] 오류 발생: {img_err}')
                        else:
                            print('[imgcheck] 이미지 경로가 없습니다.')
                            result['message'] = '이미지 경로가 없습니다.'
                        result['elapsed_ms'] = int((time.time() - start_time) * 1000)
                        log_data['imgcheck_results'].append(result)
                        print(f'[imgcheck] 결과 저장 완료: {result}')
                except Exception as e:
                    log_data['status'] = 'error'
                    log_data['error_message'] = str(e)
                    print('재생 중 예외:', e)
                    traceback.print_exc()
                finally:
                    _suppress_hotkey = False
                # update UI after event
                if app:
                    try:
                        elapsed = time.time() - start_time
                        app.root.after(0, lambda e=elapsed, t=total_s, s=float(speed): app._update_playback_status(e, t, s))
                    except Exception:
                        pass
            if playback_stop_event and playback_stop_event.is_set():
                break
    finally:
        log_data['ended_at'] = datetime.now()
        log_data['duration_s'] = (log_data['ended_at'] - log_data['started_at']).total_seconds()
        
        # 상태 판단 로직 개선
        is_stopped = playback_stop_event and playback_stop_event.is_set()
        
        if log_data.get('status') == 'running':
            log_data['status'] = 'cancelled' if is_stopped else 'completed'
        
        print(f"[재생 종료] status={log_data['status']}, is_stopped={is_stopped}, imgcheck_count={len(log_data.get('imgcheck_results', []))}")
        
        if log_data['status'] == 'completed':
            imgcheck_results = log_data.get('imgcheck_results', [])
            if imgcheck_results:
                failed = [r for r in imgcheck_results if not r.get('passed', False)]
                if failed:
                    log_data['overall_result'] = 'fail'
                    print(f"[재생 종료] imgcheck 실패: {len(failed)}/{len(imgcheck_results)}")
                else:
                    log_data['overall_result'] = 'pass'
                    print(f"[재생 종료] 모든 imgcheck 통과: {len(imgcheck_results)}")
            else:
                log_data['overall_result'] = 'pass'
                print("[재생 종료] imgcheck 없음, pass 처리")
        elif log_data['status'] == 'cancelled':
            log_data['overall_result'] = 'cancelled'
            print("[재생 종료] 사용자가 취소")
        else:
            log_data.setdefault('overall_result', 'error')
            print(f"[재생 종료] 오류 발생: {log_data.get('error_message', 'Unknown')}")

        from pathlib import Path
        html_path, csv_path = write_test_log(log_data, Path(fpath).parent)
        if app:
            try:
                app.root.after(0, lambda p=html_path: app.status.config(text=f'로그 생성: {p}'))
            except Exception:
                pass
        print('재생 종료')
        # 정리 및 UI 갱신 - playback_thread는 moveRecord.py에서 관리
        if callable(on_worker_finished):
            try:
                on_worker_finished()
            except Exception:
                pass
