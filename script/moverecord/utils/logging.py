"""로그 파일 생성 유틸"""
import os
import csv
import webbrowser
from datetime import datetime
from pathlib import Path
from .html_utils import generate_html
from .file_utils import path_to_href


def write_test_log(log_data, base_dir):
    """재생/테스트 결과를 HTML과 CSV로 저장하고 브라우저에서 엽니다."""
    log_dir = base_dir / 'logs'
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

    try:
        webbrowser.open(path_to_href(str(html_path)))
    except Exception:
        pass

    return html_path, csv_path
