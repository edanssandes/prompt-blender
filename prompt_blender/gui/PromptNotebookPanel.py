import wx
import json


class PromptPage(wx.Panel):
    def __init__(self, parent, data, prompt_name):
        super(PromptPage, self).__init__(parent)
        self.SetBackgroundColour(wx.Colour(255, 1, 1))

        self.prompt_name = prompt_name
        self.data = data
        self.view_mode = 0
        self.missing_variables = False
        self.disabled = False

        # Sizer para o layout da página
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Create a panel to hold the text editor and overlay label
        editor_panel = wx.Panel(self)
        editor_sizer = wx.BoxSizer(wx.VERTICAL)

        # TextCtrl para a edição do prompt
        self.prompt_editor = wx.TextCtrl(editor_panel, style=wx.TE_MULTILINE | wx.TE_RICH2)
        # Set Hint
        self.prompt_editor.SetHint("Insert prompt text here...")

        # Create character count label with transparent background
        self.char_count_label = wx.StaticText(editor_panel, label="0 chars")
        font = self.char_count_label.GetFont()
        font.SetPointSize(8)  # Small font
        self.char_count_label.SetFont(font)
        self.char_count_label.SetForegroundColour(wx.Colour(128, 128, 128))  # Gray color
        self.char_count_label.SetBackgroundColour(wx.Colour(255, 255, 255, 0))  # Transparent background


        # Position the label in bottom-right corner
        editor_sizer.Add(self.prompt_editor, 1, wx.EXPAND)
        editor_panel.SetSizer(editor_sizer)

        # Bind resize event to reposition label
        def on_resize(event):
            self.position_char_count_label()
            event.Skip()

        editor_panel.Bind(wx.EVT_SIZE, on_resize)

        # Set up drag and drop for the prompt editor
        drop_target = PromptEditorDropTarget(self.prompt_editor)
        self.prompt_editor.SetDropTarget(drop_target)

        # Bind text change event
        def on_prompt_change(event):
            if self.view_mode == 0:
                self.data.set_prompt(self.prompt_name, self.prompt_editor.GetValue())
                self.highlight_prompt()
            self.update_char_count()

        self.prompt_editor.Bind(wx.EVT_TEXT, on_prompt_change)

        # Set up layout
        sizer.Add(editor_panel, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Initial positioning of the label
        wx.CallAfter(self.position_char_count_label)

        self.refresh()



    def SetValue(self, text):
        self.prompt_editor.Freeze()

        # Set background color and text based on view mode
        if self.view_mode == 0:  # Edit mode
            if self.is_disabled():
                self.prompt_editor.SetBackgroundColour(wx.Colour(240, 240, 240))
            else:
                self.prompt_editor.SetBackgroundColour(wx.Colour(255, 255, 255))
            self.prompt_editor.SetValue(text)
        elif self.view_mode == 1:  # View prompt mode
            self.prompt_editor.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.prompt_editor.SetValue(text)
        else:  # Debug cache mode
            if not text:
                self.prompt_editor.SetBackgroundColour(wx.Colour(200, 200, 180))
                self.prompt_editor.SetValue("")
            else:
                self.prompt_editor.SetBackgroundColour(wx.Colour(180, 255, 180))
                self.prompt_editor.SetValue(text)

        # Apply syntax highlighting
        if text and self.view_mode != 2:
            self.highlight_prompt()

        self.prompt_editor.SetEditable(self.view_mode == 0)

        # Update character count
        self.update_char_count()

        self.prompt_editor.Thaw()

    def highlight_prompt(self):
        highlight_positions = self.data.get_hightlight_positions(prompt_name=self.prompt_name, interpolated=(self.view_mode==1))
        self.missing_variables = False

        # Background color for the prompt editor
        bg_color = self.prompt_editor.GetBackgroundColour()

        # Remove all foreground and background colors
        self.prompt_editor.SetStyle(0, self.prompt_editor.GetLastPosition(), wx.TextAttr(wx.BLACK, bg_color))



        # Aplicar coloração ao texto
        for var_name, start, end in highlight_positions:
            color = self.data.get_variable_colors(var_name)
            if color is not None:
                self.prompt_editor.SetStyle(start, end, wx.TextAttr(color))
            else:
                self.missing_variables = True
                self.prompt_editor.SetStyle(start, end, wx.TextAttr(wx.YELLOW, wx.RED))

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

    def position_char_count_label(self):
        """Position the character count label in the bottom-right corner of the text editor"""
        if not hasattr(self, 'char_count_label'):
            return
        
        # if component has been destroyed, print stacktrace with warning
        if not self.prompt_editor:
            return

        # Force the label to calculate its size
        self.char_count_label.GetParent().Layout()

        editor_size = self.prompt_editor.GetSize()
        label_size = self.char_count_label.GetBestSize()  # Use GetBestSize() instead of GetSize()

        # Position in bottom-right corner with small margin
        x = editor_size.width - label_size.width - 5
        y = editor_size.height - label_size.height - 5

        self.char_count_label.SetPosition((x, y))

        # Make sure the label is on top
        self.char_count_label.Raise()

    def update_char_count(self):
        """Update the character count label"""
        if not hasattr(self, 'char_count_label'):
            return

        text = self.prompt_editor.GetValue()
        char_count = len(text)
        self.char_count_label.SetLabel(f"{char_count} chars")

        # Reposition label in case size changed
        wx.CallAfter(self.position_char_count_label)



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
        original_text = self.text_ctrl.GetValue()

        # Don't insert text directly here! wx.TextDropTarget has default behavior that
        # automatically inserts the dragged text after OnDropText returns. To prevent
        # duplicate text insertion, we use CallAfter to perform our insertion after
        # the default behavior completes, then overwrites up any unwanted drag and drop 
        # text that was inserted by default.
        wx.CallAfter(self._insert_drop, original_text, drop_pos, dropped_text)

        return True

    def _get_char_position(self, x, y):
        """Convert screen coordinates to character position in text"""
        pos = self.text_ctrl.HitTest(wx.Point(x, y))

        if pos[0] == wx.TE_HT_UNKNOWN:
            return self.text_ctrl.GetInsertionPoint()

        # Convert line/column to character position
        line_num, col_num = pos[2], pos[1]
        lines = self.text_ctrl.GetValue().split('\n')

        char_pos = sum(len(lines[i]) + 1 for i in range(min(line_num, len(lines))))
        char_pos += min(col_num, len(lines[line_num]) if line_num < len(lines) else 0)

        return char_pos

    def _insert_drop(self, original_text, drop_pos, variable_text):
        expected_text = original_text[:drop_pos] + variable_text + original_text[drop_pos:]

        self.text_ctrl.SetValue(expected_text)
        self.text_ctrl.SetInsertionPoint(drop_pos + len(variable_text))
        self.text_ctrl.SetFocus()        