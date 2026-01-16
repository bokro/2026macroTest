"""로그 파일 생성 유틸"""
import os
import csv
import webbrowser
from datetime import datetime
from pathlib import Path
from .html_utils import generate_html
from .file_utils import path_to_href


def write_test_log(log_data, base_dir):
    """재생/테스트 결과를 HTML과 CSV로 저장하고 브라우저에서 엽니다.

    저장 위치 결정 우선순위:
    1) 환경변수 LOG_OUTPUT_DIR/logs
    2) 환경변수 TEST_SESSION_DIR (pytest session별 디렉터리)
    3) 프로젝트의 tests/testlog (tests 폴더가 존재하면 기본값)
    4) 전달된 base_dir/logs (기존 동작)
    """
    # 1) 환경변수 LOG_OUTPUT_DIR 우선
    override_dir = None
    try:
        _ov = os.getenv('LOG_OUTPUT_DIR')
        if _ov:
            override_dir = Path(_ov) / 'logs'
    except Exception:
        override_dir = None

    # 2) pytest 세션별 디렉터리 (환경변수로 전달)
    session_dir = None
    try:
        _sess = os.getenv('TEST_SESSION_DIR')
        if _sess:
            session_dir = Path(_sess)
    except Exception:
        session_dir = None

    # 3) tests/testlog 기본값 시도
    tests_log_dir = None
    try:
        cur = Path(__file__).resolve()
        for p in list(cur.parents)[:6]:  # 상위 6단계 안에서 tests 폴더 탐색
            cand = p / 'tests'
            if cand.exists() and cand.is_dir():
                tests_log_dir = cand / 'testlog'
                break
    except Exception:
        tests_log_dir = None

    # 4) fallback: 호출자가 준 base_dir/logs
    default_dir = Path(base_dir) / 'logs'

    log_dir = override_dir or session_dir or tests_log_dir or default_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = f'test_log_{ts}'
    html_path = log_dir / f'{base}.html'
    csv_path = log_dir / f'{base}.csv'

    script_path = log_data.get('script_path', '')
    img_results = log_data.get('imgcheck_results', []) or []

    # CSV output for Excel-friendly view
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['idx', 'template', 'passed', 'score', 'saved_image', 'message', 'played_at_ms'])
            for idx, ev in enumerate(img_results, 1):
                writer.writerow([
                    idx,
                    ev.get('input_image', ''),
                    ev.get('passed', False),
                    ev.get('score', ''),
                    ev.get('saved_path', ''),
                    ev.get('message', ''),
                    ev.get('elapsed_ms', ''),
                ])
    except Exception:
        pass

    # 로그 데이터 업데이트 (HTML 생성을 위해)
    log_data['log_dir'] = str(log_dir)
    log_data['csv_filename'] = os.path.basename(csv_path)
    
    # HTML 생성
    html_body = generate_html(log_data)

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_body)
    except Exception:
        pass

    # 테스트 환경에서 브라우저 자동 열기 비활성화 (환경변수로 제어)
    try:
        if not os.getenv('DISABLE_OPEN_BROWSER', ''):
            webbrowser.open(path_to_href(str(html_path)))
    except Exception:
        pass

    return html_path, csv_path
