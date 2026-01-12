# 🎯 moveRecord 프로젝트

Windows 기반 **마우스/키보드 자동화 및 매크로 작성 도구**입니다.

## 📋 주요 기능

### 1. 반복 매크로 (Tab 1)
- 특정 키를 지정된 간격으로 반복 입력
- 실행 시간, 간격, 입력할 키 설정 가능
- F5 핫키로 시작/중지 토글

### 2. 녹화/재생 (Tab 2)
- **녹화**: 마우스 움직임, 클릭, 스크롤, 키보드 입력 자동 녹화
- **재생**: 녹화된 동작을 자동 재생
- 배속 조절 (0.5x ~ 3.0x)
- 반복 횟수 설정
- 이미지 템플릿 매칭 지원 (imgcheck)
- F6 핫키로 재생 시작/중지

### 3. JSON 편집기 (Tab 3)
- 녹화된 매크로 파일 편집
- 이벤트 추가/삭제/수정
- 되돌리기/다시하기 지원
- 직관적인 행 기반 편집

### 4. imgCheck 통합
- 실시간 이미지 템플릿 매칭
- 매크로 실행 중 화면 상태 검증
- 매칭 결과를 로그에 기록

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
cd e:\PythonProject\2026macroTest
pip install -r requirements.txt
```

### 2. 프로그램 실행
```bash
python run.py
```

### 3. 기본 사용법

**Tab 1: 반복 매크로**
1. 실행 시간(초), 입력할 키, 간격(ms) 입력
2. `시작` 버튼 또는 F5 키 누르기
3. ESC로 즉시 중지

**Tab 2: 녹화/재생**
1. `녹화` 버튼으로 마우스/키보드 동작 녹화
2. JSON 파일로 자동 저장
3. `스크립트 선택`에서 파일 선택
4. `스크립트 시작` 버튼으로 재생

**Tab 3: JSON 편집**
1. `스크립트 로드`로 JSON 파일 불러오기
2. 행 추가/삭제/수정
3. `저장`으로 파일 저장

## 📁 프로젝트 구조

```
script/moverecord/
├── moveRecord.py              (메인 GUI 애플리케이션)
├── config/                    (설정 상수)
├── utils/                     (유틸리티 함수)
├── recording/                 (녹화 기능)
├── playback/                  (재생 기능)
├── ui/                        (UI & 핫키)
└── workers/                   (워커 스레드)
```

## 📚 문서

- **[ARCHITECTURE.md](script/moverecord/ARCHITECTURE.md)** - 프로젝트 아키텍처 및 구조
- **[REFACTORING_GUIDE.md](script/moverecord/REFACTORING_GUIDE.md)** - 마이그레이션 가이드 및 API 문서

## 🎮 핫키

| 핫키 | 기능 |
|------|------|
| **F5** | 반복 매크로 시작/중지 (토글) |
| **F6** | 스크립트 재생 시작/중지 (토글) |
| **F7** | 녹화 시작 |
| **ESC** | 즉시 중지 (현재 실행 중인 작업) |

## 🔧 기술 스택

- **GUI**: tkinter
- **자동화**: pynput (keyboard/mouse control)
- **이미지 처리**: OpenCV (cv2)
- **로깅**: 자체 HTML/CSV 생성

## ⚙️ 설정

기본 핫키는 다음과 같습니다:
- F5: 반복 매크로
- F6: 스크립트 재생
- F7: 녹화
- ESC: 중지

GUI에서 핫키를 변경할 수 있습니다.

## 📝 데이터 형식

### 녹화 파일 (JSON)
```json
{
  "meta": {
    "recorder_version": "2.0.0",
    "timestamp": "2026-01-12T10:00:00",
    "screen_width": 1920,
    "screen_height": 1080
  },
  "events": [
    {
      "t_ms": 0,
      "type": "mouse_move",
      "params": [100, 200]
    },
    {
      "t_ms": 50,
      "type": "key_down",
      "params": ["a"]
    }
  ]
}
```

## ⚠️ 주의사항

- **Windows 전용**: 이 도구는 Windows 운영체제에서만 동작합니다
- **관리자 권한**: 일부 기능은 관리자 권한이 필요할 수 있습니다
- **화면 해상도**: 재생 시 녹화된 해상도와 현재 해상도가 다르면 오류가 발생할 수 있습니다
- **목적**: 개인 자동화 및 테스트 목적으로만 사용하세요

## 🐛 트러블슈팅

**핫키가 작동하지 않음**
- 다른 프로그램이 핫키를 가로채고 있을 수 있습니다
- 핫키를 변경해보세요

**이미지 매칭이 실패함**
- 템플릿 이미지 크기가 너무 작을 수 있습니다
- 임계값을 조정해보세요

**재생이 정확하지 않음**
- 화면 해상도가 다를 수 있습니다
- 배속을 조정해보세요

## 📞 추가 정보

더 자세한 정보는 문서를 참고하세요:
- [ARCHITECTURE.md](script/moverecord/ARCHITECTURE.md) - 폴더 구조 및 모듈 설명
- [REFACTORING_GUIDE.md](script/moverecord/REFACTORING_GUIDE.md) - API 및 개발 가이드

## 📄 라이선스

이 프로젝트는 개인 학습 및 자동화 목적으로 제작되었습니다.
