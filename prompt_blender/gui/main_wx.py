import os
import wx
import wx.grid
from prompt_blender.gui.model import Model
import wx.lib.agw.ultimatelistctrl as ULC
import wx.adv
import pandas as pd
import threading

from prompt_blender.arguments import Config
from prompt_blender.blend import blend_prompt

from prompt_blender.llms import execute_llm
from prompt_blender.llms import dummy
from prompt_blender.gui.progress import ProgressDialog
from prompt_blender.gui.execute import ExecuteDialog
from prompt_blender.gui.preferences import PreferencesDialog, Preferences

from prompt_blender.analysis import gpt_cost, gpt_json
from prompt_blender.analysis import analyse_results

import prompt_blender.info

import hashlib
import json

import io
import zipfile
import shutil


PROJECT_FILE_EXTENSION = "pbp"
PREFERENCE_FILE = "prompt_blender.config"

class MainFrame(wx.Frame):
    TITLE = 'Prompt Blender'
    def __init__(self, parent):
        super(MainFrame, self).__init__(parent, title=MainFrame.TITLE, size=(800, 600))

        # Exemplo de dados para a árvore
        #self.data = Model.create_empty()
        self.data = Model.create_from_template()
        self.data.add_on_modified_callback(self.update_project_state)
        self.result_name = None
        self.last_result_file = None

        # Load preferences from config file
        if os.path.exists(PREFERENCE_FILE):
            self.preferences = Preferences.load_from_file(PREFERENCE_FILE)
        else:
            self.preferences = Preferences()

        self.analyse_functions = analyse_results.load_modules(["./plugins"])
        self.llm_modules = execute_llm.load_modules(["./plugins"])

        self.load_images()

        self.create_menus()

        # Dividir a janela em painéis superior e inferior
        splitter = wx.SplitterWindow(self)
        top_panel = wx.Panel(splitter)
        bottom_panel = wx.Panel(splitter)
        splitter.SplitHorizontally(top_panel, bottom_panel, sashPosition=300)


        # Criar os componentes do painel superior
        self.create_top_panel(top_panel)

        # Criar os componentes do painel inferior
        self.create_bottom_panel(bottom_panel)

        self.Centre()
        self.Show()

        # Progress dialog
        self.progress_dialog = ProgressDialog(self, "Progresso da Tarefa")

        # Execute dialog
        self.execute_dialog = ExecuteDialog(self, self.llm_modules)

        # Preferences dialog
        self.preferences_dialog = PreferencesDialog(self, self.preferences)

        self.populate_data()

    def load_images(self):
        self.image_list = wx.ImageList(16, 16)

        # images from art provider (Folder, File, Spreedsheet, json, xls_format)
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_REPORT_VIEW, wx.ART_OTHER, (16, 16)))
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_FOLDER, wx.ART_OTHER))
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER))
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_LIST_VIEW, wx.ART_OTHER))

        # Move up and down
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_GO_UP, wx.ART_OTHER))
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_OTHER))

        # Remove
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_DELETE, wx.ART_OTHER))

        # Insert
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_ADD_BOOKMARK, wx.ART_OTHER))


    def create_menus(self):
        # Menu Bar
        menu_bar = wx.MenuBar()

        # First level menus
        file_menu = wx.Menu()
        run_menu = wx.Menu()
        help_menu = wx.Menu()

        menu_bar.Append(file_menu, "File")
        menu_bar.Append(run_menu, "Run")
        menu_bar.Append(help_menu, "Help")


        # File Menu

        # New project submenu
        new_project_menu = wx.Menu()
        file_menu.AppendSubMenu(new_project_menu, "New Project")
        new_project_menu.Append(100, "Empty Project")
        new_project_menu.Append(101, "From Template")
        new_project_menu.Append(102, "From Clipboard")


        file_menu.Append(wx.ID_OPEN, "Open Project")
        # Open recent
        self.recent_menu = wx.Menu()
        file_menu.AppendSubMenu(self.recent_menu, "Open Recent")
        file_menu.Append(wx.ID_SAVE, "Save Project")
        file_menu.Append(wx.ID_SAVEAS, "Save Project As ...")
        file_menu.Append(wx.ID_CLOSE, "Close Project")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_PREFERENCES, "Preferences...")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "Sair")


        # Run Menu
        run_menu.Append(3001, "Run Combinations")
        run_menu.AppendSeparator()
        run_menu.Append(3002, "Blend Prompts")
        run_menu.Append(3003, "Export Last Results")

        # Help Menu / About
        help_menu.Append(wx.ID_ABOUT, "About")

        self.SetMenuBar(menu_bar)

        # Eventos de menu

        # Preferences
        def on_preferences(event):
            self.preferences_dialog.ShowModal()
            preferences = self.preferences_dialog.get_preferences()
            preferences.save_to_file(PREFERENCE_FILE)


        self.Bind(wx.EVT_MENU, on_preferences, id=wx.ID_PREFERENCES)

        def on_run_menu(event):
            event_id = event.GetId()
            if event_id == 3001:
                self.execute_prompts()
            elif event_id == 3002:
                self.run_blend()
            elif event_id == 3003:
                self.export_results()

        run_menu.Bind(wx.EVT_MENU, on_run_menu)

        # About
        def on_about(event):
            # Consider html text hyperlink
            info = wx.adv.AboutDialogInfo()
            info.SetName("Prompt Blender")
            info.SetVersion(prompt_blender.info.__version__)
            #info.SetDevelopers([prompt_blender.info.__author__])
            info.SetDescription(prompt_blender.info.DESCRIPTION + "\n\n" + "Developed by " + prompt_blender.info.__author__)
            info.SetWebSite(prompt_blender.info.WEB_SITE)
            wx.adv.AboutBox(info)

        self.Bind(wx.EVT_MENU, on_about, id=wx.ID_ABOUT)

        def on_new_project(event):
            if not ask_save_changes():
                return  # Cancelled

            event_id = event.GetId()
            if event_id == 100:
                self.data = Model.create_empty()
            elif event_id == 101:
                self.data = Model.create_from_template()
            elif event_id == 102:
                self.data = Model.create_from_clipboard()
            else:
                return
            
            self.data.add_on_modified_callback(self.update_project_state)

            self.populate_data()

        new_project_menu.Bind(wx.EVT_MENU, on_new_project)

        def ask_save_changes():
            if self.data.is_modified:
                # Ask to save, with 3 options: Don't save, Save, Cancel
                # Use messageDialog to customize the labels and color
                dialog = wx.MessageDialog(self, "Save changes to project?", "Save", wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_QUESTION)
                dialog.SetYesNoCancelLabels("&Save", "&Don't Save", "&Cancel")
                
                ret = dialog.ShowModal()
                
                if ret == wx.ID_YES:
                    return on_save_project(None)
                elif ret == wx.ID_CANCEL:
                    return False
            return True

        def on_open_project(event):
            if not ask_save_changes():
                return  # Cancelled
            dialog = wx.FileDialog(self, "Open Project", wildcard="Prompt Blender Project (*.pbp)|*.pbp", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if dialog.ShowModal() == wx.ID_OK:
                path = dialog.GetPath()
                self.data = Model.create_from_file(path)
                self.data.add_on_modified_callback(self.update_project_state)
                self.populate_data()

        file_menu.Bind(wx.EVT_MENU, on_open_project, id=wx.ID_OPEN)


        def on_save_project(event, force_save_as=False):
            if self.data.file_path is None or force_save_as:
                dialog = wx.FileDialog(self, "Save Project", wildcard=f"Prompt Blender Project (*.{PROJECT_FILE_EXTENSION})|*.{PROJECT_FILE_EXTENSION}", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
                if dialog.ShowModal() == wx.ID_OK:
                    path = dialog.GetPath()
                    # Append the file extension
                    if not path.endswith(f".{PROJECT_FILE_EXTENSION}"):
                        path += f".{PROJECT_FILE_EXTENSION}"

                    self.data.save_to_file(path)
                else:
                    # Cancelled
                    return False  
            else:
                self.data.save_to_file()
            return True

        def on_save_project_as(event):
            on_save_project(event, force_save_as=True)

        file_menu.Bind(wx.EVT_MENU, on_save_project, id=wx.ID_SAVE)
        file_menu.Bind(wx.EVT_MENU, on_save_project_as, id=wx.ID_SAVEAS)


        def on_close_project(event):
            if not ask_save_changes():
                return  # Cancelled
            self.data = Model.create_empty()
            self.data.add_on_modified_callback(self.update_project_state)

            self.populate_data()
            
        file_menu.Bind(wx.EVT_MENU, on_close_project, id=wx.ID_CLOSE)        

        def on_exit_menu(event):
            if not ask_save_changes():
                return
            self.Close()

        file_menu.Bind(wx.EVT_MENU, on_exit_menu, id=wx.ID_EXIT)

        def on_exit(event):
            if not ask_save_changes():
                return
            event.Skip()

        self.Bind(wx.EVT_CLOSE, on_exit)


    def create_top_panel(self, panel):
        # Adicionando um segundo SplitterWindow
        top_splitter = wx.SplitterWindow(panel)
        left_panel = wx.Panel(top_splitter)
        right_panel = wx.Panel(top_splitter)

        # Configurando a posição inicial do divisor na metade do painel
        top_splitter.SplitVertically(left_panel, right_panel)
        top_splitter.SetSashGravity(0.3)  # Mantém a proporção ao redimensionar
        top_splitter.SetSashPosition(panel.GetSize()[0] // 2)  # Posição inicial no meio

        # Sizer for the left_panel
        tree_sizer = wx.BoxSizer(wx.VERTICAL)

        # Adiciona um pequeno painel superior para a árvore de parâmetros. Ele deve ter um tamanho fixo de 100 pixels
        tree_commands_panel = wx.Panel(left_panel)
        tree_sizer.Add(tree_commands_panel, 0, wx.EXPAND)

        # os botões ficarão na horizontal, um ao lado do outro
        tree_commands_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tree_commands_panel.SetSizer(tree_commands_sizer)
        


        # adiciona botões com ícones do image_list
        # All buttons will have no border
        add_dir_button = wx.BitmapButton(tree_commands_panel, bitmap=self.image_list.GetBitmap(1))
        add_file_button = wx.BitmapButton(tree_commands_panel, bitmap=self.image_list.GetBitmap(7))
        remove_button = wx.BitmapButton(tree_commands_panel, bitmap=self.image_list.GetBitmap(6))
        move_up_button = wx.BitmapButton(tree_commands_panel, bitmap=self.image_list.GetBitmap(4))
        move_down_button = wx.BitmapButton(tree_commands_panel, bitmap=self.image_list.GetBitmap(5))
        # Resize the buttons
        add_dir_button.SetSize((20, 20))
        add_file_button.SetSize((20, 20))
        remove_button.SetSize((20, 20))
        move_up_button.SetSize((20, 20))
        move_down_button.SetSize((20, 20))

        # Adiciona os botões ao sizer
        tree_commands_sizer.Add(add_file_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(add_dir_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(remove_button, 0, wx.EXPAND)

        # Up and down will be right aligned
        tree_commands_sizer.AddStretchSpacer()
        tree_commands_sizer.Add(move_up_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(move_down_button, 0, wx.EXPAND)

        # Move up and down
        def on_move_up(event):
            item = self.tree.GetSelection()
            if item.IsOk():
                param_id = self.tree.GetItemData(item)
                new_param_id = self.data.move_param(param_id, -1)
                self.populate_tree(self.data, new_param_id)
                
        def on_move_down(event):
            item = self.tree.GetSelection()
            if item.IsOk():
                param_id = self.tree.GetItemData(item)
                new_param_id = self.data.move_param(param_id, 1)
                self.populate_tree(self.data, new_param_id)


        move_up_button.Bind(wx.EVT_BUTTON, on_move_up)
        move_down_button.Bind(wx.EVT_BUTTON, on_move_down)
        

        # Árvore de parâmetros no painel esquerdo
        self.tree = wx.TreeCtrl(left_panel, style=wx.TR_DEFAULT_STYLE | wx.TR_FULL_ROW_HIGHLIGHT | wx.TR_HIDE_ROOT)
        self.tree.AssignImageList(self.image_list)
        tree_sizer.Add(self.tree, 1, wx.EXPAND)

        # Evento de seleção de item na árvore
        def on_tree_select(event):
            # get the previous tree selection
            item_old = event.GetOldItem()
            item_new = event.GetItem()
            param_id_old = self.tree.GetItemData(item_old)
            param_id_new = self.tree.GetItemData(item_new)

            if param_id_old == param_id_new:
                return

            self.populate_table(self.data, param_id_new)
            #self.populate_prompt_editor()

        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, on_tree_select)

        # Menu de contexto para a árvore
        def on_tree_right_click(event):
            menu = wx.Menu()
            # função de bind em cada item do menu
            menu.Append(1, "Add directory...")
            menu.Append(2, "Add file...")
            menu.AppendSeparator()
            menu.Append(3, "Remove")
            menu.AppendSeparator()
            menu.Append(4, "Transform...")
            menu.Append(5, "Truncate")


            # Evento de clique do menu de contexto
            def on_menu_click(event):
                item = event.GetId()
                if item == 1:
                    self.add_param_directory()
                elif item == 2:
                    self.add_param_file()
                elif item == 3:
                    self.remove_selected_param()
                elif item == 4:
                    self.apply_transform()
                elif item == 5:
                    self.truncate_selected_param()

            self.Bind(wx.EVT_MENU, on_menu_click)

            self.tree.PopupMenu(menu)
        
        self.tree.Bind(wx.EVT_RIGHT_DOWN, on_tree_right_click)

        # Add the same events to the buttons
        add_dir_button.Bind(wx.EVT_BUTTON, lambda event: self.add_param_directory())
        add_file_button.Bind(wx.EVT_BUTTON, lambda event: self.add_param_file())
        remove_button.Bind(wx.EVT_BUTTON, lambda event: self.remove_selected_param())




        left_panel.SetSizer(tree_sizer)

        # Grid de detalhes no painel direito
        self.table = ULC.UltimateListCtrl(right_panel, agwStyle=ULC.ULC_REPORT | ULC.ULC_VRULES | ULC.ULC_HRULES | ULC.ULC_SINGLE_SEL | ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)
        
        # on select row
        def on_table_select(event):
            row = event.GetIndex()
            item = self.tree.GetSelection()
            param_id = self.tree.GetItemData(item)
            self.data.set_selected_item(param_id, row)

            self.refresh_prompts()
        
        self.table.Bind(wx.EVT_LIST_ITEM_SELECTED, on_table_select)
        

        table_sizer = wx.BoxSizer(wx.VERTICAL)
        table_sizer.Add(self.table, 1, wx.EXPAND)
        right_panel.SetSizer(table_sizer)

        # Ajustando o layout do painel superior para incluir o splitter
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer.Add(top_splitter, 1, wx.EXPAND)
        panel.SetSizer(panel_sizer)


    def add_param_directory(self):
        # Apresentar caixa de dialogo
        dialog = wx.DirDialog(self, "Selecione um diretório")
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            self.data.add_param_directory(path)
            self.populate_data()

    def add_param_file(self):
        # txt, xlsx, csv, xls
        wildcards = "All supported files|*.txt;*.xlsx;*.xls;*.csv;*.json;*.jsonl|Text files (*.txt)|*.txt|Excel files (*.xlsx, *.xls)|*.xlsx;*.xls|CSV files (*.csv)|*.csv|JSON files (*.json)|*.json|JSON Line files (*.jsonl)|*.jsonl"

        # Apresentar caixa de dialogo,

        dialog = wx.FileDialog(self, "Selecione um arquivo", wildcard=wildcards, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            try:
                path = dialog.GetPath()
                self.data.add_param_file(path)
                self.populate_data()
            except ValueError as e:
                wx.MessageBox(f"Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def apply_transform(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            param_id = self.tree.GetItemData(item)

            # Load Python file
            wildcards = "Python files (*.py)|*.py"
            dialog = wx.FileDialog(self, "Selecione um arquivo", wildcard=wildcards, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if dialog.ShowModal() == wx.ID_OK:
                path = dialog.GetPath()
                try:
                    self.data.apply_transform(param_id, path)
                except ValueError as e:
                    wx.MessageBox(f"Error applying transformation: {e}", "Error", wx.OK | wx.ICON_ERROR)
                self.populate_data()

    def truncate_selected_param(self):
        # Ask for the number (integer) of lines to keep
        dialog = wx.TextEntryDialog(self, "Enter the number of lines to keep", "Truncate", "10")
        if dialog.ShowModal() == wx.ID_OK:
            try:
                n = int(dialog.GetValue())
                item = self.tree.GetSelection()
                if item.IsOk():
                    param_id = self.tree.GetItemData(item)
                    self.data.truncate_param(param_id, n)
                    self.populate_data()
            except ValueError:
                wx.MessageBox("Error: Invalid number of lines", "Error", wx.OK | wx.ICON_ERROR)

    def remove_selected_param(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            param_id = self.tree.GetItemData(item)
            self.data.remove_param(param_id)
            self.populate_data()


    def populate_data(self):
        self.populate_tree(self.data)
        self.populate_table(self.data, 0)
        self.populate_notebook(self.data)
        self.update_project_state()

        # Remove focus from any control
        self.SetFocus()

    def update_project_state(self):
        # Set Title
        name = self.data.file_path
        if name is None:
            name = "Untitled Project"
        modified_flag = "*" if self.data.is_modified else ""
        self.SetTitle(f"{MainFrame.TITLE} - {name}{modified_flag}")

        # Enable or disable menu items
        project_opened = self.data.file_path is not None
        #self.GetMenuBar().Enable(wx.ID_SAVE, project_opened)
        self.GetMenuBar().Enable(wx.ID_SAVEAS, project_opened)
        self.GetMenuBar().Enable(wx.ID_CLOSE, project_opened)

        # Enable or disable export results menu
        self.GetMenuBar().Enable(3003, self.last_result_file is not None)

        # Recent files
        self.update_recent_files()

    def update_recent_files(self):
        # Delete all itens from the recent file menu
        for item in self.recent_menu.GetMenuItems():
            self.recent_menu.Remove(item)
        
        for i, file in enumerate(self.preferences.recent_files):
            self.recent_menu.Append(2000 + i, file)

        def on_recent_file(event):
            file = self.preferences.recent_files[event.GetId() - 2000]
            self.data = Model.create_from_file(file)
            self.data.add_on_modified_callback(self.update_project_state)
            self.populate_data()

        self.Bind(wx.EVT_MENU, on_recent_file, id=2000, id2=2000 + len(self.preferences.recent_files))


    def create_bottom_panel(self, panel):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Inserir Abas
        import wx.lib.agw.flatnotebook as FNB

        # Notebook can close tabs (x button) and navigate buttons and double click allow rename
        self.notebook = FNB.FlatNotebook(panel, agwStyle=FNB.FNB_X_ON_TAB | FNB.FNB_NODRAG | FNB.FNB_NO_TAB_FOCUS | FNB.FNB_NAV_BUTTONS_WHEN_NEEDED | FNB.FNB_NO_X_BUTTON)
        #self.notebook = wx.Notebook(panel, style=wx.NB_TOP | wx.NB_MULTILINE | wx.NB_NOPAGETHEME | wx.NB_ | wx.NB_NO_NAV_BUTTONS)
        self.notebook.SetImageList(self.image_list)
        #vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        pbox = wx.BoxSizer(wx.VERTICAL)
        # Three tabs/pages with the same content/panel
        page_panel = wx.Panel(self.notebook)
        page_panel.SetSizer(pbox)
        #self.notebook.AddPage(page_panel, f"?")

        self.prompt_pages = []
        
        # Last page is for adding new prompts. use icon in the page title.
        # cannot move or close
        #self.notebook.SetTabEnabled(3, False)

        # Event for the notebook
        def on_notebook_change(event):
            if self.notebook.GetPageCount() != self.data.get_number_of_prompts() + 1:
                # The tabs are being changed by the program
                return
            # Get the selected page
            #page = self.notebook.GetSelection()
            selected_page_id = event.GetSelection()

            # Last page add new page and ask for name
            if selected_page_id == self.notebook.GetPageCount() - 1:
                self.data.add_prompt()

                # Add a new page
                prompt_page = PromptPage(self.notebook, self.data, self.data.get_number_of_prompts()-1)
                self.notebook.InsertPage(selected_page_id, prompt_page, prompt_page.title)
                self.prompt_pages.append(prompt_page)

                #self.notebook.SetSelection(self.notebook.GetPageCount() - 2)
                event.Veto()

            # Remove focus from the prompt editor
            self.SetFocus()


        # Allow edit page name on right click
        def on_notebook_rename(event):
            selected_page_id = event.GetSelection()
            if selected_page_id == self.notebook.GetPageCount() - 1:
                return

            # Get the selected page
            prompt_page = self.prompt_pages[selected_page_id]

            # Ask for the new name
            dialog = wx.TextEntryDialog(self, "Enter the new name for the prompt", "Rename Prompt", prompt_page.title)
            if dialog.ShowModal() == wx.ID_OK:
                new_name = dialog.GetValue()
                #prompt_page.title = new_name
                self.notebook.SetPageText(selected_page_id, new_name)

        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CONTEXT_MENU, on_notebook_rename)

        def on_notebook_close(event):
            page = self.notebook.GetSelection()
            # Ask for confirmation
            ret = wx.MessageBox(f"Are you sure you want to delete page {page}?", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
            if ret == wx.YES:
                self.data.remove_prompt(page)
                self.prompt_pages.pop(page)
            else:
                event.Veto()

            #self.notebook.DeletePage(page)

        #self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, on_notebook_change)
        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CLOSING, on_notebook_close)

        # event
        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CHANGED, on_notebook_change)


        vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 0)



        # Horizontal box sizer for the checkbox and button. 
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Add "View Mode" choice list on the left of the hbox
        self.view_mode = wx.Choice(panel, choices=["Edit Mode", "View Prompt", "View Result"])
        hbox.Add(self.view_mode, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.view_mode.SetSelection(0)

        # bind the checkbox event. Port from tkinter to wxpython
        def on_view_mode(event):
            for prompt_page in self.prompt_pages:
                prompt_page.view_mode = self.view_mode.GetSelection()
            
            self.refresh_prompts()

        self.view_mode.Bind(wx.EVT_CHOICE, on_view_mode)

        # Separate both widgets with a stretchable space
        hbox.AddStretchSpacer()

        # Botões para executar ações. run_button on the right of the hbox
        self.run_button = wx.Button(panel, label="Run Combinations")
        hbox.Add(self.run_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        # Bind the button event
        def on_run_button(event):
            self.execute_prompts()

        self.run_button.Bind(wx.EVT_BUTTON, on_run_button)

            

        vbox.Add(hbox, 0, wx.EXPAND)

        panel.SetSizer(vbox)

    
    def execute_prompts(self):
        # Execute the prompts
        self.execute_error = None

        #self.progress_dialog.run_task(long_running_task)
        ret = self.execute_dialog.ShowModal()

        if ret == wx.ID_OK:
            self.progress_dialog.run_task(self.task_all)

    #def run_prompt(self):
    #    self.progress_dialog.run_task(self.task_all)

    def run_blend(self):
        self.progress_dialog.run_task(self.task_blend, auto_close=True)

    def task_blend(self):
        config = Config.load_from_dict(self.data.to_dict())
        output_dir = self.preferences.cache_dir
        blend_prompt(config, output_dir, self.progress_dialog.update_progress)


    def task_all(self):
        llm_module = self.execute_dialog.get_selected_module()
        cache_mode = self.execute_dialog.get_cache_mode()
        cache_overwrite = cache_mode == ExecuteDialog.CACHE_MODE_REPLACE

        self.last_result_file = None
        wx.CallAfter(self.update_project_state)

        config = Config.load_from_dict(self.data.to_dict())
        #output_dir = "output_teste"
        output_dir = self.preferences.cache_dir
        blend_prompt(config, output_dir)
        
        # Execute the LLM
        module_args = self.execute_dialog.get_module_args()

        # Remove private arguments (starting with '_') from the module arguments. They may contain sensitive information (e.g. API keys/secrets)
        module_args_public = {k: v for k, v in module_args.items() if not k.startswith('_')}  # FIXME duplicated code
        # Hash the module arguments to create a unique identifier for the execution
        hash_args = hashlib.md5(json.dumps(module_args_public, sort_keys=True).encode()).hexdigest()

        # Get only the module name
        module_name = llm_module.__name__.split('.')[-1]
        self.result_name = f'{module_name}_{hash_args}'
        timestamp = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")

        try:
            max_cost = self.preferences.max_cost
            execute_llm.execute_llm(llm_module, module_args, config, output_dir, self.result_name, progress_callback=self.progress_dialog.update_progress, recreate=cache_overwrite, max_cost=max_cost)
        except Exception as e:
            self.execute_error = str(e)
            wx.CallAfter(self.execution_done)
            
            # print stack trace
            import traceback
            traceback.print_exc()
            return

        analysis_results = analyse_results.analyse_results(config, output_dir, self.result_name, self.analyse_functions)


        # Create the final zip file
        last_result_file = os.path.join(output_dir, f'{self.result_name}_{timestamp}.zip')
        with zipfile.ZipFile(last_result_file, 'w') as zipf:
            for module_name, results in analysis_results.items():
                df = pd.DataFrame(results)

                # Dump directly to the zip file. Use byteio to avoid writing to disk
                byteio = io.BytesIO()
                df.to_excel(byteio, index=False)
                byteio.seek(0)
                zipf.writestr(f'{module_name}.xlsx', byteio.read())

            # Add the config file to the zip
            zipf.writestr('config.json', json.dumps(config.json))
            zipf.writestr('execution.json', json.dumps({'module': llm_module.__name__, 'args': module_args_public}))

            # This set keeps track of the result files that are already in the zip
            result_files = set()

            # Add the prompt files and result files to the zip
            for argument_combination in config.get_parameter_combinations():
                prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
                result_file = os.path.join(output_dir, argument_combination.get_result_file(self.result_name))

                if result_file not in result_files:
                    zipf.write(prompt_file, os.path.relpath(prompt_file, output_dir))
                    zipf.write(result_file, os.path.relpath(result_file, output_dir))
                    result_files.add(result_file)

        self.last_result_file = last_result_file
        wx.CallAfter(self.update_project_state)

        wx.CallAfter(self.execution_done)

       
    def execution_done(self):
        self.progress_dialog.Hide()

        if self.execute_error:
            wx.MessageBox(f"Erro ao executar o LLM: {self.execute_error}", "Erro", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("LLM executado com sucesso", "Sucesso", wx.OK | wx.ICON_INFORMATION)
            self.export_results()




    def export_results(self):
        if self.last_result_file is None:
            wx.MessageBox("Nenhum resultado para exportar", "Erro", wx.OK | wx.ICON_ERROR)
            return
        
        # default filename is the name of the last result file
        default_filename = os.path.basename(self.last_result_file)

        # Ask filename to save the results in zip format. If the file exists, ask to overwrite
        dialog = wx.FileDialog(self, "Save Results", wildcard="Zip files (*.zip)|*.zip", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, defaultFile=default_filename)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            
            # copy the zip file to the selected path
            shutil.copy(self.last_result_file, path)                

    def populate_notebook(self, data):
        self.notebook.DeleteAllPages()
        
        if data.get_number_of_prompts() == 0:
            data.add_prompt()

        self.prompt_pages = []
        for i in range(data.get_number_of_prompts()):
            prompt_page = PromptPage(self.notebook, self.data, i)
            self.notebook.AddPage(prompt_page, prompt_page.title)
            self.prompt_pages.append(prompt_page)

        self.notebook.AddPage(wx.Panel(self.notebook), "", imageId=7) 


        

    def populate_tree(self, data, selected_index=0):
        self.tree.DeleteAllItems()  # Limpar a árvore existente
        root = self.tree.AddRoot("Parâmetros")

        # Carregar parâmetros na árvore
        for index, group in enumerate(data.parameters):
            if len(group[0]) == 1:  # Assume todos os elementos do grupo têm a mesma estrutura
                for key in group[0].keys():
                    # FIXME join both loops
                    if not key.startswith("_"):
                        item = self.tree.AppendItem(root, text=f"{key}", data=index)
                        self.tree.SetItemTextColour(item, data.get_variable_colors(key))
            else:
                group_node = self.tree.AppendItem(root, text=f"Parameter Group {index+1}", data=index)
                
                # Add imagem to the group node
                self.tree.SetItemImage(group_node, 0, wx.TreeItemIcon_Normal)
                for key in group[0].keys():
                    if not key.startswith("_"):
                        item = self.tree.AppendItem(group_node, text=f"{key}", data=index)
                        self.tree.SetItemTextColour(item, data.get_variable_colors(key))

        # Selecionar o n-th registro
        if len(data.parameters) > 0:
            item = self.tree.GetFirstChild(root)[0]
            for i in range(selected_index):
                item = self.tree.GetNextSibling(item)
            self.tree.SelectItem(item)


        self.tree.ExpandAll()  # Expandir todos os nós para visualização completa

    def populate_table(self, data, param_id):
        self.table.Freeze()

        # Set table size
        self.table.ClearAll()

        # Obter os detalhes do parâmetro selecionado
        param = data.get_parameter(param_id)
        if param is None:
            self.table.Thaw()
            return
        else:
            table = pd.DataFrame(param)



        # Set column names
        for i, col in enumerate(table.columns):
            self.table.InsertColumn(i, col)
            
        
        # Preencher com os dados
        for i, row in enumerate(table.values):
            if i >= 50:
                self.table.InsertStringItem(i, f'... Truncated at {i} rows ...')
                break
            self.table.InsertStringItem(i, str(i+1))

            for j, value in enumerate(row):
                s = str(value)
                if len(s) > 50:
                    s = s[:50] + "..."
                self.table.SetStringItem(i, j, s)
            
                

        # Select the row
        self.table.Select(data.get_selected_item(param_id))

        # Best fit column widths
        for i in range(len(table.columns)-1):
            self.table.SetColumnWidth(i, ULC.ULC_AUTOSIZE)
        # Last column size equal to panel size
        width = max(self.table.GetSize()[0], 500)
        self.table.SetColumnWidth(len(table.columns)-1, width)
            


        self.table.Thaw()



    def refresh_prompts(self):

        for prompt_page in self.prompt_pages:
            prompt_page.result_name = self.result_name  # FIXME: This is a hack. Should be done in a better way
            prompt_page.output_dir = self.preferences.cache_dir  # FIXME: same as above

            prompt_page.refresh()





class PromptPage(wx.Panel):
    def __init__(self, parent, data, prompt_id):
        super(PromptPage, self).__init__(parent)
        self.SetBackgroundColour(wx.Colour(255, 1, 1))

        self.prompt_id = prompt_id
        self.data = data
        self.view_mode = 0

        # Sizer para o layout da página
        sizer = wx.BoxSizer(wx.VERTICAL)

        # TextCtrl para a edição do prompt
        self.prompt_editor = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_RICH2)
        # Set Hint
        self.prompt_editor.SetHint("Insert prompt text here...")

        # Expand the text control to fill the panel in all directions
        sizer.Add(self.prompt_editor, 1, wx.EXPAND)

        self.SetSizer(sizer)




        self.refresh()

        # Write 


        # On change event for the prompt editor
        def on_prompt_change(event):
            if self.view_mode == 0:
                self.data.set_prompt(self.prompt_id, self.prompt_editor.GetValue())
                self.highlight_prompt()

        self.prompt_editor.Bind(wx.EVT_TEXT, on_prompt_change)    



    def SetValue(self, text):
        self.prompt_editor.Freeze()

        pos_0 = 0
        pos_1 = 0

        if self.view_mode == 0:
            self.prompt_editor.SetBackgroundColour(wx.Colour(255, 255, 255))
            self.prompt_editor.SetValue(text)
        elif self.view_mode == 1:
            self.prompt_editor.SetBackgroundColour(wx.Colour(200, 200, 200))
            self.prompt_editor.SetValue(text)
        else:
            if not text:
                self.prompt_editor.SetBackgroundColour(wx.Colour(200, 200, 180))
                self.prompt_editor.SetValue("")
            else:
                self.prompt_editor.SetBackgroundColour(wx.Colour(180, 255, 180))
                self.prompt_editor.SetValue(text)


        if text and self.view_mode != 2:
            self.highlight_prompt()

        #if pos_0 and pos_1:
        #    # yellow background color for appended text
        #    self.prompt_editor.SetStyle(pos_0, pos_1, wx.TextAttr(wx.BLACK, wx.Colour(255, 255, 192)))
            
            

        self.prompt_editor.SetEditable(self.view_mode == 0)
        self.prompt_editor.Thaw()

    def highlight_prompt(self):
        highlight_positions = self.data.get_hightlight_positions(prompt_id=self.prompt_id, interpolated=(self.view_mode==1))

        # Remove todas as cores existentes
        self.prompt_editor.SetStyle(0, self.prompt_editor.GetLastPosition(), wx.TextAttr(wx.BLACK))

        # Aplicar coloração ao texto
        for var_name, start, end in highlight_positions:
            self.prompt_editor.SetStyle(start, end, wx.TextAttr(self.data.get_variable_colors(var_name)))

    def refresh(self):
        #Lock the prompt editor if the view checkbox is checked
        if self.view_mode == 0:
            text = self.data.get_prompt(self.prompt_id)
        elif self.view_mode == 1:
            text = self.data.get_interpolated_prompt(self.prompt_id)
        elif self.view_mode == 2:
            text = self.data.get_result(self.prompt_id, self.output_dir, self.result_name)

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
        return f"Prompt {self.prompt_id+1}"


def run():
    app = wx.App(False)
    frame = MainFrame(None)
    app.MainLoop()


if __name__ == '__main__':
    run()
