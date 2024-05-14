import wx
import threading
from prompt_blender.llms import execute_llm

class ProgressDialog(wx.Dialog):
    def __init__(self, parent, title):
        super(ProgressDialog, self).__init__(parent, title=title, size=(300, 200))

        self.init_ui()
        self.Centre()

        self.running = False
        self.auto_close = False

    def run_task(self, task, auto_close=False):
        # Iniciar a thread de processamento
        self.running = True
        self.auto_close = auto_close
        self.task_thread = threading.Thread(target=task)
        self.task_thread.start()

        self.ShowModal()

        print("Task finished")
        

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Barra de progresso
        self.gauge = wx.Gauge(panel, range=0, size=(250, 25))
        vbox.Add(self.gauge, flag=wx.ALL | wx.EXPAND, border=10)

        # Informativo numérico x/y
        self.progress_text = wx.StaticText(panel, label=f"0/0")
        vbox.Add(self.progress_text, flag=wx.ALL | wx.CENTER, border=5)

        # Descrição do progresso da tarefa
        self.description_text = wx.StaticText(panel, label="")
        vbox.Add(self.description_text, flag=wx.ALL | wx.LEFT, border=5)

        # Botão de cancelar/concluir
        self.button = wx.Button(panel, label="Cancelar")
        self.button.Bind(wx.EVT_BUTTON, self.on_cancel)
        vbox.Add(self.button, flag=wx.ALL | wx.CENTER, border=10)

        panel.SetSizer(vbox)

    def update_progress(self, current_value, max_value, description):
        wx.CallAfter(self._update_progress, current_value, max_value, description)
        keep_running = self.running
        return keep_running
    
    def _update_progress(self, current_value, max_value, description):
        """Atualiza a barra de progresso e os textos informativos."""
        self.gauge.SetValue(current_value)
        self.gauge.SetRange(max_value)
        self.progress_text.SetLabel(f"{current_value}/{max_value}")
        self.description_text.SetLabel(description)

        if current_value >= max_value:
            if self.auto_close:
                self.Hide()
                wx.MessageBox(description, "Task Completed", wx.OK | wx.ICON_INFORMATION)
            else:
                self.button.SetLabel("Concluir")
                self.button.Unbind(wx.EVT_BUTTON)
                self.button.Bind(wx.EVT_BUTTON, self.on_finish)


    def on_cancel(self, event):
        self.running = False
        # FIXME SegFault 
        if self.task_thread.is_alive():
            self.task_thread.join()
        self.Hide()

    def on_finish(self, event):
        """Manipulador para o botão Concluir após a conclusão da tarefa."""
        self.Hide()

if __name__ == '__main__':
    app = wx.App(False)
    dialog = ProgressDialog(None, 'Progresso da Tarefa', 100)
    app.MainLoop()
