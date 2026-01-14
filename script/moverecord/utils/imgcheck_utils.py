"""imgcheck 관련 유틸"""
import os
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

# imgCheck 모듈 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
IMGCHECK_DIR = BASE_DIR / 'imgcheck'

cv2 = None
np = None
capture_window = None
match_templates = None

try:
    import cv2
    import numpy as np
    # imgCheck 경로를 sys.path에 추가
    if str(IMGCHECK_DIR) not in sys.path:
        sys.path.insert(0, str(IMGCHECK_DIR))
    from imgCheck import capture_window, match_templates  # type: ignore
    print(f"[imgcheck_utils] imgCheck 모듈 로드 성공: {IMGCHECK_DIR}")
except ImportError as e:
    print(f"[imgcheck_utils] imgCheck 모듈 로드 실패: {e}")
    cv2 = None
    np = None
    capture_window = None
    match_templates = None
except Exception as e:
    print(f"[imgcheck_utils] 예상치 못한 오류: {type(e).__name__}: {e}")
    cv2 = None
    np = None
    capture_window = None
    match_templates = None


def perform_imgcheck(img_path):
    """imgcheck 실행"""
    result = {'input_image': img_path, 'passed': False}
    
    if not os.path.isfile(img_path):
        msg = f'imgcheck: 파일을 찾을 수 없습니다: {img_path}'
        result['message'] = msg
        print(msg)
        return result
    
    if not cv2 or not capture_window or not match_templates:
        msg = 'imgcheck: opencv 또는 imgCheck 모듈이 없습니다.'
        result['message'] = msg
        print(msg)
        return result
    
    hwnd = None
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            try:
                result['window_title'] = win32gui.GetWindowText(hwnd)
            except Exception:
                pass
            result['window_hwnd'] = int(hwnd)
    except Exception:
        hwnd = None
    
    if not hwnd:
        msg = 'imgcheck: 활성 창을 찾을 수 없습니다.'
        result['message'] = msg
        print(msg)
        return result
    
    screen = capture_window(hwnd)
    if screen is None:
        msg = 'imgcheck: 화면 캡처 실패'
        result['message'] = msg
        print(msg)
        return result
    
    base_dir = Path(__file__).resolve().parent.parent.parent
    temp_dir = base_dir / 'temp_imgcheck'
    debug_dir = base_dir / 'debugimg'
    temp_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    saved_path = None
    try:
        import shutil
        temp_img = temp_dir / os.path.basename(img_path)
        shutil.copy(img_path, temp_img)
        
        # 엄격한 매칭으로 정확한 이미지만 찾기 (threshold=0.85)
        ok, info = match_templates(screen, temp_dir, threshold=0.85)
        
        ts = time.strftime('%Y%m%d_%H%M%S')
        
        if ok:
            tpl = info.get('template') if isinstance(info, dict) else None
            score = info.get('score') if isinstance(info, dict) else None
            loc = info.get('location') if isinstance(info, dict) else None
            size = info.get('size') if isinstance(info, dict) else None
            w_t, h_t = size if size else (0, 0)
            score_text = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
            
            # 신뢰도 표시
            print(f'imgcheck PASS: {os.path.basename(img_path)} 발견 (정확도={score_text})')
            vis = screen.copy()
            if loc and size:
                top_left = loc
                bottom_right = (top_left[0] + w_t, top_left[1] + h_t)
                cv2.rectangle(vis, top_left, bottom_right, (0, 255, 0), 2)
            vis_fname = debug_dir / f'imgcheck_pass_{os.path.splitext(os.path.basename(img_path))[0]}_{ts}.png'
            cv2.imwrite(str(vis_fname), vis)
            saved_path = str(vis_fname)
            result.update({'passed': True, 'score': score, 'saved_path': saved_path, 'matched_template': tpl, 'message': '템플릿 일치'})
        else:
            best_score = None
            if info and isinstance(info, dict):
                best_raw = info.get('best_score')
                if best_raw and isinstance(best_raw, (list, tuple)) and len(best_raw) > 1:
                    best_score = best_raw[1]
            
            # 실패 메시지에 최고 점수 표시
            score_info = f" (최고 점수: {best_score:.3f}, 임계값: 0.85)" if best_score else ""
            msg = f"imgcheck FAIL: {os.path.basename(img_path)} 찾지 못함{score_info}"
            print(msg)
            fail_fname = debug_dir / f'imgcheck_fail_{os.path.splitext(os.path.basename(img_path))[0]}_{ts}.png'
            cv2.imwrite(str(fail_fname), screen)
            saved_path = str(fail_fname)
            result.update({'passed': False, 'score': best_score, 'saved_path': saved_path, 'message': '일치 없음'})
    except Exception as e:
        msg = f'imgcheck 실행 중 오류: {e}'
        result['message'] = msg
        print(msg)
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass
    
    result['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    if saved_path:
        result['saved_path'] = saved_path
    return result
