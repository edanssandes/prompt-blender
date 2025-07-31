import wx
from config_model import ConfigModel

class ConfigDialog(wx.Dialog):
    def __init__(self, parent, title="Configuration", model=None, module_types=None):
        super().__init__(parent, title=title, size=(350, 200))
        if module_types is None:
            module_types = ["Default", "ModuleA", "ModuleB"]
        if model is None:
            model = ConfigModel()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Configuration Name
        hbox_name = wx.BoxSizer(wx.HORIZONTAL)
        lbl_name = wx.StaticText(panel, label="Configuration Name:")
        hbox_name.Add(lbl_name, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.txt_name = wx.TextCtrl(panel, value=model.name)
        hbox_name.Add(self.txt_name, proportion=1)
        vbox.Add(hbox_name, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Module Type
        hbox_module = wx.BoxSizer(wx.HORIZONTAL)
        lbl_module = wx.StaticText(panel, label="Module Type:")
        hbox_module.Add(lbl_module, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        self.cmb_module = wx.ComboBox(panel, choices=module_types, style=wx.CB_READONLY)
        try:
            idx = module_types.index(model.module_type)
            self.cmb_module.SetSelection(idx)
        except ValueError:
            self.cmb_module.SetSelection(0)
        hbox_module.Add(self.cmb_module, proportion=1)
        vbox.Add(hbox_module, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Dialog Buttons
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(panel, wx.ID_OK)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL)
        hbox_buttons.AddStretchSpacer(1)
        hbox_buttons.Add(btn_ok)
        hbox_buttons.Add(btn_cancel, flag=wx.LEFT, border=5)
        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)
        self.Layout()

    def get_values(self):
        name = self.txt_name.GetValue()
        module_type = self.cmb_module.GetValue()
        return ConfigModel(name=name, module_type=module_type)