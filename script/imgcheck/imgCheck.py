"""
imgCheck.py

기능:
 - 특정 프로세스(또는 PID)를 선택
 - 해당 프로세스의 창을 캡처
 - 프로젝트의 `img/` 폴더에 있는 이미지들과 화면을 비교(템플릿 매칭)
 - 동일한 부분이 있으면 PASS 알림, 없으면 FAIL 알림

사용법:
 python imgCheck.py          # 프로세스 목록을 보여주고 선택
 python imgCheck.py --pid 1234
 python imgCheck.py --name chrome

필수 패키지:
 pip install opencv-python numpy pillow psutil pywin32

Windows 전용 구현입니다.
"""

import os
import sys
import time
import argparse
from typing import List, Tuple, Optional
from pathlib import Path

# 프로젝트 루트 기준 경로
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_IMG_DIR = BASE_DIR / 'img'
DEBUG_DIR = BASE_DIR / 'debugimg'

# 외부 의존성 확인
try:
    import psutil
    import cv2
    import numpy as np
    from PIL import ImageGrab
    import ctypes
except Exception as e:
    print("필수 패키지가 누락되었거나 임포트 중 에러가 발생했습니다:", e)
    print("설치: pip install opencv-python numpy pillow psutil")
    sys.exit(1)

# Windows 전용 모듈(pywin32)은 윈도우에서만 임포트
if sys.platform == 'win32':
    try:
        import win32gui
        import win32con
        import win32process
    except Exception as e:
        print("Windows 전용 패키지 'pywin32'가 필요합니다:", e)
        print("설치: pip install pywin32")
        sys.exit(1)
else:
    print("이 스크립트는 Windows 전용입니다.")
    sys.exit(1)

SUPPORTED_EXT = ('.png', '.jpg', '.jpeg', '.bmp')

# 프로세스 나열
def list_user_processes(limit=30) -> List[Tuple[int, str]]:
    procs = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            procs.append((p.info['pid'], p.info['name']))
        except Exception:
            pass
    # 중복 이름 제거, 안정적으로 정렬
    unique = {}
    for pid, name in procs:
        if name not in unique:
            unique[name] = pid
    items = list(unique.items())[:limit]
    return [(pid, name) for name, pid in items]

# 특정 PID에 속한 탑-레벨 창 찾기
def find_windows_for_pid(pid: int) -> List[Tuple[int, str]]:
    results: List[Tuple[int, str]] = []

    def callback(hwnd, _: None):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if window_pid == pid:
                title = win32gui.GetWindowText(hwnd)
                results.append((hwnd, title))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(callback, None)
    return results

# 이름(프로세스명 또는 창 제목)으로 창 목록 찾기 (visible 우선 정렬)
def find_windows_for_name(name_substr: str) -> List[Tuple[int, int, str, bool, str]]:
    """Returns list of (pid, hwnd, title, visible, proc_name)"""
    name_l = (name_substr or '').lower()
    results = []

    def callback(hwnd, _):
        try:
            title = win32gui.GetWindowText(hwnd) or ''
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc_name = (psutil.Process(pid).name() or '')
            except Exception:
                proc_name = ''
            if name_l in proc_name.lower() or name_l in title.lower():
                visible = bool(win32gui.IsWindowVisible(hwnd))
                results.append((pid, hwnd, title, visible, proc_name))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(callback, None)
    # visible한 창을 먼저 보여주고, 제목 기준 정렬
    results.sort(key=lambda x: (not x[3], x[2].lower()))
    return results

# 창 캡처 (클라이언트 영역만 캡처)
def capture_window(hwnd: int):
    try:
        # GetClientRect 반환값은 (left, top, right, bottom) 이지만 일반적으로 left/top이 0입니다.
        cl_left, cl_top, cl_right, cl_bottom = win32gui.GetClientRect(hwnd)
        # 클라이언트 좌표(윈도우 내부) -> 스크린 좌표로 변환
        left_top = win32gui.ClientToScreen(hwnd, (cl_left, cl_top))
        right_bottom = win32gui.ClientToScreen(hwnd, (cl_right, cl_bottom))
        left, top = left_top
        right, bottom = right_bottom
        # ImageGrab expects (left, top, right, bottom)
        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        # Convert to BGR (OpenCV 형식)
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return img_cv
    except Exception as e:
        print("창 캡처 중 오류:", e)
        return None

# 템플릿 매칭 (그레이스케일, TM_CCOEFF_NORMED 사용)
def match_templates(screen: np.ndarray, img_dir: str, threshold: float = 0.9):
    timing_start = time.time()
    if screen is None:
        return False, None
    timing_gray = time.time()
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    h_s, w_s = screen_gray.shape

    templates = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith(SUPPORTED_EXT)]
    if not templates:
        print("img 폴더에 이미지 파일이 없습니다.")
        return False, None

    best_matches = []

    # 스케일 파라미터
    scale_min = globals().get('SCALE_MIN', 0.5)
    scale_max = globals().get('SCALE_MAX', 2.0)
    scale_steps = globals().get('SCALE_STEPS', 121)
    upsample = globals().get('UPSAMPLE', False)
    use_edges = globals().get('USE_EDGES', False)
    canny_th1 = globals().get('CANNY_TH1', 50)
    canny_th2 = globals().get('CANNY_TH2', 150)

    # 전처리: 화면 엣지
    screen_proc = screen_gray
    if use_edges:
        screen_proc = cv2.Canny(screen_gray, canny_th1, canny_th2)

    for tpl_path in templates:
        tpl_color = cv2.imread(tpl_path)
        if tpl_color is None:
            continue
        tpl_gray = cv2.cvtColor(tpl_color, cv2.COLOR_BGR2GRAY)
        h_t0, w_t0 = tpl_gray.shape

        candidates = []

        # optionally upsample tpl for small templates
        tpl_variants = [tpl_gray]
        # 작은 템플릿의 경우 자동으로 업샘플 버전을 추가하여 작은 대상에 대해 기민하게 동작하도록 합니다.
        if upsample or max(w_t0, h_t0) < 48:
            tpl_up = cv2.resize(tpl_gray, (w_t0*2, h_t0*2), interpolation=cv2.INTER_CUBIC)
            tpl_variants.append(tpl_up)

        for tpl_base in tpl_variants:
            hb, wb = tpl_base.shape
            for scale in np.linspace(scale_min, scale_max, scale_steps):
                w_t = int(wb * scale)
                h_t = int(hb * scale)
                if w_t < 8 or h_t < 8:
                    continue
                if h_t > h_s or w_t > w_s:
                    continue
                tpl_resized = cv2.resize(tpl_base, (w_t, h_t), interpolation=cv2.INTER_AREA)
                tpl_proc = tpl_resized
                if use_edges:
                    tpl_proc = cv2.Canny(tpl_resized, 50, 150)
                res = cv2.matchTemplate(screen_proc, tpl_proc, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                candidates.append((max_val, max_loc, (w_t, h_t), scale))

        if not candidates:
            continue

        # 최고값 선택
        best = max(candidates, key=lambda x: x[0])
        best_val, best_loc, best_size, best_scale = best
        if globals().get('VERBOSE', False):
            print(f"DEBUG: template={os.path.basename(tpl_path)}, best_max={best_val:.6f}, scale={best_scale:.2f}")
        best_matches.append((tpl_path, best_val, best_loc, best_size))

    if not best_matches:
        return False, None

    # 최고값 찾기
    best_matches.sort(key=lambda x: x[1], reverse=True)
    top = best_matches[0]
    tpl_path, score, loc, (w_t, h_t) = top
    timing_end = time.time()
    if globals().get('VERBOSE', False):
        print(f"DEBUG: match_templates 총 시간={timing_end-timing_start:.4f}초, 변환={timing_gray-timing_start:.4f}초")
    if score >= threshold:
        # 일치 발견
        return True, {'template': tpl_path, 'score': score, 'location': loc, 'size': (w_t, h_t)}
    return False, {'best_score': top}


# 특징 기반 매칭 (ORB + RANSAC)
def feature_match(screen: np.ndarray, img_dir: str, min_inliers: Optional[int] = None, ratio: Optional[float] = None):
    """Returns (ok:bool, info:dict or None)
    info contains: template, inliers, location_poly (4x1x2 float points), matches_mask, good_matches, kp_screen, kp_tpl
    """
    timing_start = time.time()
    if screen is None:
        return False, None
    timing_gray = time.time()
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    method = globals().get('FEATURE_METHOD', 'orb')
    ratio = ratio if ratio is not None else globals().get('ORB_RATIO', 0.8)
    min_inliers = min_inliers if min_inliers is not None else globals().get('ORB_MIN_INLIERS', 6)

    # detector/descriptor 선택
    if method == 'sift':
        try:
            detector = cv2.SIFT_create()
            norm = cv2.NORM_L2
        except Exception:
            if globals().get('VERBOSE', False):
                print('SIFT 사용 불가, AKAZE로 대체합니다.')
            detector = cv2.AKAZE_create()
            norm = cv2.NORM_HAMMING
    elif method == 'akaze':
        detector = cv2.AKAZE_create()
        norm = cv2.NORM_HAMMING
    else:
        nfeat = globals().get('ORB_NFEATURES', 3000)
        detector = cv2.ORB_create(nfeat)
        norm = cv2.NORM_HAMMING

    kp_screen, des_screen = detector.detectAndCompute(screen_gray, None)
    if des_screen is None or len(kp_screen) < 4:
        return False, None

    templates = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith(SUPPORTED_EXT)]
    if not templates:
        return False, None

    # BF matcher 설정
    if norm == cv2.NORM_HAMMING:
        bf = cv2.BFMatcher(norm, crossCheck=False)
    else:
        bf = cv2.BFMatcher(norm, crossCheck=False)

    best_candidate = None
    best_inliers = 0

    for tpl_path in templates:
        tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            continue
        kp_tpl, des_tpl = detector.detectAndCompute(tpl, None)
        if des_tpl is None or len(kp_tpl) < 4:
            continue
        # tpl -> screen
        matches = bf.knnMatch(des_tpl, des_screen, k=2)
        good = []
        for m_n in matches:
            if len(m_n) < 2:
                continue
            m, n = m_n
            if m.distance < ratio * n.distance:
                good.append(m)
        if len(good) < 4:
            # 충분한 후보 매칭 아님
            continue
        src_pts = np.float32([kp_tpl[m.queryIdx].pt for m in good]).reshape(-1,1,2)
        dst_pts = np.float32([kp_screen[m.trainIdx].pt for m in good]).reshape(-1,1,2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None or mask is None:
            continue
        inliers = int(np.sum(mask))
        if inliers > best_inliers:
            best_inliers = inliers
            h, w = tpl.shape
            pts = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
            dst = cv2.perspectiveTransform(pts, M)
            best_candidate = {
                'template': tpl_path,
                'inliers': inliers,
                'location_poly': dst,
                'matches_mask': mask.ravel().tolist(),
                'good_matches': good,
                'kp_screen': kp_screen,
                'kp_tpl': kp_tpl
            }

    if best_candidate and best_inliers >= min_inliers:
        return True, best_candidate
    # 실패 시 최고 후보도 반환
    timing_end = time.time()
    if globals().get('VERBOSE', False):
        print(f"DEBUG: feature_match 총 시간={timing_end-timing_start:.4f}초, 변환={timing_gray-timing_start:.4f}초")
    return False, {'best_candidate': best_candidate, 'best_inliers': best_inliers}

# Windows 알림
def notify_windows(title: str, message: str):
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0)
    except Exception:
        print(f"{title}: {message}")

# 명령행 처리 및 실행
def main():
    parser = argparse.ArgumentParser(description="프로세스 화면에서 img/ 폴더의 템플릿 매칭을 수행합니다.")
    parser.add_argument('--pid', type=int, help='타겟 프로세스 PID')
    parser.add_argument('--name', type=str, help='프로세스 이름 또는 창 제목(부분 일치 검색)')
    parser.add_argument('--img-dir', type=str, default=str(DEFAULT_IMG_DIR), help='템플릿 이미지가 들어있는 폴더 (기본: img)')
    parser.add_argument('--threshold', type=float, default=0.9, help='매칭 임계값 (기본 0.9)')
    parser.add_argument('--verbose', action='store_true', help='디버그 로그 및 디버그 이미지 저장 메시지 출력')
    parser.add_argument('--no-feature', action='store_true', help='템플릿 매칭 실패 시 특징 기반 매칭(ORB) 시도를 비활성화')
    parser.add_argument('--auto', action='store_true', help='탑-레벨 창들 중 visible한 첫 번째 창을 자동 선택')
    # 스케일 및 전처리 옵션
    parser.add_argument('--scale-min', type=float, default=0.5, help='템플릿 스케일 최소값 (기본: 0.5)')
    parser.add_argument('--scale-max', type=float, default=2.0, help='템플릿 스케일 최대값 (기본: 2.0)')
    parser.add_argument('--scale-steps', type=int, default=121, help='스케일 단계 수 (기본 121)')
    parser.add_argument('--upsample', action='store_true', help='작은 템플릿 업샘플(2x) 시도')
    parser.add_argument('--use-edges', action='store_true', help='엣지(Canny) 기반 매칭을 시도')
    parser.add_argument('--canny-th1', type=int, default=50, help='Canny 첫번째 임계값 (기본 50)')
    parser.add_argument('--canny-th2', type=int, default=150, help='Canny 두번째 임계값 (기본 150)')
    # 특징 매칭 설정
    parser.add_argument('--feature-method', type=str, default='orb', choices=['orb','sift','akaze'], help='특징 기반 매칭 알고리즘 (기본: orb)')
    parser.add_argument('--orb-nfeatures', type=int, default=5000, help='ORB 특징 수 (기본 5000)')
    parser.add_argument('--orb-ratio', type=float, default=0.75, help='ORB ratio test 비율 (기본 0.75)')
    parser.add_argument('--orb-min-inliers', type=int, default=8, help='ORB 최소 inliers (기본 8)')

    args = parser.parse_args()
    # 전역 VERBOSE 설정
    globals()['VERBOSE'] = args.verbose
    globals()['NO_FEATURE'] = args.no_feature
    globals()['AUTO_SELECT_WINDOW'] = args.auto
    globals()['SCALE_MIN'] = args.scale_min
    globals()['SCALE_MAX'] = args.scale_max
    globals()['SCALE_STEPS'] = args.scale_steps
    globals()['UPSAMPLE'] = args.upsample
    globals()['USE_EDGES'] = args.use_edges
    globals()['CANNY_TH1'] = args.canny_th1
    globals()['CANNY_TH2'] = args.canny_th2
    globals()['FEATURE_METHOD'] = args.feature_method
    globals()['ORB_NFEATURES'] = args.orb_nfeatures
    globals()['ORB_RATIO'] = args.orb_ratio
    globals()['ORB_MIN_INLIERS'] = args.orb_min_inliers

    img_dir = Path(args.img_dir)
    if not img_dir.is_absolute():
        img_dir = BASE_DIR / img_dir
    args.img_dir = str(img_dir)

    # DPI awareness: 고해상도 화면에서 캡처 픽셀 정합성 개선
    if sys.platform == 'win32':
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            if globals().get('VERBOSE', False):
                print('DPI awareness enabled')
        except Exception:
            pass

    if not img_dir.is_dir():
        print(f"이미지 폴더가 존재하지 않습니다: {img_dir}")
        sys.exit(1)

    target_pid = None
    selected_hwnd = None

    if args.pid:
        target_pid = args.pid
    elif args.name:
        # 창(윈도우) 기준으로 선택: 프로세스명 또는 창 제목에 부분 일치하는 탑-레벨 창을 찾습니다.
        windows = find_windows_for_name(args.name)
        if windows:
            if globals().get('AUTO_SELECT_WINDOW', False):
                pid, hwnd, title, visible, proc_name = windows[0]
                target_pid = pid
                selected_hwnd = hwnd
            elif len(windows) == 1:
                pid, hwnd, title, visible, proc_name = windows[0]
                target_pid = pid
                selected_hwnd = hwnd
            else:
                print("찾은 창들 (인덱스: PID, HWND, VISIBLE, TITLE, PROC):")
                for i, (pid, hwnd, title, visible, proc_name) in enumerate(windows):
                    print(f"{i}: PID={pid}, HWND={hwnd}, VISIBLE={visible}, TITLE='{title}', PROC='{proc_name}'")
                sel = input("캡처할 창 인덱스 (기본 0): ")
                sel_idx = int(sel) if sel.strip() else 0
                pid, hwnd, title, visible, proc_name = windows[sel_idx]
                target_pid = pid
                selected_hwnd = hwnd
        else:
            # 폴백: 기존 프로세스 이름 기반 선택
            matches = [p for p in psutil.process_iter(['pid', 'name']) if args.name.lower() in (p.info['name'] or '').lower()]
            if not matches:
                print("이름과 일치하는 프로세스/창을 찾을 수 없습니다.")
                sys.exit(1)
            if len(matches) == 1:
                target_pid = matches[0].info['pid']
            else:
                print("다음 프로세스 중 선택하세요:")
                for i, p in enumerate(matches):
                    print(f"{i}: PID={p.info['pid']}, NAME={p.info['name']}")
                idx = int(input("선택 인덱스: "))
                target_pid = matches[idx].info['pid']
    else:
        # 리스트 보여주고 선택
        items = list_user_processes(limit=50)
        print("프로세스 목록 (예: 0, 1, ...):")
        for i, (pid, name) in enumerate(items):
            print(f"{i}: PID={pid}, NAME={name}")
        idx = input("선택 인덱스 (또는 PID 입력): ")
        if idx.isdigit() and int(idx) < len(items):
            target_pid = items[int(idx)][0]
        else:
            try:
                target_pid = int(idx)
            except Exception:
                print("유효하지 않은 입력입니다.")
                sys.exit(1)

    print(f"선택한 PID: {target_pid}")

    windows = find_windows_for_pid(target_pid)
    if not windows:
        print("해당 PID에 속한 창을 찾지 못했습니다.")
        sys.exit(1)

    if len(windows) == 1:
        hwnd, title = windows[0]
    else:
        # 이전에 선택한 HWND가 있으면 우선 사용
        if selected_hwnd is not None:
            for hw, tt in windows:
                if hw == selected_hwnd:
                    hwnd, title = hw, tt
                    break
            else:
                print("찾은 창들:")
                for i, (hwnd_i, title_i) in enumerate(windows):
                    print(f"{i}: HWND={hwnd_i}, TITLE='{title_i}'")
                sel = input("캡처할 창 인덱스 (기본 0): ")
                sel_idx = int(sel) if sel.strip() else 0
                hwnd, title = windows[sel_idx]
        else:
            print("찾은 창들:")
            for i, (hwnd, title) in enumerate(windows):
                print(f"{i}: HWND={hwnd}, TITLE='{title}'")
            sel = input("캡처할 창 인덱스 (기본 0): ")
            sel_idx = int(sel) if sel.strip() else 0
            hwnd, title = windows[sel_idx]

    print(f"선택 창: HWND={hwnd}, TITLE='{title}' — 캡처 중...")

    # 창을 전면으로 올리고(최소화 상태면 복원) 잠시 기다려 화면이 갱신되도록 합니다.
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print("창 전면화 중 오류:", e)

    time.sleep(0.3)

    # 캡처를 여러 번 시도하여 일시적 실패 대응
    capture_start = time.time()
    screen = None
    for attempt in range(3):
        screen = capture_window(hwnd)
        if screen is not None:
            break
        print(f"캡처 시도 {attempt+1} 실패, 재시도 중...")
        time.sleep(0.25)
    capture_time = time.time() - capture_start

    if screen is None:
        print("화면 캡처 실패")
        sys.exit(1)

    # debugimg 디렉토리 생성 및 캡처 저장
    debug_dir = DEBUG_DIR
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    capture_fname = debug_dir / f'capture_pid{target_pid}_hwnd{hwnd}_{ts}.png'
    try:
        cv2.imwrite(str(capture_fname), screen)
        if globals().get('VERBOSE', False):
            print(f"디버그: 캡처 이미지 저장 -> {capture_fname}")
    except Exception as e:
        if globals().get('VERBOSE', False):
            print("디버그 이미지 저장 실패:", e)

    ok, info = match_templates(screen, args.img_dir, args.threshold)
    if ok:
        tpl = info['template']
        score = info['score']
        loc = info['location']
        w_t, h_t = info['size']
        print(f"PASS: 템플릿 '{tpl}' 발견 (score={score:.3f}) 위치={loc}")
        print(f"[타이밍] 캡처: {capture_time:.4f}초")

        # 일치 영역 시각화 및 저장
        vis = screen.copy()
        top_left = loc
        bottom_right = (top_left[0] + w_t, top_left[1] + h_t)
        cv2.rectangle(vis, top_left, bottom_right, (0,255,0), 2)
        vis_fname = debug_dir / f"match_{os.path.splitext(os.path.basename(tpl))[0]}_{score:.3f}_{ts}.png"
        try:
            cv2.imwrite(str(vis_fname), vis)
            if globals().get('VERBOSE', False):
                print(f"디버그: 매칭 결과 이미지 저장 -> {vis_fname}")
        except Exception as e:
            if globals().get('VERBOSE', False):
                print("디버그 결과 저장 실패:", e)

        notify_windows("PASS", f"템플릿 발견: {os.path.basename(tpl)}\nscore={score:.3f}")
        sys.exit(0)
    else:
        print("템플릿 매칭으로는 못찾았습니다.")
        # --no-feature 옵션이 설정되면 특징 매칭 시도 없이 실패로 처리합니다.
        if globals().get('NO_FEATURE', False):
            print("특징 기반 매칭이 비활성화되어 있습니다 (--no-feature).")
            print("FAIL: 일치하는 템플릿을 찾지 못했습니다.")
            notify_windows("FAIL", "일치하는 템플릿을 찾지 못했습니다.")
            sys.exit(2)

        print("특징 기반 매칭(ORB)을 시도합니다...")
        f_ok, f_info = feature_match(screen, args.img_dir)
        if f_ok:
            tpl = f_info['template']
            inliers = f_info['inliers']
            poly = f_info['location_poly']
            print(f"FEATURE PASS: 템플릿 '{tpl}' 발견 (inliers={inliers})")
            print(f"[타이밍] 캡처: {capture_time:.4f}초")

            # 시각화: 폴리곤 그리기
            vis = screen.copy()
            pts_int = np.int32(poly)
            cv2.polylines(vis, [pts_int], True, (0,255,0), 3)
            vis_fname = debug_dir / f"feature_{os.path.splitext(os.path.basename(tpl))[0]}_{inliers}_{ts}.png"
            try:
                cv2.imwrite(str(vis_fname), vis)
                if globals().get('VERBOSE', False):
                    print(f"디버그: 특징 매칭 결과 저장 -> {vis_fname}")
            except Exception as e:
                if globals().get('VERBOSE', False):
                    print("디버그 저장 실패:", e)

            notify_windows("PASS", f"템플릿 발견 (특징): {os.path.basename(tpl)}\ninliers={inliers}")
            sys.exit(0)
        else:
            print("FEATURE FAIL: 특징 기반 매칭으로도 찾지 못했습니다.")
            print(f"[타이밍] 캡처: {capture_time:.4f}초")
            best = f_info.get('best_candidate') if isinstance(f_info, dict) else None
            if best:
                try:
                    tpl_path = best.get('template') if best else None
                    best_inliers = f_info.get('best_inliers', 0)
                    vis = screen.copy()
                    if best and best.get('location_poly') is not None:
                        pts_int = np.int32(best['location_poly'])
                        cv2.polylines(vis, [pts_int], True, (0,0,255), 3)
                    vis_fname = debug_dir / f"feature_best_{os.path.splitext(os.path.basename(tpl_path))[0]}_{best_inliers}_{ts}.png"
                    cv2.imwrite(str(vis_fname), vis)
                    if globals().get('VERBOSE', False):
                        print(f"디버그: 특징 실패 최고 후보 저장 -> {vis_fname}")
                except Exception as e:
                    if globals().get('VERBOSE', False):
                        print("디버그 후보 시각화 실패:", e)

            # 기존 실패 처리 (템플릿 기준 최고 후보 이미지도 이미 저장됨)
            print("FAIL: 일치하는 템플릿을 찾지 못했습니다.")
            notify_windows("FAIL", "일치하는 템플릿을 찾지 못했습니다.")
            sys.exit(2)

if __name__ == '__main__':
    main()
