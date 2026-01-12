"""이벤트 저장 관련 함수"""
import json
import os
import getpass
from datetime import datetime
from tkinter import filedialog
from pathlib import Path


def save_events_to_file(events, default_name='recording.json', meta_extra=None):
    """이벤트 목록을 JSON 파일로 저장"""
    # 기본 파일명: [user]_[YYYYMMDD]_[HHMMSS].json
    try:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        user = getpass.getuser() or 'user'
        suggested_name = f"{user}_{ts}.json"
    except Exception:
        suggested_name = default_name

    try:
        fpath = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON Files','*.json')],
            initialfile=suggested_name
        )
    except Exception:
        fpath = None
    
    if not fpath:
        return None
    
    try:
        # build events list
        json_events = []
        for ev in events:
            t_ms = int(ev[0])
            etype = ev[1]
            params = list(ev[2:])
            json_events.append({'t_ms': t_ms, 'type': etype, 'params': params})
        
        # gather screen size from temp root
        screen_w = None
        screen_h = None
        try:
            import tkinter as tk
            root_tmp = tk.Tk()
            root_tmp.withdraw()
            screen_w = root_tmp.winfo_screenwidth()
            screen_h = root_tmp.winfo_screenheight()
            root_tmp.destroy()
        except Exception:
            screen_w = None
            screen_h = None
        
        from config import RECORDER_VERSION
        meta = {
            'recorder_version': RECORDER_VERSION,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'screen_width': screen_w,
            'screen_height': screen_h
        }
        
        if meta_extra:
            try:
                meta.update(meta_extra)
            except Exception:
                pass
        
        payload = {'meta': meta, 'events': json_events}
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        
        return fpath
    except Exception as e:
        print('파일 저장 실패:', e)
        return None


def migrate_txt_to_json(txt_path):
    """txt 형식의 녹화 파일을 JSON으로 변환"""
    try:
        events = []
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                try:
                    t_ms = int(parts[0])
                except Exception:
                    continue
                etype = parts[1]
                params = []
                for p in parts[2:]:
                    # try numeric conversion
                    try:
                        if '.' in p:
                            params.append(float(p))
                        else:
                            params.append(int(p))
                    except Exception:
                        params.append(p)
                events.append({'t_ms': t_ms, 'type': etype, 'params': params})
        
        # write json sidecar
        base = os.path.splitext(txt_path)[0]
        out = base + '.json'
        from config import RECORDER_VERSION
        meta = {'recorder_version': RECORDER_VERSION, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        payload = {'meta': meta, 'events': events}
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out
    except Exception as e:
        print('마이그레이션 실패:', e)
        return None
