import os
import sys
from pathlib import Path
import pytest

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# script/moverecord 경로도 sys.path에 추가 (모듈 내 상대가 아닌 절대 임포트 대응: utils, config 등)
MOVER_DIR = PROJECT_ROOT / "script" / "moverecord"
if str(MOVER_DIR) not in sys.path:
    sys.path.insert(0, str(MOVER_DIR))

# 테스트 중 브라우저 열기 방지
os.environ.setdefault('DISABLE_OPEN_BROWSER', '1')

@pytest.fixture(scope='session')
def test_session_dir():
    """테스트 세션마다 고유한 디렉터리 생성 (히스토리 유지)"""
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = PROJECT_ROOT / "tests" / "testlog" / f"run_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # 환경변수로 세션 디렉터리를 전달 (로깅 함수가 참조)
    os.environ['TEST_SESSION_DIR'] = str(session_dir)
    
    return session_dir

@pytest.fixture
def tmp_artifacts(test_session_dir):
    """테스트 산출물 저장 경로를 세션별 디렉터리의 artifacts로 설정"""
    base = test_session_dir / "artifacts"
    base.mkdir(parents=True, exist_ok=True)
    return base
