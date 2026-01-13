"""HTML 생성 관련 유틸"""
import os
from datetime import datetime
from .file_utils import escape_html, path_to_href


def format_datetime(dt_obj):
    """datetime 객체를 문자열로 포맷팅"""
    if not dt_obj:
        return ''
    try:
        return dt_obj.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(dt_obj)


def create_meta_row(label, value):
    """메타정보 테이블 행 생성"""
    return f'<tr><th>{escape_html(label)}</th><td>{escape_html(value)}</td></tr>'


def build_summary_rows(log_data):
    """요약 정보 행 목록 생성"""
    started_at = log_data.get('started_at')
    ended_at = log_data.get('ended_at')
    duration_s = log_data.get('duration_s', '')
    status = log_data.get('status', 'unknown')
    overall = log_data.get('overall_result', 'unknown')
    script_path = log_data.get('script_path', '')
    target_meta = log_data.get('target_meta', {}) or {}
    error_message = log_data.get('error_message', '')
    
    summary_rows = [
        create_meta_row('스크립트 파일', os.path.basename(script_path) if script_path else ''),
        create_meta_row('상태', status),
        create_meta_row('전체 결과', overall),
        create_meta_row('시작', format_datetime(started_at)),
        create_meta_row('종료', format_datetime(ended_at)),
        create_meta_row('소요(초)', f"{duration_s:.2f}" if isinstance(duration_s, (int, float)) else duration_s),
        create_meta_row('로그 디렉터리', log_data.get('log_dir', '')),
    ]
    
    if target_meta:
        summary_rows.extend([
            create_meta_row('대상 PID', target_meta.get('active_window_pid', '')),
            create_meta_row('대상 프로세스', target_meta.get('active_process_name', '')),
            create_meta_row('대상 창 제목', target_meta.get('active_window_title', '')),
        ])
    
    if error_message:
        summary_rows.append(create_meta_row('에러', error_message))
    
    return summary_rows


def build_pc_meta_rows(pc_meta):
    """PC 메타정보 행 목록 생성"""
    pc_rows = []
    for k in ('host', 'user', 'os', 'python', 'screen_width', 'screen_height'):
        if k in pc_meta:
            pc_rows.append(create_meta_row(k, pc_meta.get(k, '')))
    return pc_rows


def build_imgcheck_rows(img_results):
    """imgcheck 결과 행 목록 생성"""
    img_rows = []
    for idx, ev in enumerate(img_results, 1):
        href = path_to_href(ev.get('saved_path', ''))
        link_html = f"<a href='{href}'>열기</a>" if href else ''
        img_rows.append(
            '<tr>'
            f'<td>{idx}</td>'
            f'<td>{escape_html(ev.get("input_image", ""))}</td>'
            f'<td>{"PASS" if ev.get("passed") else "FAIL"}</td>'
            f'<td>{escape_html(ev.get("score", ""))}</td>'
            f'<td>{escape_html(ev.get("message", ""))}</td>'
            f'<td>{escape_html(ev.get("elapsed_ms", ""))}</td>'
            f'<td>{link_html}</td>'
            '</tr>'
        )
    return img_rows


def generate_html(log_data):
    """HTML 로그 생성"""
    log_dir = log_data.get('log_dir', '')
    csv_base = log_data.get('csv_filename', '')
    
    summary_rows = build_summary_rows(log_data)
    pc_meta = log_data.get('pc_meta', {}) or {}
    pc_rows = build_pc_meta_rows(pc_meta)
    
    img_results = log_data.get('imgcheck_results', []) or []
    img_rows = build_imgcheck_rows(img_results)
    
    html_body = f"""
<!DOCTYPE html>
<html lang='ko'>
<head>
  <meta charset='utf-8'>
  <title>테스트 로그</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ margin-bottom: 0; }}
    .meta-table th {{ text-align: left; width: 140px; padding: 4px; background: #f0f0f0; }}
    .meta-table td {{ padding: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    table, th, td {{ border: 1px solid #ccc; }}
    th, td {{ padding: 6px; text-align: left; }}
    .pass {{ color: green; font-weight: bold; }}
    .fail {{ color: red; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>테스트 로그</h1>
  <table class='meta-table'>
    {''.join(summary_rows)}
  </table>

  <h2>PC 메타정보</h2>
  <table class='meta-table'>
    {''.join(pc_rows) if pc_rows else '<tr><td>정보 없음</td></tr>'}
  </table>

  <h2>imgcheck 결과</h2>
  <table>
    <tr><th>#</th><th>템플릿</th><th>결과</th><th>점수</th><th>메시지</th><th>재생 시점(ms)</th><th>이미지</th></tr>
    {''.join(img_rows) if img_rows else '<tr><td colspan="7">imgcheck 이벤트 없음</td></tr>'}
  </table>

  <p>CSV: {csv_base}</p>
</body>
</html>
"""
    return html_body
