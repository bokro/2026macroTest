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
    """키 문자열을 pynput Key 객체로 변환"""
    k = key_str.strip().lower()
    if not k:
        return None
    if k in SPECIAL_KEYS:
        return SPECIAL_KEYS[k]
    # 첫 글자만 사용할 경우 문자로 입력
    if len(k) == 1:
        return k
    # fallback: try first character
    return k[0]
