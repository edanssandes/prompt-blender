import wx

# This class is a Dialog that allows the user to input a list of strings in three formats: CSV, json, jsonl or one string per line.

class InputListDialog(wx.Dialog):
    FORMATS = ['txt', 'csv', 'json', 'jsonl']
    FORMAT_DESCRIPTIONS = ['Single line per item', 'CSV (Comma separated values)', 'JSON', 'JSONL']
    def __init__(self, parent, title, message, default_list=None):
        super().__init__(parent, title=title)
        self.default_list = default_list
        self.init_ui(title, message)

    def init_ui(self, title, message):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # First line is the choice of the format
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        st0 = wx.StaticText(panel, label='Choose the format of the list: ')
        hbox.Add(st0, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL)

        self.choice = wx.Choice(panel, choices=self.FORMAT_DESCRIPTIONS)
        self.choice.SetSelection(0)
        hbox.Add(self.choice, proportion=1, flag=wx.EXPAND, border=10)

        vbox.Add(hbox, flag=wx.EXPAND | wx.ALL, border=10)

        st1 = wx.StaticText(panel, label=message)
        vbox.Add(st1, flag=wx.LEFT | wx.BOTTOM, border=10)

        self.tc = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        vbox.Add(self.tc, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)

        okButton = wx.Button(panel, label='OK')
        okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        hbox.Add(okButton, flag=wx.LEFT, border=10)

        cancelButton = wx.Button(panel, label='Cancel')
        cancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        hbox.Add(cancelButton, flag=wx.LEFT, border=10)

        vbox.Add(hbox, flag=wx.ALIGN_RIGHT | wx.TOP | wx.BOTTOM | wx.RIGHT, border=10)

        panel.SetSizer(vbox)

        if self.default_list:
            self.tc.SetValue('\n'.join(self.default_list))

        self.SetSize((600, 400))
        self.SetTitle(title)

    def OnOK(self, e):
        self.result = self.tc.GetValue()
        self.EndModal(wx.ID_OK)
        e.Skip()
        

    def OnCancel(self, e):
        self.result = None
        self.EndModal(wx.ID_CANCEL)
        e.Skip()

    def GetValue(self):
        return self.result
    
    def GetExtension(self):
        # Return TXT, CSV, JSON or JSONL
        return self.FORMATS[self.choice.GetSelection()]
    
    def ShowModal(self):
        return super().ShowModal()
    
if __name__ == "__main__":
    app = wx.App(False)
    dlg = InputListDialog(None, "Input List", "Please input your list of items:", default_list=["item1", "item2", "item3"])
    if dlg.ShowModal() == wx.ID_OK:
        print("User input:")
        print(dlg.GetValue())
        print("Format selected:", dlg.GetExtension())
    else:
        print("User cancelled the dialog.")
    dlg.Destroy()
    app.MainLoop()