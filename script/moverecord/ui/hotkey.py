"""전역 핫키 처리"""
from pynput.keyboard import Listener
from utils.key_utils import key_to_name


def on_press_global(key):
    """글로벌 키 핸들러"""
    try:
        import script.moverecord.moveRecord as main_module
        name = key_to_name(key)
        
        # ignore global handling when synthetic events are being injected
        if main_module.SUPPRESS_HOTKEY:
            return
        
        # record stop hotkey (default ESC)
        rstop = main_module.RECORD_STOP_HOTKEY
        if rstop and name == rstop:
            print("녹화 중지/ESC 감지: 즉시 중지합니다.")
            main_module.stop_event.set()
            main_module.playback_stop_event.set()
            return
        
        hot = main_module.HOTKEY
        if hot and name == hot:
            print(f"{hot.upper()} 감지: 시작 시도 (글로벌)")
            app = main_module.app_instance
            if app:
                try:
                    # main thread에서 안전하게 start 호출
                    app.root.after(0, app.hotkey_start)
                except Exception:
                    pass
        
        play_hot = main_module.PLAY_HOTKEY
        if play_hot and name == play_hot:
            print(f"{play_hot.upper()} 감지: 재생 토글 (글로벌)")
            app = main_module.app_instance
            if app:
                try:
                    app.root.after(0, app.play_hotkey_toggle)
                except Exception:
                    pass
        
        rstart = main_module.RECORD_START_HOTKEY
        if rstart and name == rstart:
            print(f"{rstart.upper()} 감지: 녹화 시작 (글로벌)")
            app = main_module.app_instance
            if app:
                try:
                    app.root.after(0, app.start_recording)
                except Exception:
                    pass
    except Exception:
        pass


def create_global_hotkey_listener():
    """글로벌 핫키 리스너 생성"""
    return Listener(on_press=on_press_global)
