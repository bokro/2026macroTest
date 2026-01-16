"""JSON 편집기 Mixin - moveRecord.py의 App 클래스에서 사용"""
import json
import tkinter as tk
from tkinter import messagebox, filedialog, ttk


class JsonEditor:
    """
    JSON 편집기 관련 메소드를 제공하는 Mixin 클래스
    
    이 클래스를 사용하는 클래스는 다음 속성들을 가지고 있어야 합니다:
    - self.root: tkinter root window
    - self.editor_rows: 편집기 행 리스트
    - self.editor_canvas: Canvas 위젯
    - self.editor_inner: Canvas 내부 프레임
    - self.editor_inner_window: Canvas window ID
    - self.meta_version, self.meta_timestamp, self.meta_width, self.meta_height: Entry 위젯
    - self.meta_active_title, self.meta_active_pid, self.meta_active_process: Entry 위젯
    - self.btn_editor_save: 저장 버튼
    - self.current_editor_path: 현재 편집 중인 파일 경로
    - self.selected_row_indices: 선택된 행 인덱스 set
    - self.selection_anchor: 선택 앵커 인덱스
    - self._undo_stack, self._redo_stack: 실행 취소/다시 실행 스택
    - self._restoring_editor_state: 상태 복원 중 플래그
    - self._edit_baseline_state: 편집 기준 상태
    - self._edit_baseline_label: 편집 기준 라벨
    - self._edit_baseline_committed: 편집 기준 커밋 플래그
    - self.undo_menu, self.redo_menu: Undo/Redo 메뉴
    - self.btn_undo, self.btn_redo: Undo/Redo 버튼
    - self.btn_undo_menu, self.btn_redo_menu: Undo/Redo 메뉴 버튼
    - self._menu_default_bg, self._menu_hover_bg: 메뉴 배경색
    - self._menu_last_hover: 메뉴 마지막 호버 상태
    - self.status: 상태 레이블
    """
    
    def _get_primary_selected_index(self):
        if not self.selected_row_indices:
            return None
        return min(self.selected_row_indices)

    # --------------------- JSON Editor Related Methods ---------------------
    def load_script_to_editor(self):
        from recording.save_events import migrate_txt_to_json as _migrate_txt_to_json
        
        path = filedialog.askopenfilename(filetypes=[('JSON Files','*.json'),('Text Files','*.txt')])
        if not path:
            return
        # if txt, try migrate
        if path.lower().endswith('.txt'):
            migrated = _migrate_txt_to_json(path)
            if not migrated:
                messagebox.showerror('오류', '마이그레이션 실패')
                return
            path = migrated
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror('오류', f'파일 읽기 실패: {e}')
            return
        # populate UI
        self._populate_editor_from_payload(data)
        self.current_editor_path = path
        self.btn_editor_save.config(state='normal')

    def _open_row_editor(self, index):
        # detailed modal editor for a single row (bigger params textbox)
        if index < 0 or index >= len(self.editor_rows):
            return
        row = self.editor_rows[index]
        t_val = row['t'].get().strip()
        type_val = row['type'].get().strip()
        params_val = row['params'].get().strip()

        modal = tk.Toplevel(self.root)
        modal.title('행 편집')
        modal.transient(self.root)
        modal.grab_set()

        tk.Label(modal, text='시간(ms)').grid(row=0, column=0, sticky='w')
        t_entry = tk.Entry(modal, width=20)
        t_entry.grid(row=0, column=1, sticky='we')
        t_entry.insert(0, t_val)

        tk.Label(modal, text='타입').grid(row=1, column=0, sticky='w')
        type_options = ['key_down', 'key_up', 'mouse_move', 'mouse_click', 'mouse_scroll', 'imgcheck', 'string']
        type_entry = ttk.Combobox(modal, values=type_options, width=37, state='normal')
        type_entry.grid(row=1, column=1, sticky='we')
        type_entry.set(type_val)

        tk.Label(modal, text='파라미터 (JSON 배열)').grid(row=2, column=0, sticky='nw')
        params_text = tk.Text(modal, width=80, height=12)
        params_text.grid(row=2, column=1, sticky='we')
        params_text.insert('1.0', params_val)

        # Store original type for comparison
        original_type = type_val

        def _on_type_change(event=None):
            """Fill default params when type changes and params are empty or type is different."""
            selected_type = type_entry.get().strip()
            current_params = params_text.get('1.0', 'end').strip()
            
            # Default parameters for each type
            defaults = {
                'key_down': '["a"]',
                'key_up': '["a"]',
                'mouse_move': '[100, 100]',
                'mouse_click': '["Button.left", "press", 100, 100]',
                'mouse_scroll': '[0, 1, 100, 100]',
                'imgcheck': '["img/template.png"]',
                'string': '["텍스트를 입력하세요"]'
            }
            
            # Fill default if params empty or type changed from original
            if selected_type in defaults:
                if not current_params or (selected_type != original_type and original_type):
                    params_text.delete('1.0', 'end')
                    params_text.insert('1.0', defaults[selected_type])

        # Bind type selection change
        type_entry.bind('<<ComboboxSelected>>', _on_type_change)

        def _save_and_close():
            self._push_snapshot('행 내용 수정')
            # write back to row entries
            row['t'].delete(0, tk.END)
            row['t'].insert(0, t_entry.get().strip())
            row['type'].delete(0, tk.END)
            row['type'].insert(0, type_entry.get().strip())
            txt = params_text.get('1.0', 'end').strip()
            row['params'].delete(0, tk.END)
            row['params'].insert(0, txt)
            self.btn_editor_save.config(state='normal')
            try:
                modal.grab_release()
            except Exception:
                pass
            modal.destroy()

        btn_frame = tk.Frame(modal)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(8,0))
        tk.Button(btn_frame, text='저장', width=10, command=_save_and_close).pack(side='left', padx=(0,6))
        tk.Button(btn_frame, text='취소', width=10, command=lambda: (modal.grab_release(), modal.destroy())).pack(side='left')
        t_entry.focus_set()

    def _update_editor_scrollregion(self, _event=None):
        bbox = self.editor_canvas.bbox('all')
        if bbox:
            self.editor_canvas.configure(scrollregion=bbox)

    def _sync_editor_canvas_width(self, event):
        # allow horizontal scrolling when content exceeds visible width
        try:
            req_width = self.editor_inner.winfo_reqwidth()
            new_width = max(req_width, event.width)
            self.editor_canvas.itemconfig(self.editor_inner_window, width=new_width)
        except Exception:
            pass

    def _on_mousewheel_editor(self, event):
        try:
            delta = int(-1 * (event.delta / 120))
        except Exception:
            delta = 0
        if delta:
            self.editor_canvas.yview_scroll(delta, 'units')
        return 'break'

    def _populate_editor_from_payload(self, data):
        # reset UI before filling
        self._clear_editor(skip_snapshot=True)

        # meta (merge file meta onto recording defaults)
        defaults = self._recording_meta_defaults()
        meta = defaults.copy()
        if isinstance(data, dict):
            try:
                meta.update(data.get('meta', {}) or {})
            except Exception:
                pass

        self.meta_version.delete(0, tk.END)
        self.meta_version.insert(0, meta.get('recorder_version', '') or '')
        self.meta_timestamp.delete(0, tk.END)
        self.meta_timestamp.insert(0, meta.get('timestamp', '') or '')
        self.meta_width.delete(0, tk.END)
        self.meta_width.insert(0, '' if meta.get('screen_width') is None else str(meta.get('screen_width')))
        self.meta_height.delete(0, tk.END)
        self.meta_height.insert(0, '' if meta.get('screen_height') is None else str(meta.get('screen_height')))
        
        # active window fields
        self.meta_active_title.delete(0, tk.END)
        self.meta_active_title.insert(0, meta.get('active_window_title', '') or '')
        self.meta_active_pid.delete(0, tk.END)
        self.meta_active_pid.insert(0, '' if meta.get('active_window_pid') is None else str(meta.get('active_window_pid')))
        self.meta_active_process.delete(0, tk.END)
        self.meta_active_process.insert(0, meta.get('active_process_name', '') or '')

        # events
        raw = data.get('events', data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            return
        for ev in raw:
            if isinstance(ev, dict):
                t_ms = ev.get('t_ms', 0)
                etype = ev.get('type', '')
                params = ev.get('params', [])
            else:
                # legacy list-format
                t_ms = int(ev[0])
                etype = ev[1]
                params = ev[2:]
            # show params as json text
            try:
                params_text = json.dumps(params, ensure_ascii=False)
            except Exception:
                params_text = str(params)
            self._add_editor_row((t_ms, etype, params_text), allow_snapshot=False, defer_regrid=True)
        self._regrid_all_rows()
        self.btn_editor_save.config(state='normal')

    def _add_editor_row(self, ev=None, insert_at=None, allow_snapshot=True, defer_regrid=False):
        """Add or insert a row. If insert_at is None, append to end."""
        if allow_snapshot:
            label = '행 삽입' if insert_at is not None else '행 추가'
            self._push_snapshot(label)
        if insert_at is None:
            idx = len(self.editor_rows)
        else:
            idx = insert_at
        t_val = ''
        type_val = ''
        params_val = ''
        if ev:
            t_val = str(ev[0])
            type_val = str(ev[1])
            params_val = str(ev[2])
        t_entry = tk.Entry(self.editor_inner, width=12)
        t_entry.insert(0, t_val)
        type_entry = tk.Entry(self.editor_inner, width=20)
        type_entry.insert(0, type_val)
        params_entry = tk.Entry(self.editor_inner, width=80)
        params_entry.insert(0, params_val)
        
        new_row = {'t': t_entry, 'type': type_entry, 'params': params_entry, '_bound': False}
        self._bind_row_events(new_row, idx)
        if insert_at is None:
            self.editor_rows.append(new_row)
        else:
            self.editor_rows.insert(insert_at, new_row)
        if not defer_regrid:
            self._regrid_all_rows()

    def _unbind_row_events(self, row):
        """Remove all event bindings from a row to prevent memory leaks."""
        try:
            for w in (row['t'], row['type'], row['params']):
                w.unbind('<KeyRelease>')
                w.unbind('<FocusIn>')
                w.unbind('<FocusOut>')
                w.unbind('<Button-1>')
                w.unbind('<B1-Motion>')
            row['params'].unbind('<Double-Button-1>')
        except Exception:
            pass

    def _bind_row_events(self, row, idx):
        # Skip if already bound to prevent duplicate handlers
        if row.get('_bound', False):
            return
        for w in (row['t'], row['type'], row['params']):
            w.bind('<KeyRelease>', lambda e, lbl='행 내용 수정': self._on_entry_change(e, lbl))
            w.bind('<FocusIn>', lambda e, lbl='행 내용 수정': self._on_entry_focus_in(e, lbl))
            w.bind('<FocusOut>', self._on_entry_focus_out)
            w.bind('<Button-1>', lambda e, i=idx: self._on_row_press(e, i))
            w.bind('<B1-Motion>', lambda e, i=idx: self._on_row_drag(e, i))
        row['params'].bind('<Double-Button-1>', lambda e, i=idx: self._open_row_editor(i))
        row['_bound'] = True

    def _on_row_press(self, event, index):
        """Handle row press with multi-selection (Ctrl-toggle, Shift-range)."""
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        if shift and self.selection_anchor is not None:
            start = min(self.selection_anchor, index)
            end = max(self.selection_anchor, index)
            self.selected_row_indices = set(range(start, end + 1))
        elif ctrl:
            if index in self.selected_row_indices:
                self.selected_row_indices.remove(index)
            else:
                self.selected_row_indices.add(index)
            self.selection_anchor = index
        else:
            self.selected_row_indices = {index}
            self.selection_anchor = index
        self._update_row_selection_display()
        # ensure this row has focus for keyboard shortcuts
        try:
            self.editor_inner.focus_set()
        except Exception:
            pass

    def _on_row_drag(self, event, index):
        """Drag selection: extend range from anchor to current row while dragging."""
        if self.selection_anchor is None:
            self.selection_anchor = index
        start = min(self.selection_anchor, index)
        end = max(self.selection_anchor, index)
        self.selected_row_indices = set(range(start, end + 1))
        self._update_row_selection_display()

    def _push_snapshot(self, label='변경', state=None):
        # 임시: 되돌리기/다시하기 비활성화 시 스냅샷 저장 안 함
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return
        if self._restoring_editor_state:
            return
        snap_state = state if state is not None else self._capture_editor_state()
        if snap_state is None:
            return
        self._undo_stack.append({'state': snap_state, 'label': label or '변경'})
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._refresh_history_menus()

    def _refresh_history_menus(self):
        # 임시: 메뉴 전체 비활성화 표시
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            try:
                self.undo_menu.delete(0, 'end')
                self.undo_menu.add_command(label='비활성화됨(테스트)', state='disabled')
                self.btn_undo.config(state='disabled')
                self.btn_undo_menu.config(state='disabled')
            except Exception:
                pass
            try:
                self.redo_menu.delete(0, 'end')
                self.redo_menu.add_command(label='비활성화됨(테스트)', state='disabled')
                self.btn_redo.config(state='disabled')
                self.btn_redo_menu.config(state='disabled')
            except Exception:
                pass
            return
        self._reset_menu_highlight(self.undo_menu, 'undo')
        self._reset_menu_highlight(self.redo_menu, 'redo')
        try:
            self.undo_menu.delete(0, 'end')
            if not self._undo_stack:
                self.undo_menu.add_command(label='기록 없음', state='disabled')
            else:
                for idx, entry in enumerate(reversed(self._undo_stack)):
                    steps = idx + 1
                    lbl = f'{steps}단계: {entry.get("label", "변경")}'
                    self.undo_menu.add_command(label=lbl, command=lambda c=steps: self._undo_editor(count=c))
        except Exception:
            pass
        try:
            self.redo_menu.delete(0, 'end')
            if not self._redo_stack:
                self.redo_menu.add_command(label='기록 없음', state='disabled')
            else:
                for idx, entry in enumerate(reversed(self._redo_stack)):
                    steps = idx + 1
                    lbl = f'{steps}단계: {entry.get("label", "변경")}'
                    self.redo_menu.add_command(label=lbl, command=lambda c=steps: self._redo_editor(count=c))
        except Exception:
            pass

    def _reset_menu_highlight(self, menu, key=None):
        try:
            end = menu.index('end')
            if end is None:
                return
            for i in range(end + 1):
                menu.entryconfig(i, background=self._menu_default_bg)
            if key:
                self._menu_last_hover[key] = None
                try:
                    menu.selection_clear(0, 'end')
                except Exception:
                    pass
        except Exception:
            pass

    def _on_history_menu_hover(self, menu, stack, key):
        try:
            idx = menu.index('active')
        except Exception:
            idx = None
        # 기록없음 상태이거나 비활성화된 항목이면 아무 동작 안함
        if idx is None or not stack:
            return
        # 항목이 disabled 상태인지 확인
        try:
            state = menu.entrycget(idx, 'state')
            if state == 'disabled':
                return
        except Exception:
            pass
        if self._menu_last_hover.get(key) == idx:
            return
        self._reset_menu_highlight(menu, key)
        try:
            for i in range(idx + 1):
                menu.entryconfig(i, background=self._menu_hover_bg)
            self._menu_last_hover[key] = idx
        except Exception:
            pass

    def _on_entry_focus_in(self, _event=None, label='행 내용 수정'):
        if self._restoring_editor_state:
            return
        if self._edit_baseline_state is None:
            self._edit_baseline_state = self._capture_editor_state()
            self._edit_baseline_label = label
            self._edit_baseline_committed = False

    def _on_entry_change(self, _event=None, label='행 내용 수정'):
        self.btn_editor_save.config(state='normal')
        if self._restoring_editor_state:
            return
        if self._edit_baseline_state is not None and not self._edit_baseline_committed:
            label_to_use = self._edit_baseline_label or label
            self._push_snapshot(label_to_use, state=self._edit_baseline_state)
            self._edit_baseline_committed = True

    def _on_entry_focus_out(self, _event=None):
        self._edit_baseline_state = None
        self._edit_baseline_label = ''
        self._edit_baseline_committed = False

    def _capture_editor_state(self):
        try:
            meta = {
                'recorder_version': self.meta_version.get().strip(),
                'timestamp': self.meta_timestamp.get().strip(),
                'screen_width': self.meta_width.get().strip(),
                'screen_height': self.meta_height.get().strip(),
            }
            events = []
            for r in self.editor_rows:
                ttxt = r['t'].get().strip()
                typ = r['type'].get().strip()
                ptxt = r['params'].get().strip()
                events.append({'t_ms': ttxt, 'type': typ, 'params': ptxt})
            return {'meta': meta, 'events': events}
        except Exception:
            return None

    def _restore_editor_state(self, state):
        if not state:
            return
        self._on_entry_focus_out()
        self._restoring_editor_state = True
        try:
            self._clear_editor(skip_snapshot=True)
            meta = state.get('meta', {}) or {}
            try:
                self.meta_version.insert(0, meta.get('recorder_version', ''))
                self.meta_timestamp.insert(0, meta.get('timestamp', ''))
                self.meta_width.insert(0, meta.get('screen_width', ''))
                self.meta_height.insert(0, meta.get('screen_height', ''))
            except Exception:
                pass
            events = state.get('events', []) or []
            for ev in events:
                try:
                    t_ms = ev.get('t_ms', '')
                    typ = ev.get('type', '')
                    params = ev.get('params', '')
                    self._add_editor_row((t_ms, typ, params), allow_snapshot=False, defer_regrid=True)
                except Exception:
                    pass
            self._regrid_all_rows()
            self.btn_editor_save.config(state='normal')
        finally:
            self._restoring_editor_state = False
            self._update_row_selection_display()

    def _undo_editor(self, event=None, count=1):
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return 'break'
        if not self._undo_stack:
            return 'break'
        steps = min(max(1, count), len(self._undo_stack))
        # 현재 상태 저장
        cur = self._capture_editor_state()
        # 모든 단계를 pop하고 redo 스택에 push
        final_state = None
        for i in range(steps):
            entry = self._undo_stack.pop()
            if i == 0 and cur:  # 처음에만 현재 상태 저장
                self._redo_stack.append({'state': cur, 'label': entry.get('label', '변경')})
                if len(self._redo_stack) > 10:
                    self._redo_stack.pop(0)
            else:
                self._redo_stack.append({'state': entry.get('state'), 'label': entry.get('label', '변경')})
                if len(self._redo_stack) > 10:
                    self._redo_stack.pop(0)
            final_state = entry.get('state')
        # 최종 상태로 한 번만 restore
        if final_state:
            self._restore_editor_state(final_state)
        self._refresh_history_menus()
        return 'break'

    def _redo_editor(self, event=None, count=1):
        if globals().get('DID_DISABLE_UNDO_REDO_ONCE', False):
            return 'break'
        if not self._redo_stack:
            return 'break'
        steps = min(max(1, count), len(self._redo_stack))
        # 현재 상태 저장
        cur = self._capture_editor_state()
        # 모든 단계를 pop하고 undo 스택에 push
        final_state = None
        for i in range(steps):
            entry = self._redo_stack.pop()
            if i == 0 and cur:  # 처음에만 현재 상태 저장
                self._undo_stack.append({'state': cur, 'label': entry.get('label', '변경')})
                if len(self._undo_stack) > 10:
                    self._undo_stack.pop(0)
            else:
                self._undo_stack.append({'state': entry.get('state'), 'label': entry.get('label', '변경')})
                if len(self._undo_stack) > 10:
                    self._undo_stack.pop(0)
            final_state = entry.get('state')
        # 최종 상태로 한 번만 restore
        if final_state:
            self._restore_editor_state(final_state)
        self._refresh_history_menus()
        return 'break'

    def _update_row_selection_display(self):
        for i, r in enumerate(self.editor_rows):
            bg = 'lightyellow' if i in self.selected_row_indices else 'white'
            for w in (r['t'], r['type'], r['params']):
                try:
                    w.config(bg=bg)
                except Exception:
                    pass
        try:
            # keep selection visible after updates
            self.editor_canvas.update_idletasks()
        except Exception:
            pass

    def _regrid_all_rows(self):
        """Re-grid all rows after insert or delete."""
        for i, r in enumerate(self.editor_rows):
            r['t'].grid(row=i, column=0, sticky='we')
            r['type'].grid(row=i, column=1, sticky='we')
            r['params'].grid(row=i, column=2, sticky='we')
            # Unbind and rebind with correct index to update event handlers
            self._unbind_row_events(r)
            r['_bound'] = False
            self._bind_row_events(r, i)
        self._update_row_selection_display()
        try:
            self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox('all'))
        except Exception:
            pass

    def _insert_row_after_selected(self):
        """Insert a new empty row after the selected row."""
        target = self._get_primary_selected_index()
        if target is None:
            messagebox.showinfo('정보', '먼저 행을 클릭하여 선택하세요.')
            return
        self._push_snapshot('행 삽입')
        insert_pos = target + 1
        self._add_editor_row(ev=None, insert_at=insert_pos, allow_snapshot=False)
        self.btn_editor_save.config(state='normal')

    def _add_time_offset(self):
        """Add time offset (ms) to all rows after the selected row."""
        target = self._get_primary_selected_index()
        if target is None:
            messagebox.showinfo('정보', '먼저 기준이 될 행을 클릭하여 선택하세요.')
            return
        offset_str = tk.simpledialog.askstring('시간 추가', '추가할 시간(ms)을 입력하세요:', parent=self.root)
        if not offset_str:
            return
        try:
            offset_ms = int(float(offset_str))
        except Exception:
            messagebox.showerror('오류', '유효한 숫자를 입력하세요.')
            return
        # add offset to all rows after selected
        self._push_snapshot('시간 오프셋 추가')
        for i in range(target + 1, len(self.editor_rows)):
            r = self.editor_rows[i]
            try:
                current_t = int(float(r['t'].get().strip()))
                new_t = current_t + offset_ms
                r['t'].delete(0, tk.END)
                r['t'].insert(0, str(new_t))
            except Exception:
                pass
        self.btn_editor_save.config(state='normal')
        messagebox.showinfo('완료', f'선택된 행({target}) 이후의 {len(self.editor_rows) - target - 1}개 행에\n{offset_ms}ms가 추가되었습니다.')

    def _remove_editor_row(self, index, allow_snapshot=True, defer_regrid=False):
        if index < 0 or index >= len(self.editor_rows):
            return
        if allow_snapshot:
            self._push_snapshot('행 삭제')
        row = self.editor_rows.pop(index)
        try:
            # Unbind events before destroying to prevent memory leaks
            self._unbind_row_events(row)
            row['t'].destroy()
            row['type'].destroy()
            row['params'].destroy()
        except Exception:
            pass
        if not defer_regrid:
            self._regrid_all_rows()
        self.btn_editor_save.config(state='normal')

    def _delete_selected_row(self):
        """Delete the currently selected row in the JSON editor."""
        if not self.selected_row_indices:
            messagebox.showinfo('정보', '삭제할 행을 먼저 선택하세요.')
            return
        # delete in descending order to keep indices valid
        label = f'선택 행 삭제 ({len(self.selected_row_indices)}개)'
        self._push_snapshot(label)
        indices = sorted(self.selected_row_indices, reverse=True)
        for idx in indices:
            self._remove_editor_row(idx, allow_snapshot=False, defer_regrid=True)
        self._regrid_all_rows()
        self.selected_row_indices = set()
        self.selection_anchor = None
        self._update_row_selection_display()
        self.btn_editor_save.config(state='normal')

    def _clear_editor(self, skip_snapshot=False):
        if not skip_snapshot:
            self._push_snapshot('초기화')
        self._on_entry_focus_out()
        for r in list(self.editor_rows):
            try:
                r['t'].destroy()
                r['type'].destroy()
                r['params'].destroy()
            except Exception:
                pass
        self.editor_rows = []
        self.selected_row_indices = set()
        self.selection_anchor = None
        self.meta_version.delete(0, tk.END)
        self.meta_timestamp.delete(0, tk.END)
        self.meta_width.delete(0, tk.END)
        self.meta_height.delete(0, tk.END)
        self.meta_active_title.delete(0, tk.END)
        self.meta_active_pid.delete(0, tk.END)
        self.meta_active_process.delete(0, tk.END)
        self.btn_editor_save.config(state='disabled')

    def save_edited_script(self):
        # ask for path
        try:
            fpath = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON Files','*.json')], initialfile='edited_recording.json')
        except Exception:
            fpath = None
        if not fpath:
            return
        # gather meta (align with recording default format)
        meta = self._recording_meta_defaults()
        user_version = self.meta_version.get().strip()
        if user_version:
            meta['recorder_version'] = user_version
        user_ts = self.meta_timestamp.get().strip()
        if user_ts:
            meta['timestamp'] = user_ts
        # width/height fall back to defaults if blank or invalid
        def _parse_int(val):
            s = val.strip()
            if not s:
                return None
            try:
                return int(s)
            except Exception:
                return None
        w = _parse_int(self.meta_width.get())
        h = _parse_int(self.meta_height.get())
        if w is not None:
            meta['screen_width'] = w
        if h is not None:
            meta['screen_height'] = h
        
        # active window fields
        active_title = self.meta_active_title.get().strip()
        if active_title:
            meta['active_window_title'] = active_title
        active_pid = _parse_int(self.meta_active_pid.get())
        if active_pid is not None:
            meta['active_window_pid'] = active_pid
        active_process = self.meta_active_process.get().strip()
        if active_process:
            meta['active_process_name'] = active_process
        
        # reflect resolved meta back to UI
        try:
            self.meta_version.delete(0, tk.END)
            self.meta_version.insert(0, meta.get('recorder_version', ''))
            self.meta_timestamp.delete(0, tk.END)
            self.meta_timestamp.insert(0, meta.get('timestamp', ''))
            self.meta_width.delete(0, tk.END)
            self.meta_width.insert(0, '' if meta.get('screen_width') is None else str(meta.get('screen_width')))
            self.meta_height.delete(0, tk.END)
            self.meta_height.insert(0, '' if meta.get('screen_height') is None else str(meta.get('screen_height')))
            self.meta_active_title.delete(0, tk.END)
            self.meta_active_title.insert(0, meta.get('active_window_title', '') or '')
            self.meta_active_pid.delete(0, tk.END)
            self.meta_active_pid.insert(0, '' if meta.get('active_window_pid') is None else str(meta.get('active_window_pid')))
            self.meta_active_process.delete(0, tk.END)
            self.meta_active_process.insert(0, meta.get('active_process_name', '') or '')
        except Exception:
            pass
        # events
        events = []
        for r in self.editor_rows:
            ttxt = r['t'].get().strip()
            typ = r['type'].get().strip()
            ptxt = r['params'].get().strip()
            try:
                t_ms = int(float(ttxt))
            except Exception:
                t_ms = 0
            # parse params: try json.loads, fallback to '|' split
            params = None
            try:
                params = json.loads(ptxt) if ptxt else []
                if not isinstance(params, list):
                    params = [params]
            except Exception:
                # fallback split
                parts = [p.strip() for p in ptxt.split('|')] if ptxt else []
                # try to convert numeric
                def conv(x):
                    if x == '':
                        return ''
                    try:
                        if '.' in x:
                            return float(x)
                        else:
                            return int(x)
                    except Exception:
                        return x
                params = [conv(p) for p in parts]
            events.append({'t_ms': t_ms, 'type': typ, 'params': params})
        payload = {'meta': meta, 'events': events}
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('저장 완료', f'파일을 저장했습니다: {fpath}')
            self.status.config(text=f'저장: {fpath}')
            self.btn_editor_save.config(state='disabled')
            self.current_editor_path = fpath
        except Exception as e:
            messagebox.showerror('저장 실패', f'파일 저장 실패: {e}')

    # --------------------- end JSON Editor ---------------------
