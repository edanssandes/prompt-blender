import os
import wx
from prompt_blender.gui.dialogs.PreferencesDialog import PreferencesDialog
from prompt_blender.gui.PromptNotebookPanel import PromptPage
from prompt_blender.model import Model
from prompt_blender.gui.MainMenu import MainMenu
import wx.lib.agw.ultimatelistctrl as ULC
import pandas as pd

from prompt_blender.blend import blend_prompt

from prompt_blender.llms import execute_llm
from prompt_blender.gui.dialogs import ProgressDialog, RunConfigurationsDialog, InputListDialog
from prompt_blender.preferences import Preferences

from prompt_blender.analysis import analyse_results

from datetime import datetime

import shutil

from prompt_blender import result_file


PROJECT_FILE_EXTENSION = "pbp"
SUPPORTED_ENCODINGS = ["utf-8", "latin1", "windows-1252", "utf-16", "utf-32", "ascii"] 

class MainFrame(wx.Frame):
    TITLE = 'Prompt Blender'
    def __init__(self, parent, model=None):
        super(MainFrame, self).__init__(parent, title=MainFrame.TITLE, size=(800, 600))

        if model:
            self.data = model
        else:
            # Create empty project by default example
            default_example = os.path.join(os.path.dirname(__file__), 'examples', 'english_translation.pbp')
            self.data = Model.create_from_example(default_example)

        self.data.add_on_modified_callback(self.update_project_state)
        self.selected_parameter = None

        self.preferences = Preferences.load_from_file()

        self.analyse_functions = analyse_results.load_modules(["./plugins"])
        self.llm_modules = execute_llm.load_modules(["./plugins"])

        self.load_images()
        self.setup_menu()

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
        #self.execute_dialog = ExecuteDialog(self, self.llm_modules)
        #self.run_configurations = []
        self.execute_dialog = RunConfigurationsDialog(self, self.llm_modules)

        def on_run_configuration_change(run_configurations):
            self.data.run_configurations = run_configurations

            self.refresh_prompts()

        self.execute_dialog.on_values_changed = on_run_configuration_change

        # Preferences dialog
        self.preferences_dialog = PreferencesDialog(self, self.preferences)

        self.reset_view_mode()
        self.populate_data()

    def load_images(self):
        size = (16, 16)
        self.image_list = wx.ImageList(*size)

        client = wx.ART_BUTTON

        # images from art provider (Folder, File, Spreedsheet, json, xls_format)
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_REPORT_VIEW, client, size))

        # Insert
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_PLUS, client, size))
        self.image_list.Add(wx.ArtProvider.GetBitmap(wx.ART_ADD_BOOKMARK, client, size))


    def setup_menu(self):
        """Configura o menu principal usando a classe MainMenu"""
        self.main_menu = MainMenu(self)
        
        # Configurar callbacks
        self.main_menu.set_callback('new_empty_project', self._on_new_empty_project)
        self.main_menu.set_callback('new_from_clipboard', self._on_new_from_clipboard)
        self.main_menu.set_callback('load_example_template', self._on_load_example_template)
        self.main_menu.set_callback('open_project', self.open_project)
        self.main_menu.set_callback('save_project', self.save_project)
        self.main_menu.set_callback('save_project_as', self.save_project_as)
        self.main_menu.set_callback('close_project', self.close_project)
        self.main_menu.set_callback('show_preferences', self._on_show_preferences)
        self.main_menu.set_callback('exit_application', self._on_exit_application)
        self.main_menu.set_callback('run_combinations', self.execute_prompts)
        self.main_menu.set_callback('blend_prompts', self.run_blend)
        self.main_menu.set_callback('export_results', self.export_results)
        self.main_menu.set_callback('expire_cache_all', lambda: self.expire_cache('all'))
        self.main_menu.set_callback('expire_cache_error_items', lambda: self.expire_cache('error_items'))
        self.main_menu.set_callback('expire_cache_current_item', lambda: self.expire_cache('current_item'))
        self.main_menu.set_callback('import_cache', self.import_cache)
        self.main_menu.set_callback('show_about', None)  # Usa implementação padrão
        self.main_menu.set_callback('open_recent_file', self._on_open_recent_file)
        
        # Criar menus
        self.main_menu.create_menus()
        
        # Bind evento de fechamento da janela
        self.Bind(wx.EVT_CLOSE, self._on_window_close)
    
    def _on_new_empty_project(self):
        """Callback para criar projeto vazio"""
        if not self.ask_save_changes():
            return
        self.data = Model.create_empty()
        self.data.add_on_modified_callback(self.update_project_state)
        self.reset_view_mode()
        self.populate_data()
    
    def _on_load_example_template(self, template_file):
        """Callback para carregar template de exemplo"""
        if not self.ask_save_changes():
            return
        
        self.data = Model.create_from_example(template_file)
        self.data.add_on_modified_callback(self.update_project_state)
        self.reset_view_mode()
        self.populate_data()
    
    def _on_new_from_clipboard(self):
        """Callback para criar projeto a partir da área de transferência"""
        if not self.ask_save_changes():
            return
        self.data = Model.create_from_clipboard()
        self.data.add_on_modified_callback(self.update_project_state)
        self.reset_view_mode()
        self.populate_data()
    
    def _on_show_preferences(self):
        """Callback para mostrar preferências"""
        self.preferences_dialog.ShowModal()
        preferences = self.preferences_dialog.get_preferences()
        preferences.save_to_file()
    
    def _on_exit_application(self):
        """Callback para sair da aplicação"""
        if not self.ask_save_changes():
            return
        self.Close()
    
    def _on_window_close(self, event):
        """Handler para o fechamento da janela"""
        if not self.ask_save_changes():
            return
        event.Skip()
    
    def _on_open_recent_file(self, file_index):
        """Callback para abrir arquivo recente"""
        if not self.ask_save_changes():
            return
        
        file_path = self.preferences.recent_files[file_index]
        try:
            self.data = Model.create_from_file(file_path)
        except FileNotFoundError:
            wx.MessageBox(f"File does not exist: {file_path}", "Error", wx.OK | wx.ICON_ERROR)
            self.preferences.remove_recent_file(file_path)
            self.update_recent_files()
            return
        except ValueError as e:
            wx.MessageBox(f"Error loading project: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        self.data.add_on_modified_callback(self.update_project_state)
        self.reset_view_mode()
        self.populate_data()


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
        #tree_commands_panel.SetMinSize((-1, 80))
        


        # adiciona botões com ícones do image_list
        # All buttons will have no border
        size = (16, 16)
        #add_dir_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, size))
        #add_file_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_OTHER, size))
        add_table_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_PLUS, wx.ART_OTHER, size))
        remove_table_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_DELETE, wx.ART_OTHER, size))
        #move_up_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_GO_UP, wx.ART_OTHER, size))
        #move_down_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_OTHER, size))

        save_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_SAVE, wx.ART_OTHER, size))
        open_button = wx.BitmapButton(tree_commands_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, wx.ART_OTHER, size))

        # Add tooltips
        #add_dir_button.SetToolTip("Add Directory")
        #add_file_button.SetToolTip("Add File")
        add_table_button.SetToolTip("Add Table")
        remove_table_button.SetToolTip("Remove Table/Variable")
        #move_up_button.SetToolTip("Move Up")
        #move_down_button.SetToolTip("Move Down")

        save_button.SetToolTip("Save Project")
        open_button.SetToolTip("Open Project")

        
        # Resize the buttons
        #add_dir_button.SetSize((20, 20))
        #add_file_button.SetSize((20, 20))
        #remove_button.SetSize((20, 20))
        #move_up_button.SetSize((20, 20))
        #move_down_button.SetSize((20, 20))

        # Adiciona os botões ao sizer
        tree_commands_sizer.Add(save_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(open_button, 0, wx.EXPAND)
        # Space between buttons
        tree_commands_sizer.AddSpacer(10)

        #tree_commands_sizer.Add(add_file_button, 0, wx.EXPAND)
        #tree_commands_sizer.Add(add_dir_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(add_table_button, 0, wx.EXPAND)
        tree_commands_sizer.Add(remove_table_button, 0, wx.EXPAND)

        

        # Up and down will be right aligned
        #tree_commands_sizer.AddStretchSpacer()
        #tree_commands_sizer.Add(move_up_button, 0, wx.EXPAND)
        #tree_commands_sizer.Add(move_down_button, 0, wx.EXPAND)



        #move_up_button.Bind(wx.EVT_BUTTON, on_move_up)
        #move_down_button.Bind(wx.EVT_BUTTON, on_move_down)
        

        # Árvore de parâmetros no painel esquerdo
        self.tree = wx.TreeCtrl(left_panel, style=wx.TR_DEFAULT_STYLE | wx.TR_FULL_ROW_HIGHLIGHT | wx.TR_HIDE_ROOT)
        self.tree.AssignImageList(self.image_list)
        tree_sizer.Add(self.tree, 1, wx.EXPAND)

        # Evento de seleção de item na árvore
        def on_tree_select(event):
            # get the previous tree selection
            item_old = event.GetOldItem()
            item_new = event.GetItem()
            param_id_old, param_key_old = self.tree.GetItemData(item_old) if item_old else (None, None)
            param_id_new, param_key_new = self.tree.GetItemData(item_new) if item_new else (None, None)

            if param_id_old == param_id_new:
                return
            
            self.selected_parameter = param_id_new

            self.populate_table(self.data, self.selected_parameter)
            #self.populate_prompt_editor()

        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, on_tree_select)

        # Drag and drop support
        def on_tree_begin_drag(event):
            item = event.GetItem()
            if item.IsOk():
                param_id, param_key = self.tree.GetItemData(item)
                if param_key is not None:  # Only allow dragging variable names, not table names
                    # Create a text data object with the variable name
                    text_data = wx.TextDataObject(f"{{{param_key}}}")
                    drag_source = wx.DropSource(self.tree)
                    drag_source.SetData(text_data)
                    result = drag_source.DoDragDrop(True)

        self.tree.Bind(wx.EVT_TREE_BEGIN_DRAG, on_tree_begin_drag)

        # Menu de contexto para a árvore
        def on_tree_right_click(event):
            menu = wx.Menu()
            # função de bind em cada item do menu
            #menu.Append(1, "Add directory...")
            #menu.Append(2, "Add file...")
            #menu.AppendSeparator()
            menu.Append(3, "Remove")
            menu.AppendSeparator()
            menu.Append(4, "Rename")
            menu.Append(5, "Transform...")
            menu.Append(6, "Truncate")
            menu.Append(7, "Remove Duplicates")
            menu.AppendSeparator()
            menu.Append(8, "Move Up")
            menu.Append(9, "Move Down")


            # Evento de clique do menu de contexto
            def on_menu_click(event):
                item = event.GetId()
                if item == 1:
                    self.add_table_from_directory()
                elif item == 2:
                    self.add_table_from_file()
                elif item == 3:
                    self.remove_selected_param()
                elif item == 4:
                    self.rename_selected_item()
                elif item == 5:
                    self.apply_transform()
                elif item == 6:
                    self.truncate_selected_param()
                elif item == 7:
                    self.remove_duplicates()
                elif item == 8:
                    self.move_selection_up()
                elif item == 9:
                    self.move_selection_down()

            self.Bind(wx.EVT_MENU, on_menu_click)

            self.tree.PopupMenu(menu)
        
        self.tree.Bind(wx.EVT_RIGHT_DOWN, on_tree_right_click)

        # Add the same events to the buttons
        #add_dir_button.Bind(wx.EVT_BUTTON, lambda event: self.add_param_directory())
        #add_file_button.Bind(wx.EVT_BUTTON, lambda event: self.add_param_file())
        remove_table_button.Bind(wx.EVT_BUTTON, lambda event: self.remove_selected_param())
        #add_list_button.Bind(wx.EVT_BUTTON, lambda event: self.add_param_list())
        save_button.Bind(wx.EVT_BUTTON, lambda event: self.save_project())
        open_button.Bind(wx.EVT_BUTTON, lambda event: self.open_project())
        

        #add_list_button will show a menu with the options to "Add File", "Add Directory", etc.
        def on_add_list(event):
            menu = wx.Menu()
            menu.Append(2, "Add Spreadsheet")
            menu.Append(3, "Add Directory")
            menu.Append(1, "Add Manual List")

            def on_menu_click(event):
                item = event.GetId()
                try:
                    if item == 1:
                        self.add_table_from_list()
                    elif item == 2:
                        self.add_table_from_file()
                    elif item == 3:
                        self.add_table_from_directory()
                except ValueError as e:
                    wx.MessageBox(f"Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

            menu.Bind(wx.EVT_MENU, on_menu_click)

            add_table_button.PopupMenu(menu)

        add_table_button.Bind(wx.EVT_BUTTON, on_add_list)


        left_panel.SetSizer(tree_sizer)

        # Grid de detalhes no painel direito
        self.table = ULC.UltimateListCtrl(right_panel, agwStyle=ULC.ULC_REPORT | ULC.ULC_VRULES | ULC.ULC_HRULES | ULC.ULC_SINGLE_SEL | ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)
        
        # on select row
        def on_table_select(event):
            row = event.GetIndex()
            item = self.tree.GetSelection()
            param_id, _ = self.tree.GetItemData(item)
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

    def save_project(self, force_save_as=False):
        if self.data.file_path is None or force_save_as:
            dialog = wx.FileDialog(self, "Save Project", wildcard=f"Prompt Blender Project (*.{PROJECT_FILE_EXTENSION})|*.{PROJECT_FILE_EXTENSION}", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if dialog.ShowModal() == wx.ID_OK:
                path = dialog.GetPath()
                # Append the file extension
                if not path.endswith(f".{PROJECT_FILE_EXTENSION}"):
                    path += f".{PROJECT_FILE_EXTENSION}"

                self.data.save_to_file(path)
                self.preferences.add_recent_file(path)
                self.update_recent_files()

            else:
                # Cancelled
                return False  
        else:
            self.data.save_to_file()
        return True

    def save_project_as(self):
        self.save_project(force_save_as=True)
        
    def ask_save_changes(self):
        if self.data.is_modified:
            # Ask to save, with 3 options: Don't save, Save, Cancel
            # Use messageDialog to customize the labels and color
            dialog = wx.MessageDialog(self, "Save changes to project?", "Save", wx.YES_NO | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_QUESTION)
            dialog.SetYesNoCancelLabels("&Save", "&Don't Save", "&Cancel")
            
            ret = dialog.ShowModal()
            
            if ret == wx.ID_YES:
                return self.save_project(None)
            elif ret == wx.ID_CANCEL:
                return False
        return True

    def open_project(self):
        if not self.ask_save_changes():
            return  # Cancelled
        dialog = wx.FileDialog(self, "Open Project", wildcard="Prompt Blender Project (*.pbp)|*.pbp", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            try:
                self.data = Model.create_from_file(path)
                self.data.add_on_modified_callback(self.update_project_state)
                self.reset_view_mode()
                self.populate_data()
                self.preferences.add_recent_file(path)
                self.update_recent_files()
            except ValueError as e:
                wx.MessageBox(f"Error loading project: {e}", "Error", wx.OK | wx.ICON_ERROR)
            
    def close_project(self):
        if not self.ask_save_changes():
            return  # Cancelled
        self.data = Model.create_empty()
        self.data.add_on_modified_callback(self.update_project_state)

        self.reset_view_mode()
        self.populate_data()

    def add_table_from_directory(self):
        # Apresentar caixa de dialogo
        dialog = wx.DirDialog(self, "Selecione um diretório")
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()

            #options = {}
            #options['encoding'] = self.ask_encoding()
            #options['split_count'] = self.ask_split_count()
            #options['split_length'] = self.ask_split_length()

            options = self.ask_directory_options()

            self.data.add_table_from_directory(path, **options)
            self.populate_data()

    def ask_directory_options(self):
        # Ask, in a single dialog, encoding, split_length (integer) and split_count (-1: last, 0: all, n: first n)
        dialog = wx.Dialog(self, style=wx.DEFAULT_DIALOG_STYLE)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog.SetSizer(dialog_sizer)
        dialog.SetTitle("Directory Options")
        dialog.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        dialog.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        dialog.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        # Encoding
        encodings = ["utf-8", "latin1", "windows-1252", "utf-16", "utf-32", "ascii"]
        encodings.sort()
        default_encoding = "utf-8"
        encoding_label = wx.StaticText(dialog, label="Encoding:")
        encoding_choice = wx.Choice(dialog, choices=encodings)
        encoding_choice.SetSelection(encodings.index(default_encoding))
        dialog_sizer.Add(encoding_label, 0, wx.ALL, 5)
        dialog_sizer.Add(encoding_choice, 0, wx.EXPAND | wx.ALL, 5)

        # Split length
        split_length_label = wx.StaticText(dialog, label="Split Length (bytes):")
        split_length_text = wx.TextCtrl(dialog, value="8000000")  # Default value
        dialog_sizer.Add(split_length_label, 0, wx.ALL, 5)
        dialog_sizer.Add(split_length_text, 0, wx.EXPAND | wx.ALL, 5)

        # Split count
        split_count_label = wx.StaticText(dialog, label="Maximum split Count (0: all, n: first n, -n: last n):")
        split_count_text = wx.TextCtrl(dialog, value="0")  # Default value
        dialog_sizer.Add(split_count_label, 0, wx.ALL, 5)
        dialog_sizer.Add(split_count_text, 0, wx.EXPAND | wx.ALL, 5)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(dialog, wx.ID_OK, label="OK")
        cancel_button = wx.Button(dialog, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        dialog_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER)
        dialog_sizer.AddSpacer(10)

        # Fit dialog to content and set fixed size
        dialog.Fit()
        dialog.SetMinSize(dialog.GetSize())
        dialog.SetMaxSize(dialog.GetSize())
        dialog.SetSize(dialog.GetSize())
        dialog.Layout()

        # Show the dialog
        if dialog.ShowModal() == wx.ID_OK:
            encoding = encoding_choice.GetStringSelection()
            try:
                split_length = int(split_length_text.GetValue())
                split_count = int(split_count_text.GetValue())
            except ValueError:
                wx.MessageBox("Invalid split length or count. Please enter valid integers.", "Error", wx.OK | wx.ICON_ERROR)
                dialog.Destroy()
                return None

            dialog.Destroy()
            return {'encoding': encoding,
                    'split_length': split_length,
                    'split_count': split_count}
        else:
            dialog.Destroy()
            return None

    def add_table_from_file(self):
        # txt, xlsx, csv, xls
        wildcards = "All supported files|*.txt;*.xlsx;*.xls;*.csv;*.json;*.jsonl|Text files (*.txt)|*.txt|Excel files (*.xlsx, *.xls)|*.xlsx;*.xls|CSV files (*.csv)|*.csv|JSON files (*.json)|*.json|JSON Line files (*.jsonl)|*.jsonl"

        # Apresentar caixa de dialogo,
        dialog = wx.FileDialog(self, "Selecione um arquivo", wildcard=wildcards, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)

        if dialog.ShowModal() == wx.ID_OK:
            try:
                paths = dialog.GetPaths()

                # Set maximum rows from preferences
                maximum_rows = self.preferences.max_rows

                options = {}

                # if there is any csv or txt file, ask for encoding
                if any(path.endswith(".csv") or path.endswith(".txt") for path in paths):
                    options['encoding'] = self.ask_encoding()

                for path in paths:
                    self.data.add_table_from_file(path, maximum_rows=maximum_rows, **options)
                self.populate_data()
            except ValueError as e:
                wx.MessageBox(f"Error: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def ask_encoding(self):
        # Show combobox with most common encodings
        encodings = SUPPORTED_ENCODINGS
        encodings.sort()
        default_encoding = "utf-8"

        # dialog with choice/combobox with encoding. User can set a custom encoding
        dialog = wx.SingleChoiceDialog(self, "Select the file encoding", "File Encoding", encodings, 
                                       style=wx.CHOICEDLG_STYLE)
        dialog.SetSelection(encodings.index(default_encoding))
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.GetStringSelection()




    def add_table_from_list(self):
        # Show a dialog to enter text in multiline mode
        #dialog = wx.TextEntryDialog(self, "Enter the list of values, one per line", "Add List", "", style=wx.TE_MULTILINE | wx.OK | wx.CANCEL)
        with InputListDialog(self, "Add List", "Enter the list of values, one per line") as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                values = dialog.GetValue()
                extension = dialog.GetExtension()
                self.data.add_table_from_string(values, extension, maximum_rows=self.preferences.max_rows)
                self.populate_data()

    def apply_transform(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            param_id, _ = self.tree.GetItemData(item)

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
                    param_id, _ = self.tree.GetItemData(item)
                    self.data.truncate_param(param_id, n)
                    self.populate_data()
            except ValueError:
                wx.MessageBox("Error: Invalid number of lines", "Error", wx.OK | wx.ICON_ERROR)

    def remove_duplicates(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            param_id, _ = self.tree.GetItemData(item)
            self.data.remove_duplicates(param_id)
            self.populate_data()

    def remove_selected_param(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            param_id, param_key = self.tree.GetItemData(item)

            # Ask for confirmation
            if param_key is not None:
                param_label = f'"{param_key}" (child of {param_id})'
            else:
                param_label = f'"{param_id}" (and all its children)'
            ret = wx.MessageBox(f"Are you sure you want to remove the selected item?\nName: {param_label}", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
            if ret != wx.YES:
                return

            if param_key is None:
                self.data.remove_param(param_id)
            else:
                self.data.remove_param_key(param_id, param_key)
            self.populate_data()

    def rename_selected_item(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            table_name, variable_name = self.tree.GetItemData(item)
            if variable_name is not None:
                dialog = wx.TextEntryDialog(self, "Enter the new variable name", "Rename", variable_name)
                if dialog.ShowModal() == wx.ID_OK:
                    new_name = dialog.GetValue()
                    self.data.rename_variable(table_name, variable_name, new_name)
                    self.populate_data()
            else:
                dialog = wx.TextEntryDialog(self, "Enter the new table name", "Rename", table_name)
                if dialog.ShowModal() == wx.ID_OK:
                    new_name = dialog.GetValue()
                    self.data.rename_table(table_name, new_name)
                    self.populate_data()

        # Move up and down
    def move_selection_up(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            self.data.move_param(self.selected_parameter, -1)
            self.populate_tree(self.data)
            
    def move_selection_down(self):
        item = self.tree.GetSelection()
        if item.IsOk():
            self.data.move_param(self.selected_parameter, 1)
            self.populate_tree(self.data)

    def populate_data(self):
        self.selected_parameter = self.data.get_first_parameter()
        self.populate_tree(self.data)
        self.populate_table(self.data, self.selected_parameter)
        self.populate_notebook(self.data)
        self.update_project_state()
        self.update_run_configurations()

        # Remove focus from any control
        self.SetFocus()

    def reset_view_mode(self):
        self.view_mode.SetSelection(0)

    def update_run_configurations(self):
        # Update the run configurations dialog with the current data
        print(self.data.run_configurations)
        self.execute_dialog.set_configurations(self.data.run_configurations)

    def update_project_state(self):
        # Set Title
        name = self.data.file_path
        if name is None:
            name = "Untitled Project"
        else:
            # Relative path to the project file if it is a subdirectory of the current directory
            if name.startswith(os.getcwd()):
                name = os.path.relpath(name)

        modified_flag = "*" if self.data.is_modified else ""
        self.SetTitle(f"{MainFrame.TITLE} - {name}{modified_flag}")

        # Enable or disable menu items
        project_opened = self.data.file_path is not None
        self.main_menu.update_project_menu_state(project_opened)

        # Recent files
        self.update_recent_files()

    def update_recent_files(self):
        """Atualiza o menu de arquivos recentes usando a classe MainMenu"""
        self.main_menu.update_recent_files(self.preferences.recent_files)


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
            if self.notebook.GetPageCount() != len(self.data.get_prompt_names()) + 1:
                # The tabs are being changed by the program
                return
            # Get the selected page
            #page = self.notebook.GetSelection()
            selected_page_id = event.GetSelection()

            # Last page add new page and ask for name
            if selected_page_id == self.notebook.GetPageCount() - 1:
                new_prompt_name = self.data.add_prompt()

                # Add a new page
                prompt_page = PromptPage(self.notebook, self.data, new_prompt_name)
                self.notebook.InsertPage(selected_page_id, prompt_page, prompt_page.title)
                self.prompt_pages.append(prompt_page)

                #self.notebook.SetSelection(self.notebook.GetPageCount() - 2)
                event.Veto()

            # Remove focus from the prompt editor
            self.SetFocus()


        # Allow edit page name on right click
        def on_notebook_rename(event):
            selected_page_id = self.notebook.GetSelection()
            if selected_page_id == self.notebook.GetPageCount() - 1:
                return

            # Get the selected page
            prompt_page = self.prompt_pages[selected_page_id]

            # Ask for the new name
            dialog = wx.TextEntryDialog(self, "Enter the new name for the prompt", "Rename Prompt", prompt_page.title)
            if dialog.ShowModal() == wx.ID_OK:
                new_name = dialog.GetValue()
                if self.data.rename_prompt(prompt_page.title, new_name):
                    self.notebook.SetPageText(selected_page_id, new_name)
                    prompt_page.title = new_name



        def on_notebook_close(event):
            selected_page_id = self.notebook.GetSelection()
            # Get the selected page
            prompt_page = self.prompt_pages[selected_page_id]

            # Ask for confirmation
            ret = wx.MessageBox(f"Are you sure you want to delete \"{prompt_page.title}\"?", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
            if ret == wx.YES:
                self.data.remove_prompt(prompt_page.title)
                self.prompt_pages.pop(selected_page_id)
            else:
                event.Veto()

        def on_notebook_disable(event):
            selected_page_id = self.notebook.GetSelection()
            prompt_page = self.prompt_pages[selected_page_id]
            disabled = not prompt_page.is_disabled()
            prompt_page.set_disabled(disabled)
            self.data.set_prompt_disabled(prompt_page.title, disabled)

            self.refresh_prompts()

        #self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, on_notebook_change)
        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CLOSING, on_notebook_close)

        # event
        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CHANGED, on_notebook_change)


        # Add context menu SetRightClickMenu
        menu = wx.Menu()
        menu.Append(1, "Rename")
        menu.Append(2, "Delete")
        menu.Append(3, "Disable/Enable")
        #self.notebook.SetRightClickMenu(menu)
        # Last page cannot raise the context menu
        
        def on_notebook_context_menu_show(event):
            selected_page_id = event.GetSelection()
            if selected_page_id != self.notebook.GetPageCount() - 1:
                self.notebook.SetSelection(selected_page_id)
                page = self.notebook.GetPage(selected_page_id)
                page.PopupMenu(menu)
            else:
                self.notebook.SetRightClickMenu(None)
                return

        self.notebook.Bind(FNB.EVT_FLATNOTEBOOK_PAGE_CONTEXT_MENU, on_notebook_context_menu_show)

        # Bind menu click
        def on_notebook_menu(event):
            # Call on_notebook_rename or on_notebook_close
            item = event.GetId()
            if item == 1:
                on_notebook_rename(event)
            elif item == 2:
                self.notebook.DeletePage(self.notebook.GetSelection())
            elif item == 3:
                # Disable/Enable
                on_notebook_disable(event)



        menu.Bind(wx.EVT_MENU, on_notebook_menu)




        vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 0)



        # Horizontal box sizer for the checkbox and button. 
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Add "View Mode" choice list on the left of the hbox
        self.view_mode = wx.Choice(panel, choices=["Edit Mode", "View Prompt", "Debug Cache"])
        hbox.Add(self.view_mode, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.view_mode.SetSelection(0)

        # bind the checkbox event. 
        def on_view_mode(event):
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
        # Show message error if there is no prompt
        if self.data.get_number_of_prompts() == 0:
            wx.MessageBox("No prompts to execute.\nPlease, add at least one prompt", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Show message error if there is missing variable in the prompts
        error_pages = [page for page in self.prompt_pages if page.missing_variables]
        if error_pages:
            wx.MessageBox("Missing variables in the prompts.\nPlease, correct them before executing", "Error", wx.OK | wx.ICON_ERROR)
            # Select the first page with missing variables
            self.notebook.SetSelection(self.prompt_pages.index(error_pages[0]))
            return


        # Execute the prompts
        self.execute_error = None
        self.interrupted = False

        #self.progress_dialog.run_task(long_running_task)
        ret = self.execute_dialog.ShowModal()

        if ret == wx.ID_OK:
            self.progress_dialog.run_task(self.task_all)

    #def run_prompt(self):
    #    self.progress_dialog.run_task(self.task_all)

    def run_blend(self):
        self.progress_dialog.run_task(self.task_blend, auto_close=True)

    def task_blend(self):
        output_dir = self.preferences.cache_dir
        blend_prompt(self.data, output_dir, self.progress_dialog.update_progress)

    def expire_cache(self, expire_type='all'):
        # Ask for confirmation
        if expire_type == 'current_item':
            ret = wx.MessageBox("Are you sure you want to expire the cache?\nThis will remove the cached results for the current selected item.", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        elif expire_type == 'all':
            ret = wx.MessageBox("Are you sure you want to expire the cache?\nThis will remove ALL cached results for this execution.", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        elif expire_type == 'error_items':
            ret = wx.MessageBox("Are you sure you want to expire the cache?\nThis will remove cached results for items that had errors in JSON analysis.", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        else:
            return
    
        if ret != wx.YES:
            return
        
        # Expire the cache
        output_dir = self.preferences.cache_dir
        run_args = self.data.get_run_args(self.llm_modules)

        expired_count = 0

        for _, run in run_args.items():
            if expire_type == 'all':
                current_combinations = None
                error_items_only = False
            elif expire_type == 'error_items':
                current_combinations = None
                error_items_only = True
            elif expire_type == 'current_item':
                prompt_name = self.prompt_pages[self.notebook.GetSelection()].title
                current_combinations = [self.data.get_current_combination(prompt_name)]
                error_items_only = False

            r = execute_llm.expire_cache(run, self.data, output_dir, cache_timeout=0, combinations=current_combinations, error_items_only=error_items_only)  #, progress_callback=self.progress_dialog.update_progress)
            expired_count += r

        if expired_count == 0:
            wx.MessageBox("No cached items to expire.", "Information", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox(f"{expired_count} cached items expired successfully.", "Success", wx.OK | wx.ICON_INFORMATION)

    def import_cache(self, read_only=True):
        """Import cache from a ZIP file containing results"""
        # Ask for ZIP file to import
        dialog = wx.FileDialog(self, "Select ZIP file to import cache from", wildcard="Zip files (*.zip)|*.zip", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() != wx.ID_OK:
            return
        zip_path = dialog.GetPath()
        
        # Confirm import
        mode = "read-only" if read_only else "overwrite"
        ret = wx.MessageBox(f"Are you sure you want to import cache from '{os.path.basename(zip_path)}' in {mode} mode?\nThis will copy cached results to your current cache directory.", "Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        if ret != wx.YES:
            return
        
        try:
            stats = self._import_cache_from_zip(zip_path, read_only=read_only)
            message = f"Cache import completed:\n" \
                     f"Copied: {stats['copied']}\n" \
                     f"Equal: {stats['equal']}\n" \
                     f"Different: {stats['different']}"
            wx.MessageBox(message, "Import Results", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error importing cache: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _import_cache_from_zip(self, zip_path, read_only=False):
        """Extract cache folder from ZIP file to current cache directory
        
        Args:
            zip_path (str): Path to the ZIP file
            read_only (bool): If True, do not modify files, just return statistics
            
        Returns:
            dict: Statistics with keys 'copied', 'equal', 'different'
        """
        import zipfile
        import os
        
        cache_dir = os.path.join(self.preferences.cache_dir, 'cache')
        stats = {'copied': 0, 'equal': 0, 'different': 0}
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Find all files in the 'cache' folder within the ZIP
            cache_files = [f for f in zipf.namelist() if f.startswith('cache/')]
            
            for file_path in cache_files:
                # Extract to the cache directory, maintaining the relative path
                target_path = os.path.join(cache_dir, os.path.relpath(file_path, 'cache'))
                
                # Read content from ZIP
                with zipf.open(file_path) as source:
                    zip_content = source.read().decode('utf-8')
                
                if os.path.exists(target_path):
                    # File exists, compare content
                    with open(target_path, 'r', encoding='utf-8') as target:
                        existing_content = target.read()
                    
                    if zip_content == existing_content:
                        stats['equal'] += 1
                    else:
                        stats['different'] += 1
                        if not read_only:
                            # Overwrite
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'w', encoding='utf-8') as target:
                                target.write(zip_content)
                            # Already counted as different
                else:
                    print(">", target_path)
                    # File does not exist
                    stats['copied'] += 1
                    if not read_only:
                        # Copy it
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'w', encoding='utf-8') as target:
                            target.write(zip_content)
        
        return stats

    def task_all(self):
        #llm_module = self.execute_dialog.get_selected_module()
        #cache_timeout = self.execute_dialog.get_cache_timeout()
        #print('Task All', llm_module)
        cache_timeout = None

        wx.CallAfter(self.update_project_state)

        #output_dir = "output_teste"
        output_dir = self.preferences.cache_dir
        blend_prompt(self.data, output_dir)
        
        # Execute the LLM
        #module_args = self.execute_dialog.get_module_args()

        # Each run configuration is a module with its own arguments
        run_args = self.data.get_run_args(self.llm_modules)

        max_timestamp = ''

        for name, run in run_args.items():

            try:
                max_cost = self.preferences.max_cost
                timestamp = execute_llm.execute_llm(run, self.data, output_dir, progress_callback=self.progress_dialog.update_progress, cache_timeout=cache_timeout, max_cost=max_cost, gui=True)
                max_timestamp = max(max_timestamp, timestamp)

                if not self.progress_dialog.running:
                    self.interrupted = True
                    break

            except Exception as e:
                self.execute_error = str(e)
                wx.CallAfter(self.execution_done)
                
                # print stack trace
                import traceback
                traceback.print_exc()
                return

        if not self.interrupted:
            self.export_current_results(max_timestamp)

        wx.CallAfter(self.update_project_state)

        wx.CallAfter(self.execution_done)

    def export_current_results(self, timestamp=None):
        run_args = self.data.get_run_args(self.llm_modules)
        output_dir = self.preferences.cache_dir

        analysis_results = {}
        for name, run in run_args.items():
            ret = analyse_results.analyse_results(run, self.data, output_dir, self.analyse_functions)
            analysis_results[name] = ret

        if all([x == {} for x in analysis_results.values()]):
            return None

        if timestamp is None:
            timestamp = int(datetime.now().timestamp())

        # The zipfile name is the result name with the timestamp
        zipfile_name = f'tmp_{timestamp}.zip'
        result_filename = os.path.join(output_dir, zipfile_name)

        # Create the final zip file with all analysis results
        result_file.save_analysis_results(result_filename, output_dir, analysis_results, self.data, run_args)

        return result_filename


       
    def execution_done(self):
        if self.execute_error:
            wx.MessageBox(f"LLM Execution error: {self.execute_error}", "Erro", wx.OK | wx.ICON_ERROR)
        elif self.interrupted:
            wx.MessageBox("Interrupted Excecution", "Interruption", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("LLM Execution successful", "Success", wx.OK | wx.ICON_INFORMATION)
            self.export_results()

        self.progress_dialog.Hide()


    def export_results(self):
        result_filename = self.export_current_results()

        if result_filename is None:
            wx.MessageBox("Nenhum resultado para exportar", "Erro", wx.OK | wx.ICON_ERROR)
            return

        if self.data.file_path is None:
            prefix = "untitled"
        else:
            prefix = os.path.splitext(self.data.file_path)[0]

        # default filename is the project filename without extension and the "results.zip" suffix.
        default_filename = f"{prefix}_results.zip"

        # Ask filename to save the results in zip format. If the file exists, ask to overwrite
        dialog = wx.FileDialog(self, "Save Results", wildcard="Zip files (*.zip)|*.zip", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, defaultFile=default_filename)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            
            # copy the zip file to the selected path
            shutil.copy(result_filename, path)                

    def populate_notebook(self, data):
        self.notebook.DeleteAllPages()
        
        if data.get_number_of_prompts() == 0:
            data.add_prompt()

        self.prompt_pages = []
        first_enabled_page_id = None
        for prompt_name in data.get_prompt_names():
            prompt_page = PromptPage(self.notebook, self.data, prompt_name)
            disabled = data.is_prompt_disabled(prompt_name)
            prompt_page.set_disabled(disabled)
            self.notebook.AddPage(prompt_page, prompt_page.title)
            self.prompt_pages.append(prompt_page)

            if not disabled and first_enabled_page_id is None:
                first_enabled_page_id = len(self.prompt_pages) - 1

        # Select first enabled page
        if first_enabled_page_id is not None:
            self.notebook.SetSelection(first_enabled_page_id)

        # Add a page with a "+" icon to add new prompts
        self.notebook.AddPage(wx.Panel(self.notebook), "", imageId=2) 

        # refresh the prompts
        self.refresh_prompts()

        

    def populate_tree(self, data):
        self.tree.DeleteAllItems()  # Limpar a árvore existente
        root = self.tree.AddRoot("Parâmetros", data=(None, None))

        variable_names = set()

        # Carregar parâmetros na árvore
        for group_name, group in data.parameters.items():
            # Group node with italic font
            # f"Parameter Group {index+1}"
            group_node = self.tree.AppendItem(root, text=group_name, data=(group_name, None))
            self.tree.SetItemFont(group_node, wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
            # gray color
            self.tree.SetItemTextColour(group_node, wx.Colour(64, 64, 64))
            
            # Add imagem to the group node
            self.tree.SetItemImage(group_node, 0, wx.TreeItemIcon_Normal)

            if group_name == self.selected_parameter:
                self.tree.SelectItem(group_node)

            if len(group) == 0:
                # Add a dummy item to show that the group is empty
                item = self.tree.AppendItem(group_node, text="(empty)", data=(group_name, None))
                # In gray
                self.tree.SetItemTextColour(item, wx.Colour(128, 128, 128))
                # italic
                self.tree.SetItemFont(item, wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))

            else:
                for key in group[0].keys():
                    if not key.startswith("_"):
                        if key in variable_names:
                            # insert tag after the item (in the right)
                            tag = " (duplicated)"
                        else:
                            tag = ""
                            variable_names.add(key)
                        item = self.tree.AppendItem(group_node, text=f"{key}{tag}", data=(group_name, key))
                        self.tree.SetItemTextColour(item, data.add_variable_color(key))

        self.tree.ExpandAll()  # Expandir todos os nós para visualização completa

    def populate_table(self, data, param_group_name):
        self.table.Freeze()

        # Set table size
        self.table.ClearAll()

        # Obter os detalhes do parâmetro selecionado
        param = data.get_parameter(param_group_name)
        if param is None or len(param) == 0:
            self.table.InsertColumn(0, "No data", width=500)
            self.table.Thaw()
            return
        else:
            table = pd.DataFrame(param)

        # Set column names
        for i, col in enumerate(table.columns):
            self.table.InsertColumn(i, col)
            
        
        # Preencher com os dados
        for i, row in enumerate(table.values):
            max_rows = 50
            if i >= max_rows:
                self.table.InsertStringItem(i, f'... Showing only the first {max_rows} rows. Total: {len(table)} ...')
                break
            self.table.InsertStringItem(i, str(i+1))

            for j, value in enumerate(row):
                s = str(value)
                if len(s) > 50:
                    s = s[:50] + "..."
                self.table.SetStringItem(i, j, s)
                

        # Select the row
        self.table.Select(data.get_selected_item(param_group_name))

        # Best fit column widths
        for i in range(len(table.columns)-1):
            self.table.SetColumnWidth(i, ULC.ULC_AUTOSIZE)
        # Last column size equal to panel size
        width = max(self.table.GetSize()[0], 500)
        self.table.SetColumnWidth(len(table.columns)-1, width)
            
        # Set second column to purple color
        for i in range(len(table)):
            # COlumn! not row
            #self.table.SetItemBackgroundColour(i, wx.Colour(255, 200, 255))
            #self
            pass


        self.table.Thaw()



    def refresh_prompts(self):
        run_args = self.data.get_run_args(self.llm_modules)
        run_hashes = {run_name: run_args['run_hash'] 
                      for run_name, run_args in run_args.items()}

        for idx, prompt_page in enumerate(self.prompt_pages):
            prompt_page.view_mode = self.view_mode.GetSelection()
            prompt_page.run_hashes = run_hashes
            prompt_page.output_dir = self.preferences.cache_dir  # FIXME: this should be made in a better way

            prompt_page.refresh()

            # if the page is disabled, set the title color to gray
            if prompt_page.is_disabled():
                self.notebook.SetPageTextColour(idx, wx.Colour(200, 200, 200))       
            else:     
                # default color
                self.notebook.SetPageTextColour(idx, wx.Colour(0, 0, 0))



def run(model=None):
    app = wx.App(False)
    frame = MainFrame(None, model=model)
    app.MainLoop()


if __name__ == '__main__':
    run()
