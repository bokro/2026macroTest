"""전역 상수 및 설정"""
from pynput.keyboard import Key

# recorder version for metadata
RECORDER_VERSION = '1.0'

# 핫키설정
HOTKEY = 'f5'
PLAY_HOTKEY = 'f6'
RECORD_START_HOTKEY = 'f7'
RECORD_STOP_HOTKEY = 'esc'

# suppress handling of global hotkeys while synthetic (script) inputs are sent
SUPPRESS_HOTKEY = False

# 이번 테스트용 임시 비활성화 플래그
DID_DISABLE_UNDO_REDO_ONCE = False



# 키 파싱: 단일 문자 또는 특수키 이름
SPECIAL_KEYS = {
    'enter': Key.enter,
    'esc': Key.esc,
    'space': Key.space,
    'tab': Key.tab,
    'backspace': Key.backspace,
    'shift': Key.shift,
    'ctrl': Key.ctrl,
    'alt': Key.alt,
}
