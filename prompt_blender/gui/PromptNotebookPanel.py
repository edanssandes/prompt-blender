import wx
import wx.stc
import json
from prompt_blender.gui import placeholder_colors
from prompt_blender.gui.dialogs.JsonWizardDialog import JsonWizardDialog, json_to_fields


class PromptPage(wx.Panel):
    DEBOUNCE_INTERVAL = 250  # Waits this amount of milliseconds after the last text change before updating the prompt data.

    def __init__(self, parent, data, prompt_name, on_change=None):
        super(PromptPage, self).__init__(parent)

        self.prompt_name = prompt_name
        self.data = data
        self.view_mode = 0
        self.missing_variables = False
        self.disabled = False
        self.on_change = on_change
        self.highlighted_text = ""
        self.style_map = {}

        # Debounce timer for text changes
        self.debounce_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounce_timer, self.debounce_timer)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # TextCtrl para a edição do prompt
        self.prompt_editor = wx.stc.StyledTextCtrl(self)
        self.prompt_editor.SetMarginType(1, wx.stc.STC_MARGIN_NUMBER)
        self.prompt_editor.SetMarginWidth(1, 36)
        # Wrap long lines
        self.prompt_editor.SetWrapMode(wx.stc.STC_WRAP_WORD)

        self.setup_styles()
        
        # Set up drag and drop for the prompt editor
        drop_target = PromptEditorDropTarget(self.prompt_editor)
        self.prompt_editor.SetDropTarget(drop_target)

        # Bind text change event
        def on_prompt_change(event):
            if self.view_mode == 0:
                # Start/restart debounce timer
                self.debounce_timer.Stop()
                self.debounce_timer.StartOnce(PromptPage.DEBOUNCE_INTERVAL)

        self.prompt_editor.Bind(wx.stc.EVT_STC_CHANGE, on_prompt_change)

        # Custom right-click context menu (with JSON wizard options)
        self.prompt_editor.UsePopUp(wx.stc.STC_POPUP_NEVER)
        self.prompt_editor.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        # Set up layout
        sizer.Add(self.prompt_editor, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.refresh()

    def _on_debounce_timer(self, event):
        """Called after some time of no text changes to update prompt and highlight. This reduce flickering. """
        if self.view_mode == 0:
            self.data.set_prompt(self.prompt_name, self.prompt_editor.GetText())
            self.highlight_prompt()
        if self.on_change:
            self.on_change()

    # --- Context menu / JSON wizard -------------------------------------
    ID_JSON_EDIT = wx.NewIdRef()
    ID_JSON_INSERT = wx.NewIdRef()

    def _on_context_menu(self, event):
        editor = self.prompt_editor
        editable = editor.IsEditable()
        has_sel = not editor.GetSelectionEmpty()

        menu = wx.Menu()

        # Reuse the standard editor actions, then append our new JSON items.
        items = [
            (wx.ID_UNDO, "Undo", lambda e: editor.Undo(), editable and editor.CanUndo()),
            (wx.ID_REDO, "Redo", lambda e: editor.Redo(), editable and editor.CanRedo()),
            (None, None, None, None),  # separator
            (wx.ID_CUT, "Cut", lambda e: editor.Cut(), editable and has_sel),
            (wx.ID_COPY, "Copy", lambda e: editor.Copy(), has_sel),
            (wx.ID_PASTE, "Paste", lambda e: editor.Paste(), editable and editor.CanPaste()),
            (wx.ID_DELETE, "Delete", lambda e: editor.Clear(), editable and has_sel),   
            (None, None, None, None),  # separator
            (wx.ID_SELECTALL, "Select All", lambda e: editor.SelectAll(), True),
            (None, None, None, None),  # separator
            (self.ID_JSON_EDIT, "Edit JSON as Table...", self._on_edit_json, editable and has_sel),
            (self.ID_JSON_INSERT, "Insert JSON as Table...", self._on_insert_json, editable),
        ]
        for item_id, label, handler, enabled in items:
            if item_id is None:
                menu.AppendSeparator()
                continue
            item = menu.Append(item_id, label)
            item.Enable(enabled)
            menu.Bind(wx.EVT_MENU, handler, item)

        editor.PopupMenu(menu)
        menu.Destroy()

    def _on_edit_json(self, event):
        editor = self.prompt_editor
        selected = editor.GetSelectedText()
        try:
            fields, multiple = json_to_fields(selected)
        except ValueError as exc:
            wx.MessageBox(
                f"The selected text could not be parsed as a JSON object.\n\n{exc}",
                "Edit JSON as Table", wx.OK | wx.ICON_WARNING)
            return

        dialog = JsonWizardDialog(self, fields=fields, multiple=multiple,
                                  title="Edit JSON as Table")
        try:
            if dialog.ShowModal() == wx.ID_OK:
                if wx.MessageBox("Replace the selected text with the new JSON?",
                                 "Replace Text",
                                 wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
                    return
                editor.ReplaceSelection(dialog.GetJson())
                self._commit_text_change()
        finally:
            dialog.Destroy()

    def _on_insert_json(self, event):
        editor = self.prompt_editor
        dialog = JsonWizardDialog(self, title="Insert JSON as Table")
        try:
            if dialog.ShowModal() == wx.ID_OK:
                editor.ReplaceSelection(dialog.GetJson())
                self._commit_text_change()
        finally:
            dialog.Destroy()

    def _commit_text_change(self):
        """Persist editor content after a programmatic edit and refresh highlight."""
        if self.view_mode == 0:
            self.data.set_prompt(self.prompt_name, self.prompt_editor.GetText())
            self.highlighted_text = ""
            self.highlight_prompt()
        if self.on_change:
            self.on_change()

    def setup_styles(self, default_bg_color=wx.Colour(255, 255, 255), default_fg_color=wx.Colour(0, 255, 0)):
        """Set up styles for the prompt editor based on current variable colors."""

        self.prompt_editor.StyleSetBackground(wx.stc.STC_STYLE_DEFAULT, default_bg_color)
        self.prompt_editor.StyleSetForeground(wx.stc.STC_STYLE_DEFAULT, default_fg_color)
        self.prompt_editor.StyleClearAll()

        self.prompt_editor.StyleSetBackground(wx.stc.STC_STYLE_LINENUMBER, wx.Colour(230, 230, 230))
        self.prompt_editor.StyleSetForeground(wx.stc.STC_STYLE_LINENUMBER, wx.Colour(150, 150, 150))

        self.style_map = {}

        style_id = 1
        self.style_map['missing'] = style_id
        self.prompt_editor.StyleSetForeground(style_id, wx.YELLOW)
        self.prompt_editor.StyleSetBackground(style_id, wx.RED)


        for color_id, color in enumerate(placeholder_colors):
            style_id += 1
            self.prompt_editor.StyleSetForeground(style_id, color)
            self.style_map[color_id] = style_id


        if self.view_mode == 2:
            self.prompt_editor.SetLexer(wx.stc.STC_LEX_JSON)
        else:
            self.prompt_editor.SetLexer(wx.stc.STC_LEX_NULL)


    def SetValue(self, text):
        self.prompt_editor.Freeze()

        # Set background color and text based on view mode
        if self.view_mode == 0:  # Edit mode
            if self.is_disabled():
                bg_color = wx.Colour(240, 240, 240)
            else:
                bg_color = wx.Colour(255, 255, 255)
        elif self.view_mode == 1:  # View prompt mode
            bg_color = wx.Colour(200, 200, 200)
        else:  # Debug cache mode
            if not text:
                bg_color = wx.Colour(200, 200, 180)
            else:
                bg_color = wx.Colour(180, 255, 180)

        #self.prompt_editor.StyleResetDefault()

        self.setup_styles(default_bg_color=bg_color, default_fg_color=wx.BLACK)

        self.prompt_editor.SetEditable(True)  # Make editable to set text
        self.prompt_editor.SetValue(text or "")
        self.prompt_editor.SetEditable(self.view_mode == 0)

        # Apply syntax highlighting
        if text and self.view_mode != 2:
            self.highlight_prompt()

        self.prompt_editor.Thaw()

    def highlight_prompt(self):
        text = self.prompt_editor.GetText()
        if text == self.highlighted_text:
            return  # No changes, skip highlighting
        
        self.highlighted_text = text

        highlight_positions = self.data.get_hightlight_positions(prompt_name=self.prompt_name, interpolated=(self.view_mode==1))
        self.missing_variables = False

        # Background color for the prompt editor
        bg_color = self.prompt_editor.StyleGetBackground(wx.stc.STC_STYLE_DEFAULT)

        # Convert text to bytes for byte positions
        text_bytes = text.encode('utf-8')

        # Reset all styling to default
        self.prompt_editor.StartStyling(0)
        self.prompt_editor.SetStyling(len(text_bytes), 0)

        # Aplicar coloração ao texto
        for var_name, start, end in highlight_positions:
            # Convert character positions to byte positions
            byte_start = len(text[:start].encode('utf-8'))
            byte_end = len(text[:end].encode('utf-8'))
            
            color_id = self.data.get_variable_colors(var_name)
            if color_id is not None:
                self.prompt_editor.StartStyling(byte_start)
                self.prompt_editor.SetStyling(byte_end - byte_start, self.style_map[color_id % len(placeholder_colors)])
            else:
                self.missing_variables = True
                self.prompt_editor.StartStyling(byte_start)
                self.prompt_editor.SetStyling(byte_end - byte_start, self.style_map['missing'])

    def refresh(self):
        #Lock the prompt editor if the view checkbox is checked
        if self.view_mode == 0:
            text = self.data.get_prompt(self.prompt_name)
        elif self.view_mode == 1:
            text = self.data.get_interpolated_prompt(self.prompt_name)
        elif self.view_mode == 2:
            text = self.data.get_result(self.prompt_name, self.output_dir, self.run_hashes)

            # Try format the text as json, with identation. Otherwise, just show the text
            try:
                text = json.dumps(json.loads(text), indent=4)
            except:
                pass
        else:
            text = "?"  # Should never happen

        self.highlighted_text = ""  # Force re-highlighting
        self.SetValue(text)

    @property
    def title(self):
        return self.prompt_name

    @title.setter
    def title(self, value):
        self.prompt_name = value

    def is_disabled(self):
        return self.disabled

    def set_disabled(self, value):
        self.disabled = value

    def set_zoom(self, zoom_percentage):
        """Set the zoom level for the prompt editor font"""
        base_font_size = 10  # Default font size
        font_size = int(base_font_size * zoom_percentage / 100.0)
        
        self.prompt_editor.SetZoom((zoom_percentage - 100)//15)

        # Refresh the editor to apply changes
        self.refresh()



class PromptEditorDropTarget(wx.TextDropTarget):
    def __init__(self, prompt_editor):
        wx.TextDropTarget.__init__(self)
        self.prompt_editor = prompt_editor

    def OnDropText(self, x, y, dropped_text):
        """Handle drag and drop text insertion."""
        if not self.prompt_editor.IsEditable():
            return False

        # StyledTextCtrl positions are byte offsets; InsertText, SetCurrentPos
        # and SetSelection all expect byte positions, so work entirely in bytes.
        byte_pos = self.prompt_editor.PositionFromPoint(wx.Point(x, y))
        if byte_pos == -1:
            byte_pos = self.prompt_editor.GetCurrentPos()

        self.prompt_editor.InsertText(byte_pos, dropped_text)
        end_pos = byte_pos + len(dropped_text.encode('utf-8'))
        self.prompt_editor.SetSelection(end_pos, end_pos)
        self.prompt_editor.SetFocus()

        return False
       