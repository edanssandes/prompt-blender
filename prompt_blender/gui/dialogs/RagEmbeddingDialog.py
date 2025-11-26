import wx

class RagEmbeddingDialog(wx.Dialog):
    EMBEDDING_MODELS = [
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002"
    ]

    RETURN_FORMATS = [
        "text",
        "json"
    ]

    def __init__(self, parent, title, config=None):
        super().__init__(parent, title=title)

        if config is None:
            config = {
                'model_name': 'text-embedding-3-small',
                'chunk_size': 500,
                'chunk_overlap': 50,
                'return_format': 'json'
            }

        self._original_config = config.copy()
        self._current_config = config.copy()

        self.init_ui()
        self.Centre()

    def init_ui(self):
        self.panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(vbox)

        # Create a grid bag sizer for the form fields (allows spanning)
        grid_sizer = wx.GridBagSizer(vgap=5, hgap=10)

        # Model selection
        model_label = wx.StaticText(self.panel, label="Embedding Model:")
        grid_sizer.Add(model_label, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.model_combo = wx.ComboBox(self.panel, choices=self.EMBEDDING_MODELS, style=wx.CB_DROPDOWN)
        grid_sizer.Add(self.model_combo, pos=(0, 1), flag=wx.EXPAND)

        # Chunk size
        chunk_size_label = wx.StaticText(self.panel, label="Chunk Size:")
        grid_sizer.Add(chunk_size_label, pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.chunk_size_spin = wx.SpinCtrl(self.panel, min=100, max=10000)
        grid_sizer.Add(self.chunk_size_spin, pos=(1, 1), flag=wx.EXPAND)

        # Chunk overlap
        chunk_overlap_label = wx.StaticText(self.panel, label="Chunk Overlap:")
        grid_sizer.Add(chunk_overlap_label, pos=(2, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.chunk_overlap_spin = wx.SpinCtrl(self.panel, min=0, max=1000)
        grid_sizer.Add(self.chunk_overlap_spin, pos=(2, 1), flag=wx.EXPAND)

        # Return format
        return_format_label = wx.StaticText(self.panel, label="Return Format:")
        grid_sizer.Add(return_format_label, pos=(3, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.return_format_choice = wx.Choice(self.panel, choices=self.RETURN_FORMATS)
        grid_sizer.Add(self.return_format_choice, pos=(3, 1), flag=wx.EXPAND)

        # Make the second column expandable
        grid_sizer.AddGrowableCol(1)

        # Add the grid sizer to the main vertical sizer
        vbox.Add(grid_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons
        button_panel = wx.Panel(self.panel)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        button_panel.SetSizer(hbox)
        hbox.AddStretchSpacer()

        self.ok_button = wx.Button(button_panel, label="OK")
        self.cancel_button = wx.Button(button_panel, label="Cancel")
        hbox.Add(self.cancel_button, flag=wx.ALL, border=5)
        hbox.Add(self.ok_button, flag=wx.ALL, border=5)
        vbox.Add(button_panel, flag=wx.EXPAND | wx.ALL, border=5)

        self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        # Bind change events
        self.model_combo.Bind(wx.EVT_COMBOBOX, self.on_config_changed)
        self.chunk_size_spin.Bind(wx.EVT_SPINCTRL, self.on_config_changed)
        self.chunk_overlap_spin.Bind(wx.EVT_SPINCTRL, self.on_config_changed)
        self.return_format_choice.Bind(wx.EVT_CHOICE, self.on_config_changed)

        # Set initial values
        self.refresh_fields(self._current_config)

        # Layout
        vbox.Fit(self)
        self.Layout()

    def refresh_fields(self, config):
        self.model_combo.SetValue(config['model_name'])
        self.chunk_size_spin.SetValue(config['chunk_size'])
        self.chunk_overlap_spin.SetValue(config['chunk_overlap'])
        self.return_format_choice.SetSelection(self.RETURN_FORMATS.index(config['return_format']))

    def on_config_changed(self, event):
        self._current_config['model_name'] = self.model_combo.GetValue()
        self._current_config['chunk_size'] = self.chunk_size_spin.GetValue()
        self._current_config['chunk_overlap'] = self.chunk_overlap_spin.GetValue()
        self._current_config['return_format'] = self.RETURN_FORMATS[self.return_format_choice.GetSelection()]

    def get_config(self):
        return self._original_config

    def on_cancel(self, event):
        self._current_config = self._original_config.copy()
        self.refresh_fields(self._current_config)
        self.EndModal(wx.ID_CANCEL)

    def on_ok(self, event):
        self._original_config = self._current_config.copy()
        self.EndModal(wx.ID_OK)

if __name__ == '__main__':
    app = wx.App()
    dlg = RagEmbeddingDialog(None, title="RAG Embedding Configuration")
    if dlg.ShowModal() == wx.ID_OK:
        print("Configuration saved:")
        print(dlg.get_config())
    else:
        print("Dialog cancelled.")
    dlg.Destroy()
    app.MainLoop()
