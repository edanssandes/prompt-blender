import wx
import os
from prompt_blender.llms import execute_llm

class ExecuteDialog(wx.Dialog):
    CACHE_MODE_KEEP = 0
    CACHE_MODE_REPLACE = 1
    CACHE_MODES = {
        CACHE_MODE_KEEP: "Always keep cache",
        CACHE_MODE_REPLACE: "Replace cache if exists"
    }

    def __init__(self, parent, modules):
        super(ExecuteDialog, self).__init__(parent, title='Execution Configuration', size=(300, 180))

        # Load fom llm_models
        self.available_models = modules

        # For each module, create its argument dictionary
        self.module_args = {module_name: llm_module.get_args() for module_name, llm_module in self.available_models.items()}

        self.selected_module = 'chatgpt'
        self.selected_cache_mode = self.CACHE_MODE_KEEP

        self.init_ui()
        self.Centre()
        #self.SetMinSize((900, 200))



    def init_ui(self):
        self.panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Grid sizer for the first lines, containing global execution parameters
        # First column size is fixed, second column size is flexible
        grid = wx.FlexGridSizer(2, 1, 1)
        grid.SetFlexibleDirection(wx.HORIZONTAL)

        # Combo box with cache modes.
        self.cache_mode = wx.Choice(self.panel, choices=list(self.CACHE_MODES.values()))
        grid.Add(wx.StaticText(self.panel, label="Cache Mode:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        grid.Add(self.cache_mode, proportion=1, flag=wx.ALL | wx.EXPAND, border=1)
     

        # Combo Box with modules. Closed list. Cannot focus text box.
        self.combo = wx.Choice(self.panel, choices=[llm_module.module_info['name'] for llm_module in self.available_models.values()])
        # Set different values

        grid.Add(wx.StaticText(self.panel, label="Module:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        grid.Add(self.combo, proportion=1, flag=wx.ALL | wx.EXPAND, border=1)
        self.combo.SetMinSize((300, -1))



        vbox.Add(grid, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)

        # Add horizontal separator
        vbox.Add(wx.StaticLine(self.panel), flag=wx.ALL | wx.EXPAND, border=5)

        # Painel que receberá o painel de parâmetros específicos para cada modelo, conforme a seleção
        self.parameters_panel = wx.Panel(self.panel)
        #self.parameters_panel.SetSize((900, -1))

        vbox.Add(self.parameters_panel, flag=wx.ALL | wx.EXPAND, border=5)

        def on_combo(event):

            self.store_args()
            # Get nth element from the list of available models
            idx_selected_module = self.combo.GetSelection()
            self.selected_module = list(self.available_models.keys())[idx_selected_module]
            
            self.populate_parameters_panel()

            print("Selected: ", self.selected_module)

        # bind
        self.combo.Bind(wx.EVT_CHOICE, on_combo)



        # Cache mode update
        def on_cache_mode(event):
            self.selected_cache_mode = self.cache_mode.GetSelection()
            print("Cache mode: ", self.selected_cache_mode)

        self.cache_mode.Bind(wx.EVT_CHOICE, on_cache_mode)
        

        # Botão de cancelar/concluir
        self.button = wx.Button(self.panel, label="Executar")
        vbox.Add(self.button, flag=wx.ALL | wx.CENTER, border=10)

        self.panel.SetSizer(vbox)

        # Set the proper size for the dialog
        vbox.Fit(self)
        self.Refresh()

        # On button click
        self.button.Bind(wx.EVT_BUTTON, self.on_execute)

        # On close
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Set the default value to the first item
        self.populate_parameters_panel()

        # Remove focus from the combo box
        self.parameters_panel.SetFocus()
        
    def populate_parameters_panel(self):

        # Remove the current panel from the parameters_panel
        for child in self.parameters_panel.GetChildren():
            child.Destroy()

        # Create a new panel on the existing parameters_panel to show content
        module = self.available_models[self.selected_module]
        if hasattr(module, 'ConfigPanel'):
        
            config_panel = module.ConfigPanel(self.parameters_panel)
            config_panel.args = module.get_args()

            # Set the sizer for parameters_panel and add the config_panel to it
            parameters_sizer = wx.BoxSizer(wx.VERTICAL)
            parameters_sizer.Add(config_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
            self.parameters_panel.SetSizer(parameters_sizer)

        # Select combo by text
        self.combo.SetStringSelection(self.selected_module)

        # Select cache mode
        self.cache_mode.SetSelection(self.selected_cache_mode)

        # Expand dialog to fit new content
        #self.parameters_panel.Fit()
        #self.Fit()
        self.panel.GetSizer().Fit(self)

        self.Refresh()        

    def on_close(self, event):
        self.store_args()
        event.Skip()

    def on_execute(self, event):
        # Save the current parameters
        self.store_args()

        #self._execute_function()

        self.EndModal(wx.ID_OK)

    def store_args(self):
        if self.selected_module is not None:
            print("Storing args for ", self.selected_module)
            children = self.parameters_panel.GetChildren()
            if len(children) > 0:
                self.module_args[self.selected_module] = children[0].args

    def get_selected_module(self):
        return self.available_models[self.selected_module]
    
    def get_module_args(self):
        return self.module_args[self.selected_module]
    
    def set_module_args(self, args):
        self.module_args[self.selected_module] = args

    def get_cache_mode(self):
        return self.cache_mode.GetSelection()

if __name__ == '__main__':
    app = wx.App(False)
    dialog = ExecuteDialog(None)
    app.MainLoop()
