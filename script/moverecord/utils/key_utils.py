"""키 입력 관련 유틸 함수"""
from config.constants import SPECIAL_KEYS


def key_to_name(key):
    """키 객체를 문자열 이름으로 변환"""
    try:
        # KeyCode (문자)인 경우
        if hasattr(key, 'char') and key.char is not None:
            return key.char.lower()
    except Exception:
        pass
    try:
        # Key enum (예: Key.f5, Key.enter)
        return key.name
    except Exception:
        return str(key).lower().strip("'\"")


def parse_hotkey_str(s: str):
    """핫키 문자열 파싱"""
    k = (s or '').strip().lower()
    if not k:
        return None
    if k in SPECIAL_KEYS:
        return k
    if k.startswith('f') and k[1:].isdigit():
        return k
    if len(k) == 1:
        return k
    return k


def parse_key(key_str: str):
    """키 문자열을 pynput Key 객체 또는 마우스 동작으로 변환
    
    Returns:
        키보드 키, 또는 마우스 동작을 나타내는 딕셔너리
        예: {'type': 'mouse', 'action': 'left_click'}
    """
    k = key_str.strip().lower()
    if not k:
        return None
    
    # 마우스 동작 파싱
    mouse_actions = {
        '좌클릭': {'type': 'mouse', 'action': 'left_click'},
        'left_click': {'type': 'mouse', 'action': 'left_click'},
        'lclick': {'type': 'mouse', 'action': 'left_click'},
        '우클릭': {'type': 'mouse', 'action': 'right_click'},
        'right_click': {'type': 'mouse', 'action': 'right_click'},
        'rclick': {'type': 'mouse', 'action': 'right_click'},
        '휠클릭': {'type': 'mouse', 'action': 'middle_click'},
        'middle_click': {'type': 'mouse', 'action': 'middle_click'},
        'mclick': {'type': 'mouse', 'action': 'middle_click'},
        '휠업': {'type': 'mouse', 'action': 'scroll_up'},
        'wheel_up': {'type': 'mouse', 'action': 'scroll_up'},
        'scroll_up': {'type': 'mouse', 'action': 'scroll_up'},
        '휠다운': {'type': 'mouse', 'action': 'scroll_down'},
        'wheel_down': {'type': 'mouse', 'action': 'scroll_down'},
        'scroll_down': {'type': 'mouse', 'action': 'scroll_down'},
    }
    
    if k in mouse_actions:
        return mouse_actions[k]
    
    # 키보드 키 파싱
    if k in SPECIAL_KEYS:
        return SPECIAL_KEYS[k]
    # 첫 글자만 사용할 경우 문자로 입력
    if len(k) == 1:
        return k
    # fallback: try first character
    return k[0]
