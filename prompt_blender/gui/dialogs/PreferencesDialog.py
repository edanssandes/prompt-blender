import wx
from prompt_blender.preferences import Preferences



class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, preferences=None):
        super(PreferencesDialog, self).__init__(parent, title="Preferences")

        if not preferences:
            preferences = Preferences()

        self._original_preferences = preferences
        self._current_preferences = self._original_preferences.clone()

        self.init_ui()
        self.Centre()


    def init_ui(self):
        self.panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(vbox)

        # Component that will hold the cache directory used by the execution. 
        horizontal_panel = wx.Panel(self.panel)
        horizontal_panel.SetMinSize((400, -1))
        self.cache_ctrl = wx.TextCtrl(horizontal_panel, style=wx.TE_READONLY)
        # Button with "..." for directory selection. The button must be small, square 1:1 proportion
        self.cache_button = wx.Button(horizontal_panel, label="...", size=(40, 30))
        self.cache_button.Bind(wx.EVT_BUTTON, self.on_cache_button)

        # Add label and cache controls horizontally, vertically centered in the second line
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        horizontal_panel.SetSizer(hbox)
        hbox.Add(wx.StaticText(horizontal_panel, label="Cache Directory:"), flag=wx.ALL | wx.CENTER, border=5)
        hbox.Add(self.cache_ctrl, proportion=1, flag=wx.ALL | wx.CENTER | wx.EXPAND, border=5)
        hbox.Add(self.cache_button, flag=wx.ALL | wx.CENTER, border=5)
        vbox.Add(horizontal_panel, proportion=0, flag=wx.ALL | wx.EXPAND, border=5)

        # Add horizontal separator
        line = wx.StaticLine(self.panel)
        vbox.Add(line, proportion=0, flag=wx.ALL | wx.EXPAND, border=5)

        # Maximum number of allowed combinations (numeric SpinCtrl, range=0-10000)
        vbox.Add(wx.StaticText(self.panel, label="Maximum number of allowed combinations:"), proportion=0, flag=wx.LEFT | wx.TOP, border=5)
        self.max_combinations = wx.SpinCtrl(self.panel, min=0, max=10000)
        vbox.Add(self.max_combinations, proportion=0, flag=wx.LEFT | wx.TOP, border=5)

        # Maximum cost per execution (in dollars) - SpinCtrl with 2 decimal places, default 1.50, range=0.0-20.0
        vbox.Add(wx.StaticText(self.panel, label="Maximum cost per execution (in dollars):"), proportion=0, flag=wx.LEFT | wx.TOP, border=5)
        self.max_cost = wx.SpinCtrlDouble(self.panel, min=0.0, max=20.0, inc=0.01)
        vbox.Add(self.max_cost, proportion=0, flag=wx.LEFT | wx.TOP, border=5)


        # Timeout per request (in seconds)
        vbox.Add(wx.StaticText(self.panel, label="Timeout per request (in seconds):"), proportion=0, flag=wx.LEFT | wx.TOP, border=5)
        self.timeout = wx.SpinCtrl(self.panel, min=0, max=300)
        vbox.Add(self.timeout, proportion=0, flag=wx.LEFT | wx.TOP, border=5)


        # Maximum number of rows (numeric SpinCtrl, range=0-100000)
        vbox.Add(wx.StaticText(self.panel, label="Maximum number of rows:"), proportion=0, flag=wx.LEFT | wx.TOP, border=5)
        self.max_rows = wx.SpinCtrl(self.panel, min=0, max=100000)
        vbox.Add(self.max_rows, proportion=0, flag=wx.LEFT | wx.TOP, border=5)


        # Add horizontal separator
        #line = wx.StaticLine(self.panel)
        #vbox.Add(line, flag=wx.ALL | wx.EXPAND, border=5)

        # Apply and Cancel buttons panel
        horizontal_panel = wx.Panel(self.panel)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        horizontal_panel.SetSizer(hbox)
        hbox.AddStretchSpacer()
        self.apply_button = wx.Button(horizontal_panel, label="Apply")
        self.cancel_button = wx.Button(horizontal_panel, label="Cancel")
        hbox.Add(self.cancel_button, flag=wx.ALL | wx.CENTER, border=5)
        hbox.Add(self.apply_button, flag=wx.ALL | wx.CENTER, border=5)
        vbox.Add(horizontal_panel, proportion=0, flag=wx.ALL | wx.EXPAND, border=5)

        self.apply_button.Bind(wx.EVT_BUTTON, self.on_apply)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)


        # Add space to the bottom
        #vbox.Add((60, 60), flag=wx.ALL | wx.EXPAND, border=5)


        self.refresh_fields(self._current_preferences)
        self.refresh_buttons()

        def on_timeout_changed(event):
            self._current_preferences.timeout = self.timeout.GetValue()
            self.refresh_buttons()

        def on_max_cost_changed(event):
            self._current_preferences.max_cost = self.max_cost.GetValue()
            self.refresh_buttons()

        def on_max_combinations_changed(event):
            self._current_preferences.max_combinations = self.max_combinations.GetValue()
            self.refresh_buttons()

        def on_cache_changed(event):
            self._current_preferences.cache_dir = self.cache_ctrl.GetValue()
            self.refresh_buttons()

        def on_max_rows_changed(event):
            self._current_preferences.max_rows = self.max_rows.GetValue()
            self.refresh_buttons()

        self.timeout.Bind(wx.EVT_SPINCTRL, on_timeout_changed)
        self.max_cost.Bind(wx.EVT_SPINCTRLDOUBLE, on_max_cost_changed)
        self.max_combinations.Bind(wx.EVT_SPINCTRL, on_max_combinations_changed)
        self.cache_ctrl.Bind(wx.EVT_TEXT, on_cache_changed)
        self.max_rows.Bind(wx.EVT_SPINCTRL, on_max_rows_changed)

        def on_close(event):
            if self._current_preferences != self._original_preferences:
                dlg = wx.MessageDialog(self, "Do you want to apply the changes?", "Apply changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
                result = dlg.ShowModal()
                if result == wx.ID_CANCEL:
                    event.Veto()
                    return

                if result == wx.ID_YES:
                    self.apply()
            event.Skip()

        self.Bind(wx.EVT_CLOSE, on_close)

        # Layout
        vbox.Fit(self)
        #self.panel.Fit()
        #self.Fit()
        self.Layout()

    def refresh_fields(self, preferences):
        self.cache_ctrl.SetValue(preferences.cache_dir)
        self.max_combinations.SetValue(preferences.max_combinations)
        self.max_cost.SetValue(preferences.max_cost)
        self.timeout.SetValue(preferences.timeout)
        self.max_rows.SetValue(preferences.max_rows)

    def refresh_buttons(self):
        print("Refresh buttons")
        self.apply_button.Enable(self._current_preferences != self._original_preferences)

    def get_preferences(self):
        return self._original_preferences

    def on_cache_button(self, event):
        dlg = wx.DirDialog(self, "Choose a directory:", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.cache_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def on_cancel(self, event):
        self._current_preferences._preferences = self._original_preferences._preferences.copy()
        self.refresh_fields(self._current_preferences)
        self.Close()

    def on_apply(self, event):
        self.apply()
        self.Close()

    def apply(self):
        self._original_preferences._preferences = self._current_preferences._preferences.copy()


if __name__ == '__main__':
    app = wx.App()
    dlg = PreferencesDialog(None)
    dlg.Fit()
    dlg.Show()
    app.MainLoop()
    print(dlg.get_preferences()._preferences)        