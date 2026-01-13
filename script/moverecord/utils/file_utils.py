"""PC 메타정보 및 파일 경로 관련 유틸"""
import socket
import getpass
import platform
import sys
import tkinter as tk
from pathlib import Path


def collect_pc_meta():
    """PC 메타정보 수집"""
    info = {
        'host': socket.gethostname(),
        'user': getpass.getuser(),
        'os': platform.platform(),
        'python': sys.version.split()[0],
    }
    try:
        tmp = tk.Tk()
        tmp.withdraw()
        info['screen_width'] = tmp.winfo_screenwidth()
        info['screen_height'] = tmp.winfo_screenheight()
        tmp.destroy()
    except Exception:
        pass
    return info


def escape_html(text):
    """HTML 특수문자 이스케이프"""
    try:
        return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    except Exception:
        return str(text)


def path_to_href(path):
    """파일 경로를 HTML href 링크로 변환"""
    if not path:
        return ''
    try:
        import os
        norm = os.path.abspath(path).replace('\\', '/').replace(' ', '%20')
        return 'file:///' + norm
    except Exception:
        return ''


def get_base_dir():
    """프로젝트 기준 디렉토리 반환"""
    return Path(__file__).resolve().parent.parent.parent
