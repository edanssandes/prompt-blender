import wx
import wx.stc
import json


class PromptPage(wx.Panel):
    DEBOUNCE_INTERVAL = 250  # Waits this amount of milliseconds after the last text change before updating the prompt data.

    def __init__(self, parent, data, prompt_name, on_change=None):
        super(PromptPage, self).__init__(parent)
        #self.SetBackgroundColour(wx.Colour(255, 1, 1))

        self.prompt_name = prompt_name
        self.data = data
        self.view_mode = 0
        self.missing_variables = False
        self.disabled = False
        self.on_change = on_change
        self.highlighted_text = ""

        # Debounce timer for text changes
        self.debounce_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounce_timer, self.debounce_timer)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # TextCtrl para a edição do prompt
        self.prompt_editor = wx.stc.StyledTextCtrl(self)
        self.prompt_editor.SetLexer(wx.stc.STC_LEX_NULL)
        self.style_map = {}
        self.next_style = 1

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

        self.prompt_editor.StyleResetDefault()
        self.prompt_editor.SetBackgroundColour(bg_color)
        for margin in range(5):
            self.prompt_editor.SetMarginBackground(margin, bg_color)
        self.prompt_editor.StyleSetBackground(0, bg_color)
        self.prompt_editor.StyleSetForeground(0, wx.BLACK)

        self.prompt_editor.SetText(text)

        # Apply syntax highlighting
        if text and self.view_mode != 2:
            self.highlight_prompt()

        self.prompt_editor.SetEditable(self.view_mode == 0)

        self.prompt_editor.Thaw()

    def highlight_prompt(self):

        text = self.prompt_editor.GetText()
        if text == self.highlighted_text:
            return  # No changes, skip highlighting
        
        self.highlighted_text = text

        highlight_positions = self.data.get_hightlight_positions(prompt_name=self.prompt_name, interpolated=(self.view_mode==1))
        self.missing_variables = False

        # Background color for the prompt editor
        bg_color = self.prompt_editor.GetBackgroundColour()

        # Reset all styling to default
        self.prompt_editor.StartStyling(0)
        self.prompt_editor.SetStyling(self.prompt_editor.GetTextLength(), 0)

        # Convert text to bytes for byte positions
        text_bytes = text.encode('utf-8')

        # Aplicar coloração ao texto
        for var_name, start, end in highlight_positions:
            # Convert character positions to byte positions
            byte_start = len(text[:start].encode('utf-8'))
            byte_end = len(text[:end].encode('utf-8'))
            
            color = self.data.get_variable_colors(var_name)
            if color is not None:
                if color not in self.style_map:
                    style_num = self.next_style
                    self.next_style += 1
                    self.style_map[color] = style_num
                    self.prompt_editor.StyleSetForeground(style_num, color)
                    self.prompt_editor.StyleSetBackground(style_num, bg_color)
                else:
                    style_num = self.style_map[color]
                self.prompt_editor.StartStyling(byte_start)
                self.prompt_editor.SetStyling(byte_end - byte_start, style_num)
            else:
                self.missing_variables = True
                if 'missing' not in self.style_map:
                    style_num = self.next_style
                    self.next_style += 1
                    self.style_map['missing'] = style_num
                    self.prompt_editor.StyleSetForeground(style_num, wx.YELLOW)
                    self.prompt_editor.StyleSetBackground(style_num, wx.RED)
                else:
                    style_num = self.style_map['missing']
                self.prompt_editor.StartStyling(byte_start)
                self.prompt_editor.SetStyling(byte_end - byte_start, style_num)

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
        
        self.prompt_editor.StyleSetSize(0, font_size)

        # Refresh the editor to apply changes
        self.refresh()



class PromptEditorDropTarget(wx.TextDropTarget):
    def __init__(self, text_ctrl):
        wx.TextDropTarget.__init__(self)
        self.text_ctrl = text_ctrl

    def OnDropText(self, x, y, dropped_text):
        # Only allow dropping if the text control is editable
        if not self.text_ctrl.IsEditable():
            return False

        # Get the insertion position from coordinates
        drop_pos = self._get_char_position(x, y)

        # Store original text for cleanup
        original_text = self.text_ctrl.GetText()

        # Don't insert text directly here! wx.TextDropTarget has default behavior that
        # automatically inserts the dragged text after OnDropText returns. To prevent
        # duplicate text insertion, we use CallAfter to perform our insertion after
        # the default behavior completes, then overwrites up any unwanted drag and drop 
        # text that was inserted by default.
        wx.CallAfter(self._insert_drop, original_text, drop_pos, dropped_text)

        return True

    def _get_char_position(self, x, y):
        """Convert screen coordinates to character position in text"""
        byte_pos = self.text_ctrl.PositionFromPoint(wx.Point(x, y))

        if byte_pos == -1:
            return self.text_ctrl.GetCurrentPos()

        # Convert byte position to character position
        text = self.text_ctrl.GetText()
        text_bytes = text.encode('utf-8')
        char_pos = len(text_bytes[:byte_pos].decode('utf-8'))

        return char_pos

    def _insert_drop(self, original_text, drop_pos, variable_text):
        expected_text = original_text[:drop_pos] + variable_text + original_text[drop_pos:]

        self.text_ctrl.SetText(expected_text)
        new_char_pos = drop_pos + len(variable_text)
        # Convert character position to byte position
        byte_pos = len(expected_text[:new_char_pos].encode('utf-8'))
        self.text_ctrl.SetCurrentPos(byte_pos)
        self.text_ctrl.SetFocus()        