import wx
import os
from prompt_blender.llms import execute_llm
from prompt_blender.gui.config_model import ConfigModel

class ExecuteDialog(wx.Dialog):

    def __init__(self, parent, title, module, config, used_names):
        super(ExecuteDialog, self).__init__(parent, title=title, size=(300, 180))

        # Load fom llm_models
        self.module = module
        self.module_id = module.module_info['id']
        if config.module_args:
            self.module_args = config.module_args
            self.config_name = config.name
        else:
            # Create the default values for the module
            self.module_args = module.get_args()
            self.config_name = "Unnamed"

        self.used_names = used_names
        # remove the name from the used names list, so it can be reused
        if config.name in self.used_names:
            self.used_names.remove(config.name)

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
        #self.cache_mode = wx.Choice(self.panel, choices=[x for _,x in self.CACHE_MODES])
        #grid.Add(wx.StaticText(self.panel, label="Cache Timeout:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        #grid.Add(self.cache_mode, proportion=1, flag=wx.ALL | wx.EXPAND, border=1)

        # Text with name of the configuration (txt_name)
        self.txt_name = wx.TextCtrl(self.panel, value="New Configuration")
        grid.Add(wx.StaticText(self.panel, label="Configuration Name:"), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        grid.Add(self.txt_name, proportion=1, flag=wx.ALL | wx.EXPAND, border=1)
        # Set minimum size for the text box
        self.txt_name.SetMinSize((300, -1))  # Width is fixed, height is flexible
        
        # Bind name change event for validation
        self.txt_name.Bind(wx.EVT_TEXT, self.on_name_change)
        self.validate_name(self.txt_name.GetValue())


        # Combo Box with modules. Closed list. Cannot focus text box.
        #self.combo = wx.Choice(self.panel, choices=[self.get_module_label(llm_module) for llm_module in self.available_models.values()])
            


        vbox.Add(grid, proportion=1, flag=wx.ALL | wx.EXPAND, border=5)

        # Add horizontal separator
        vbox.Add(wx.StaticLine(self.panel), flag=wx.ALL | wx.EXPAND, border=5)

        # Painel que receberá o painel de parâmetros específicos para cada modelo, conforme a seleção
        self.parameters_panel = wx.Panel(self.panel)
        #self.parameters_panel.SetSize((900, -1))

        vbox.Add(self.parameters_panel, flag=wx.ALL | wx.EXPAND, border=5)

        # --- Bottom panel for "Run All" button ---
        bottom_panel = wx.Panel(self.panel)
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
        hbox_bottom.AddStretchSpacer(1)  # Push button to the right

        self.button = wx.Button(bottom_panel, label="Save")
        hbox_bottom.Add(self.button, flag=wx.RIGHT | wx.BOTTOM, border=10)

        bottom_panel.SetSizer(hbox_bottom)
        vbox.Add(bottom_panel, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)



        # Botão de cancelar/concluir
        #vbox.Add(self.button, flag=wx.ALL | wx.CENTER, border=10)

        self.panel.SetSizer(vbox)

        # Set the proper size for the dialog
        vbox.Fit(self)
        self.Refresh()

        # On button click
        self.button.Bind(wx.EVT_BUTTON, self.on_save)

        # On close
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Set the default value to the first item
        self.populate_parameters_panel()

        # Remove focus from the combo box
        self.parameters_panel.SetFocus()
        
    def get_module_label(self, llm_module):
        name = llm_module.module_info['name']
        version = llm_module.module_info.get('version', '')
        if version:
            version = f" - v{version}"
        return f"{name}{version}"

    def populate_parameters_panel(self):
        # Remove the current panel from the parameters_panel
        for child in self.parameters_panel.GetChildren():
            child.Destroy()
            
        # Necessary to update the size of the panel, otherwise the new panel may not fit correctly            
        self.panel.GetSizer().Fit(self)  
        

        if hasattr(self.module, 'ConfigPanel'):
        
            config_panel = self.module.ConfigPanel(self.parameters_panel)
            config_panel.args = self.module_args  # Get the args for the selected module
            #config_panel.args = module.get_args()

            # Set the sizer for parameters_panel and add the config_panel to it
            parameters_sizer = wx.BoxSizer(wx.VERTICAL)
            parameters_sizer.Add(config_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
            self.parameters_panel.SetSizer(parameters_sizer)


        self.txt_name.SetValue(self.config_name)

        # Expand dialog to fit new content
        #self.parameters_panel.Fit()
        #self.Fit()
        self.panel.GetSizer().Fit(self)

        self.Refresh()        


    def on_name_change(self, event):
        """Called when the text in the name field changes."""
        self.validate_name(self.txt_name.GetValue())
        event.Skip()

    def validate_name(self, name):
        """Checks if the name is a duplicate and updates the UI."""
        # A name is valid if it's the original name or not in the used_names list.
        if name not in self.used_names:
            self.txt_name.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
            self.txt_name.Refresh()
            return True
        else:
            # Mark as invalid
            self.txt_name.SetBackgroundColour(wx.Colour(255, 255, 128))  # Yellow
            self.txt_name.Refresh()
            return False

    def on_save(self, event):
        """Handles the save button click, validating before closing."""
        current_name = self.txt_name.GetValue()
        if not self.validate_name(current_name):
            wx.MessageBox(
                f"The configuration name '{current_name}' is already in use. Please choose a different name.",
                "Duplicate Name",
                wx.OK | wx.ICON_ERROR
            )
            return  # Stop, do not close the dialog

        # If validation passes, proceed with the original execute logic
        self.on_execute(event)


    def on_close(self, event):
        self.store_args()
        event.Skip()

    def on_execute(self, event):
        # Save the current parameters
        self.store_args()

        #self._execute_function()

        self.EndModal(wx.ID_OK)

    def store_args(self):
        children = self.parameters_panel.GetChildren()
        if len(children) > 0:
            self.module_args = children[0].args

    def get_selected_module(self):
        return self.module
    
    def get_module_args(self):
        return self.module_args
    
    def set_module_args(self, args):
        self.module_args = args

    # def get_cache_timeout(self):
    #     return self.CACHE_MODES[self.cache_mode.GetSelection()][0]


    def get_values(self):
        name = self.txt_name.GetValue()
        module_id = self.module_id
        
        module_args = self.get_module_args()
        return ConfigModel(
            name=name,
            module_id=module_id,
            module_args=module_args
        )
    
if __name__ == '__main__':
    app = wx.App(False)
    modules = execute_llm.load_modules(["./plugins"])
    config = ConfigModel()
    print(modules)
    dialog = ExecuteDialog(None, "Execute Dialog", modules['b85680ef-8da2-4ed5-b881-ce33fe5d3ec0'], config, [])
    dialog.ShowModal()
    app.MainLoop()    