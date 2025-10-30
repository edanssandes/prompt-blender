import wx
from prompt_blender.gui.config_model import ConfigModel
from prompt_blender.gui.dialogs.ExecuteDialog import ExecuteDialog

def get_art_bitmap(art_id, size=wx.ART_BUTTON):
    return wx.ArtProvider.GetBitmap(art_id, wx.ART_TOOLBAR, (16, 16))

class RunConfigurationsDialog(wx.Dialog):
    TITLE = "Run Configurations"
    DEFAULT_MODULE = "ChatGPT"

    def __init__(self, parent, available_modules=None):
        super().__init__(parent, title=RunConfigurationsDialog.TITLE, size=(500, 400))
        # if configurations:
        #     self.configurations = [ConfigModel.from_dict(x) for x in configurations]
        # else:
        #     self.configurations = []
        self.available_modules = available_modules
        self.on_values_changed = None
        self.configurations = []

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Button row at the top, aligned left, with space on the right
        self.button_panel = wx.Panel(panel)
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)

        # Add Configuration button (plus icon)
        self.add_button = wx.BitmapButton(
            self.button_panel, 
            bitmap=get_art_bitmap(wx.ART_PLUS)
        )
        self.add_button.SetToolTip("Add Configuration")
        hbox_buttons.Add(self.add_button, flag=wx.RIGHT, border=5)

        # Edit Configuration button (pencil icon)
        self.edit_button = wx.BitmapButton(
            self.button_panel, 
            bitmap=get_art_bitmap(wx.ART_EDIT)
        )
        self.edit_button.SetToolTip("Edit Configuration")
        self.edit_button.Disable()
        hbox_buttons.Add(self.edit_button, flag=wx.RIGHT, border=5)

        # Remove Configuration button (x icon)
        self.remove_button = wx.BitmapButton(
            self.button_panel, 
            bitmap=get_art_bitmap(wx.ART_DELETE)
        )
        self.remove_button.SetToolTip("Remove Configuration")
        self.remove_button.Disable()
        hbox_buttons.Add(self.remove_button, flag=wx.RIGHT, border=20)  # Extra space after buttons

        hbox_buttons.AddStretchSpacer(1)  # Pushes everything else to the left, adds space to the right

        self.button_panel.SetSizer(hbox_buttons)
        vbox.Add(self.button_panel, flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, border=10)

        # Listbox for configurations
        self.listbox = wx.ListBox(panel)
        vbox.Add(self.listbox, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # --- Bottom panel for "Run All" button ---
        self.bottom_panel = wx.Panel(panel)
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
        hbox_bottom.AddStretchSpacer(1)  # Push button to the right

        self.run_all_button = wx.Button(self.bottom_panel, label="Run All")
        self.run_all_button.SetToolTip("Run all configurations")
        hbox_bottom.Add(self.run_all_button, flag=wx.RIGHT | wx.BOTTOM, border=10)

        self.bottom_panel.SetSizer(hbox_bottom)
        vbox.Add(self.bottom_panel, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
        # --- End bottom panel ---

        panel.SetSizer(vbox)

        # Bind events
        self.add_button.Bind(wx.EVT_BUTTON, self.add_configuration)
        self.edit_button.Bind(wx.EVT_BUTTON, self.edit_configuration)
        self.remove_button.Bind(wx.EVT_BUTTON, self.remove_configuration)
        self.listbox.Bind(wx.EVT_LISTBOX, self.on_select)
        self.listbox.Bind(wx.EVT_LISTBOX_DCLICK, self.on_edit_double_click)  # Double click to edit
        self.run_all_button.Bind(wx.EVT_BUTTON, self.run_all_configurations)

        self.update_enabled_buttons()

        self.Centre()
        #self.Show()

    def set_configurations(self, configurations):
        """Set configurations from a list of dictionaries."""
        self.configurations = [ConfigModel.from_dict(key, value) for key, value in configurations.items()]
        self.listbox.Clear()
        for config in self.configurations:
            self.listbox.Append(self.config_to_string(config))
        self.update_enabled_buttons()


    def on_select(self, event):
        self.update_enabled_buttons()

    def update_enabled_buttons(self):
        """Update the enabled state of the edit and remove buttons based on selection."""
        selected = self.listbox.GetSelection() != wx.NOT_FOUND
        self.edit_button.Enable(selected)
        self.remove_button.Enable(selected)

        # If listbox is empty, disable the run all button
        empty = self.listbox.GetCount() == 0
        self.run_all_button.Enable(not empty)

    def add_configuration(self, event):
        # show a SingleChoiceDialog with the available modules names
        if self.available_modules:
            module_keys = list(self.available_modules.keys())
            module_names = [module.module_info['name'] for module in self.available_modules.values()]
            # TODO set default to chatgpt
            dlg = wx.SingleChoiceDialog(
                self, 
                "Select a module to configure:", 
                "Select Module", 
                module_names
            )
            dlg.SetSelection(module_names.index(self.DEFAULT_MODULE))
            

            #size
            dlg.SetSize((300, 200))
            if dlg.ShowModal() != wx.ID_OK:
                return
            selected_module_name = dlg.GetStringSelection()
            selected_module_key = module_keys[module_names.index(selected_module_name)]
            selected_module = self.available_modules[selected_module_key]

        result = self.prompt_for_configuration("Add New Configuration", module=selected_module)
        print(result)
        if result:
            self.configurations.append(result)
            self.listbox.Append(self.config_to_string(result))
            self.notify_change()
            self.update_enabled_buttons()

    def notify_change(self):
        if self.on_values_changed:
            # Convert ConfigModel instances to dictionaries for outside use
            dict_data = {config.name:config.to_dict() for config in self.configurations}

            self.on_values_changed(dict_data)


    def config_to_string(self, config):
        module_name = self.available_modules[config.module_id].module_info['name']
        return f"{config.name} ({module_name})"


    def edit_configuration(self, event):
        selected_index = self.listbox.GetSelection()
        if selected_index == wx.NOT_FOUND:
            return
        current_config = self.configurations[selected_index]
        selected_module = self.available_modules[current_config.module_id]

        result = self.prompt_for_configuration("Edit Configuration", module=selected_module, config=current_config)
        if result:
            self.configurations[selected_index] = result
            self.listbox.SetString(selected_index, self.config_to_string(result))
            self.notify_change()
            self.update_enabled_buttons()

    def remove_configuration(self, event):
        selected_index = self.listbox.GetSelection()
        if selected_index == wx.NOT_FOUND:
            return
        config_name = self.listbox.GetString(selected_index)
        confirm = wx.MessageBox(
            f"Are you sure you want to delete the configuration '{config_name}'?",
            "Confirm Deletion",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        )
        if confirm != wx.YES:
            return
        self.configurations.pop(selected_index)
        self.listbox.Delete(selected_index)
        self.listbox.SetSelection(wx.NOT_FOUND)  # Clear selection

        self.notify_change()
        self.update_enabled_buttons()




    def prompt_for_configuration(self, title, module=None, config=None):
        if config is None:
            config = ConfigModel()
        
        # Get all configuration names
        all_names = [cfg.name for cfg in self.configurations]
            
        module_name = module.module_info['name']
        dlg = ExecuteDialog(self, title=f"{title} ({module_name})", module=module, config=config, used_names=all_names)
        
        result = None
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_values()
        dlg.Destroy()
        print(result)
        return result

    def run_all_configurations(self, event):
        self.EndModal(wx.ID_OK)

    def on_edit_double_click(self, event):
        self.edit_configuration(event)

if __name__ == "__main__":
    from prompt_blender.llms import execute_llm
    llm_modules = execute_llm.load_modules(["./plugins"])

    app = wx.App(False)
    dlg = RunConfigurationsDialog(None, available_modules=llm_modules)
    dlg.ShowModal()
    app.MainLoop()