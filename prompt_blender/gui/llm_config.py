# Wizard next-next-finish style

class LLMConfigDialog(wx.Dialog):
    def __init__(self, parent, execute_function):
        super(LLMConfigDialog, self).__init__(parent, title='Model Configuration', size=(300, 180))

        self.init_ui()
        self.Centre()

        self._execute_function = execute_function


    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Label LLM:
        self.label = wx.StaticText(panel, label="Model Selection:")
        vbox.Add(self.label, flag=wx.ALL | wx.LEFT, border=5)

        # Load fom llm_models
        available_models = list(execute_llm.load_modules().keys())

        # Combo Box com as opções. Closed list.
        self.combo = wx.ComboBox(panel, choices=available_models, style=wx.CB_READONLY)
        vbox.Add(self.combo, flag=wx.ALL | wx.EXPAND, border=5)

        # Botão de cancelar/concluir
        self.button = wx.Button(panel, label="Next")
        vbox.Add(self.button, flag=wx.ALL | wx.CENTER, border=10)

        panel.SetSizer(vbox)

        # On button click
        self.button.Bind(wx.EVT_BUTTON, self.on_execute)

    def on_execute(self, event):
        self._execute_function()