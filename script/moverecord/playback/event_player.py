"""이벤트 재생 엔진"""
import time
import json
from datetime import datetime
from pynput.keyboard import Controller as KeyController, Key
from pynput.mouse import Controller as MouseController, Button as MouseButton

try:
    import script.moverecord.moveRecord as main_module
except ImportError:
    main_module = None


def play_event(controller, mouse_controller, etype, params):
    """개별 이벤트 재생"""
    if etype == 'mouse_move':
        x, y = params
        mouse_controller.position = (int(x), int(y))
    elif etype == 'mouse_click':
        btn = params[0]
        action = params[1]
        x = int(params[2])
        y = int(params[3])
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
        mouse_controller.position = (x, y)
        mouse_controller.scroll(int(dx), int(dy))
    elif etype == 'string':
        try:
            text = params[0]
            controller.type(str(text))
        except Exception as e:
            print('string 입력 중 오류:', e)
    elif etype == 'key_down':
        k = params[0]
        # special key names like Key.enter
        if isinstance(k, str) and k.startswith('Key.'):
            keyname = k.split('.',1)[1]
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
        if isinstance(k, str) and k.startswith('Key.'):
            keyname = k.split('.',1)[1]
            key_obj = getattr(Key, keyname, None)
            if key_obj is not None:
                controller.release(key_obj)
        elif isinstance(k, str) and len(k) == 1:
            controller.release(k)
        else:
            controller.release(str(k)[0])
    elif etype == 'imgcheck':
        img_path = params[0] if params else ''
        result = {'input_image': img_path, 'passed': False}
        if img_path:
            print(f'imgcheck 실행: {img_path}')
            from utils.imgcheck_utils import perform_imgcheck
            result = perform_imgcheck(img_path) or result
        else:
            print('imgcheck: 이미지 경로가 없습니다.')
            result['message'] = '이미지 경로가 없습니다.'
        return result
    
    return None


def playback_from_file(fpath, speed=1.0, repeat=1):
    """파일에서 이벤트를 읽어서 재생"""
    from utils.file_utils import collect_pc_meta
    from utils.html_utils import generate_html
    import csv
    from pathlib import Path
    
    playback_stop_event = None
    playback_thread = None
    on_worker_finished = None
    
    if main_module:
        try:
            playback_stop_event = main_module.playback_stop_event
            playback_thread = main_module.playback_thread
            on_worker_finished = main_module.on_worker_finished
        except Exception:
            pass
    
    # 메인 로직은 moveRecord.py의 playback_from_file에서 처리
    # 이 파일은 이벤트 재생만 담당
    pass
