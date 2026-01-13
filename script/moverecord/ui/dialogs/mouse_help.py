"""마우스 이벤트 도움말 대화상자"""

from tkinter import messagebox


def show_mouse_help():
    """마우스 이벤트 파라미터 도움말을 표시합니다."""
    messagebox.showinfo(
        '마우스 이벤트 도움말',
        """마우스 이벤트 파라미터 형식:

1. mouse_click: ["Button.left", "press", x, y]
   - Button: "Button.left", "Button.middle", "Button.right"
   - Action: "press", "release"
   - x, y: 클릭 위치

2. mouse_scroll: [dx, dy, x, y]
   - dx: 좌우 스크롤 (음수=왼쪽, 양수=오른쪽)
   - dy: 상하 스크롤 (음수=아래, 양수=위)
   - x, y: 스크롤 위치

3. mouse_move: [x, y]
   - x, y: 마우스 이동 위치

예제:
- mouse_click: ["Button.left", "press", 100, 100]
- mouse_scroll: [0, 3, 500, 300]
- mouse_move: [1920, 1080]"""
    )
