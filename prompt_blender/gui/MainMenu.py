import wx
import wx.adv
import prompt_blender.info
import os
import glob


class MainMenu:
    """
    Classe responsável pela criação e gerenciamento do menu principal da aplicação.
    Utiliza callbacks para separar a lógica de negócio da interface.
    """
    
    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.menu_bar = None
        self.recent_menu = None
        
        # Template directory and files
        self.template_files = MainMenu.load_templates()
        
        # Callbacks - serão definidos pela classe principal
        self.callbacks = {
            'new_empty_project': None,
            'new_from_clipboard': None,
            'open_project': None,
            'save_project': None,
            'save_project_as': None,
            'close_project': None,
            'show_preferences': None,
            'exit_application': None,
            'run_combinations': None,
            'blend_prompts': None,
            'export_results': None,
            'expire_cache_all': None,
            'expire_cache_current_item': None,
            'expire_cache_error_items': None,
            'import_cache': None,
            'show_about': None,
            'open_recent_file': None,
            'load_example_template': None
        }

    @staticmethod
    def load_templates():
        """Carrega arquivos de template de um diretório específico"""
        templates_dir = os.path.join(os.path.dirname(__file__), 'examples')
        template_files = sorted(glob.glob(os.path.join(templates_dir, '*.pbp')))
        return template_files

    def set_callback(self, action, callback):
        """Define um callback para uma ação específica"""
        if action in self.callbacks:
            self.callbacks[action] = callback
        else:
            raise ValueError(f"Callback '{action}' não reconhecido")
    
    def create_menus(self):
        """Cria a estrutura completa do menu"""
        self.menu_bar = wx.MenuBar()
        
        # Criar menus principais
        file_menu = self._create_file_menu()
        run_menu = self._create_run_menu()
        help_menu = self._create_help_menu()
        
        # Adicionar menus à barra
        self.menu_bar.Append(file_menu, "File")
        self.menu_bar.Append(run_menu, "Run")
        self.menu_bar.Append(help_menu, "Help")
        
        # Configurar a barra de menu no frame
        self.parent.SetMenuBar(self.menu_bar)
        
        return self.menu_bar
    
    def _create_file_menu(self):
        """Cria o menu File"""
        file_menu = wx.Menu()
        
        # Submenu New Project
        new_project_menu = wx.Menu()
        new_project_menu.Append(100, "Empty Project")
        new_project_menu.Append(102, "From Clipboard")
        
        # Submenu From Example with template files
        example_menu = self._create_example_menu()
        new_project_menu.AppendSubMenu(example_menu, "From Example")
        
        file_menu.AppendSubMenu(new_project_menu, "New Project")
        
        # Outros itens do menu File
        file_menu.Append(wx.ID_OPEN, "Open Project")
        
        # Menu Recent Files
        self.recent_menu = wx.Menu()
        file_menu.AppendSubMenu(self.recent_menu, "Open Recent")
        
        file_menu.Append(wx.ID_SAVE, "Save Project")
        file_menu.Append(wx.ID_SAVEAS, "Save Project As ...")
        file_menu.Append(wx.ID_CLOSE, "Close Project")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_PREFERENCES, "Preferences...")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "Sair")
        
        # Bind eventos
        new_project_menu.Bind(wx.EVT_MENU, self._on_new_project)
        file_menu.Bind(wx.EVT_MENU, self._on_open_project, id=wx.ID_OPEN)
        file_menu.Bind(wx.EVT_MENU, self._on_save_project, id=wx.ID_SAVE)
        file_menu.Bind(wx.EVT_MENU, self._on_save_project_as, id=wx.ID_SAVEAS)
        file_menu.Bind(wx.EVT_MENU, self._on_close_project, id=wx.ID_CLOSE)
        file_menu.Bind(wx.EVT_MENU, self._on_preferences, id=wx.ID_PREFERENCES)
        file_menu.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        
        return file_menu
    
    def _create_run_menu(self):
        """Cria o menu Run"""
        run_menu = wx.Menu()
        
        run_menu.Append(3001, "Run Combinations")
        run_menu.AppendSeparator()
        run_menu.Append(3002, "Blend Prompts")
        run_menu.Append(3003, "Export Results")
        
        # Submenu Expire Cache
        expire_cache_menu = wx.Menu()
        expire_cache_menu.Append(3005, "All Items")
        expire_cache_menu.Append(3004, "Current Item")
        expire_cache_menu.Append(3006, "Error Items Only")
        #expire_cache_menu.Append(3007, "Import Cache")
        run_menu.AppendSubMenu(expire_cache_menu, "Expire Cache")
        
        # Bind eventos
        run_menu.Bind(wx.EVT_MENU, self._on_run_menu)
        
        return run_menu
    
    def _create_help_menu(self):
        """Cria o menu Help"""
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_ABOUT, "About")
        
        # Bind eventos
        help_menu.Bind(wx.EVT_MENU, self._on_about, id=wx.ID_ABOUT)
        
        return help_menu
    
    def _create_example_menu(self):
        """Cria o submenu From Example com os templates disponíveis"""
        example_menu = wx.Menu()
        
        if not self.template_files:
            example_menu.Append(4000, "No examples available")
            example_menu.Enable(4000, False)
        else:
            # Adicionar cada template como item do menu
            for i, template_file in enumerate(self.template_files):
                template_name = os.path.splitext(os.path.basename(template_file))[0]
                # Formatar o nome do template (substituir _ por espaços e capitalizar)
                display_name = template_name.replace('_', ' ').title()
                menu_id = 4000 + i
                example_menu.Append(menu_id, display_name)
        
        # Bind eventos para os templates
        example_menu.Bind(wx.EVT_MENU, self._on_example_template)
        
        return example_menu
    
    def update_recent_files(self, recent_files):
        """Atualiza o menu de arquivos recentes"""
        if not self.recent_menu:
            return
            
        # Limpar itens existentes
        for item in self.recent_menu.GetMenuItems():
            self.recent_menu.Remove(item)
        
        if not recent_files:
            self.recent_menu.Append(2000, "No recent files")
            self.recent_menu.Enable(2000, False)
            return
        
        # Adicionar arquivos recentes
        import os
        for i, file_path in enumerate(reversed(recent_files)):
            # Caminho relativo se for subdiretório do atual
            display_path = file_path
            if file_path.startswith(os.getcwd()):
                display_path = os.path.relpath(file_path)
                display_path = os.path.join(".", display_path)
            
            idx = 2000 + (len(recent_files) - 1 - i)
            self.recent_menu.Append(idx, f'{i+1:2d} {display_path}')
        
        # Bind evento para arquivos recentes
        self.parent.Bind(wx.EVT_MENU, self._on_recent_file, 
                        id=2000, id2=2000 + len(recent_files))
    
    def enable_menu_item(self, menu_id, enabled):
        """Habilita/desabilita um item do menu"""
        if self.menu_bar:
            self.menu_bar.Enable(menu_id, enabled)
    
    def update_project_menu_state(self, project_opened):
        """Atualiza o estado dos itens de menu relacionados ao projeto"""
        # Enable or disable menu items based on project state
        #self.enable_menu_item(wx.ID_SAVE, project_opened)
        self.enable_menu_item(wx.ID_SAVEAS, project_opened)
        self.enable_menu_item(wx.ID_CLOSE, project_opened)
    
    def update_results_menu_state(self, has_results):
        """Atualiza o estado dos itens de menu relacionados aos resultados"""
        # Enable or disable export results menu
        self.enable_menu_item(3003, has_results)
    
    # Event handlers
    def _on_new_project(self, event):
        """Handler para New Project"""
        event_id = event.GetId()
        if event_id == 100 and self.callbacks['new_empty_project']:
            self.callbacks['new_empty_project']()
        elif event_id == 102 and self.callbacks['new_from_clipboard']:
            self.callbacks['new_from_clipboard']()
    
    def _on_open_project(self, event):
        """Handler para Open Project"""
        if self.callbacks['open_project']:
            self.callbacks['open_project']()
    
    def _on_save_project(self, event):
        """Handler para Save Project"""
        if self.callbacks['save_project']:
            self.callbacks['save_project']()
    
    def _on_save_project_as(self, event):
        """Handler para Save Project As"""
        if self.callbacks['save_project_as']:
            self.callbacks['save_project_as']()
    
    def _on_close_project(self, event):
        """Handler para Close Project"""
        if self.callbacks['close_project']:
            self.callbacks['close_project']()
    
    def _on_preferences(self, event):
        """Handler para Preferences"""
        if self.callbacks['show_preferences']:
            self.callbacks['show_preferences']()
    
    def _on_exit(self, event):
        """Handler para Exit"""
        if self.callbacks['exit_application']:
            self.callbacks['exit_application']()
    
    def _on_run_menu(self, event):
        """Handler para itens do menu Run"""
        event_id = event.GetId()
        if event_id == 3001 and self.callbacks['run_combinations']:
            self.callbacks['run_combinations']()
        elif event_id == 3002 and self.callbacks['blend_prompts']:
            self.callbacks['blend_prompts']()
        elif event_id == 3003 and self.callbacks['export_results']:
            self.callbacks['export_results']()
        elif event_id == 3005 and self.callbacks['expire_cache_all']:
            self.callbacks['expire_cache_all']()
        elif event_id == 3004 and self.callbacks['expire_cache_current_item']:
            self.callbacks['expire_cache_current_item']()
        elif event_id == 3006 and self.callbacks['expire_cache_error_items']:
            self.callbacks['expire_cache_error_items']()
        elif event_id == 3007 and self.callbacks['import_cache']:
            self.callbacks['import_cache']()
    
    def _on_about(self, event):
        """Handler para About"""
        if self.callbacks['show_about']:
            self.callbacks['show_about']()
        else:
            # Implementação padrão do About
            self._show_default_about()
    
    def _on_recent_file(self, event):
        """Handler para arquivos recentes"""
        if self.callbacks['open_recent_file']:
            file_index = event.GetId() - 2000
            self.callbacks['open_recent_file'](file_index)
    
    def _on_example_template(self, event):
        """Handler para templates de exemplo"""
        if self.callbacks['load_example_template']:
            # Encontrar o arquivo de template baseado no ID do menu
            template_index = event.GetId() - 4000
            if 0 <= template_index < len(self.template_files):
                template_file = self.template_files[template_index]
                self.callbacks['load_example_template'](template_file)
    
    def _show_default_about(self):
        """Mostra o diálogo About padrão"""
        info = wx.adv.AboutDialogInfo()
        info.SetName("Prompt Blender")
        info.SetVersion(prompt_blender.info.__version__)
        info.SetDescription(prompt_blender.info.DESCRIPTION + "\n\n" + 
                           "Developed by " + prompt_blender.info.__author__)
        info.SetWebSite(prompt_blender.info.WEB_SITE)
        wx.adv.AboutBox(info)