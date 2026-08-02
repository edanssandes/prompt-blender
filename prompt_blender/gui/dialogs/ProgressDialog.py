import wx
import wx.lib.agw.pygauge
import threading
import time


def _format_tokens(value):
    """Format a token count as millions with two decimals, or '-' when zero."""
    if not value:
        return "-"
    return f"{value / 1_000_000:.2f} M"


def _format_bytes(value):
    """Format a byte count as KB or MB (two decimals), or '-' when zero."""
    if not value:
        return "-"
    mb = value / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.2f} MB"
    return f"{value / 1024:.2f} KB"


def _format_cost(value):
    """Format a monetary cost with two decimals, or '-' when zero."""
    if not value:
        return "-"
    return f"{value:.2f}"


def _format_cost_pair(current_value, max_value):
    """Format monetary values as (current, max) with two decimals or '-' when zero."""
    return _format_cost(current_value), _format_cost(max_value)


class ProgressDialog(wx.Dialog):
    def __init__(self, parent, title):
        super(ProgressDialog, self).__init__(parent, title=title, size=(420, 300))

        self.init_ui()
        self.Centre()

        self.running = False
        self.auto_close = False
        self.task_thread = None

    def run_task(self, task, auto_close=False):
        # Iniciar a thread de processamento
        self.running = True
        self.auto_close = auto_close
        self.task_thread = threading.Thread(target=task)
        self.task_thread.start()

        self.reset_progress()
        self.ShowModal()

        print("Task finished")
        
    def reset_progress(self):
        self.gauge.SetValue(0)
        self.gauge.SetRange(100)
        self.gauge.SetDrawValue(draw=True, drawPercent=False, formatString="")
        self.gauge.Refresh()

        self.description_text.SetLabel("Initializing task...")
        self._reset_stats()

    def _reset_stats(self):
        self.tokens_in_value.SetLabel("-")
        self.tokens_out_value.SetLabel("-")
        self.bytes_in_value.SetLabel("-")
        self.bytes_out_value.SetLabel("-")
        self.cost_current_value.SetLabel("-")
        self.cost_max_value.SetLabel("-")

    def init_ui(self):
        panel = self.panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Barra de progresso
        #self.gauge = wx.lib.agw.pygauge.PyGauge(panel, -1, size=(250, 25), style=wx.GA_HORIZONTAL)
        self.gauge = wx.lib.agw.pygauge.PyGauge(panel, -1, size=(9999, 25), style=wx.GA_HORIZONTAL)
        self.gauge.SetBackgroundColour(wx.WHITE)
        self.gauge.SetBarColour(wx.Colour(128, 164, 255))
        self.gauge.SetBorderColor(wx.Colour(128, 128, 128))
        self.gauge.SetBorderPadding(1)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, border=12)

        # Descrição do progresso da tarefa
        self.description_text = wx.StaticText(panel, label="")
        vbox.Add(self.description_text, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

        # Usage panel (tokens / bytes / cost)
        vbox.Add(self._build_stats_panel(panel), 0,
                 wx.EXPAND | wx.LEFT | wx.RIGHT, border=12)

        # Botão de cancelar/concluir
        self.button = wx.Button(panel)
        vbox.Add(self.button, flag=wx.ALL | wx.CENTER, border=12)
        self._update_button()

        # When closing the dialog, call the cancel method
        self.Bind(wx.EVT_CLOSE, self.on_cancel)

        self.reset_progress()

        panel.SetSizer(vbox)

    def _build_stats_panel(self, parent):
        box = wx.StaticBox(parent, label="Usage")
        box.SetForegroundColour(wx.Colour(90, 90, 90))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=3, cols=3, vgap=8, hgap=16)
        grid.AddGrowableCol(1, 1)
        grid.AddGrowableCol(2, 1)

        label_colour = wx.Colour(110, 110, 110)
        value_colour = wx.Colour(30, 30, 30)

        def make_label(text):
            st = wx.StaticText(box, label=text)
            st.SetForegroundColour(label_colour)
            return st

        def make_value(text="-"):
            st = wx.StaticText(box, label=text, style=wx.ALIGN_LEFT)
            font = st.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            st.SetFont(font)
            st.SetForegroundColour(value_colour)
            return st

        # Column headers (Input / Output)
        grid.Add(make_label(""), 0, wx.ALIGN_CENTER_VERTICAL)
        header_in = make_label("Input")
        header_out = make_label("Output")
        grid.Add(header_in, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(header_out, 0, wx.ALIGN_CENTER_VERTICAL)

        # Tokens row
        grid.Add(make_label("Tokens (M)"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tokens_in_value = make_value()
        self.tokens_out_value = make_value()
        grid.Add(self.tokens_in_value, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.tokens_out_value, 0, wx.ALIGN_CENTER_VERTICAL)

        # Data row (bytes)
        grid.Add(make_label("Data"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.bytes_in_value = make_value()
        self.bytes_out_value = make_value()
        grid.Add(self.bytes_in_value, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.bytes_out_value, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, border=8)

        # Total cost
        cost_row = wx.BoxSizer(wx.HORIZONTAL)
        cost_label = wx.StaticText(box, label="Total Cost (US$)")
        cost_label.SetForegroundColour(label_colour)
        self.cost_current_value = wx.StaticText(box, label="-")
        cost_font = self.cost_current_value.GetFont()
        cost_font.SetWeight(wx.FONTWEIGHT_BOLD)
        cost_font.SetPointSize(cost_font.GetPointSize() + 1)
        self.cost_current_value.SetFont(cost_font)
        self.cost_current_value.SetForegroundColour(wx.Colour(0, 120, 60))
        self.cost_separator_value = wx.StaticText(box, label="  limit: ")
        self.cost_separator_value.SetForegroundColour(wx.Colour(120, 140, 140))
        self.cost_max_value = wx.StaticText(box, label="-")
        self.cost_max_value.SetFont(cost_font)
        self.cost_max_value.SetForegroundColour(wx.Colour(120, 140, 140))
        cost_row.Add(cost_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
        cost_row.Add(self.cost_current_value, 0, wx.ALIGN_CENTER_VERTICAL)
        cost_row.Add(self.cost_separator_value, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, border=4)
        cost_row.Add(self.cost_max_value, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(cost_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        return sizer

    def update_progress(self, current_value, max_value, description, stats=None):
        wx.CallAfter(self._update_progress, current_value, max_value, description, stats)
        keep_running = self.running
        return keep_running
    
    def _update_progress(self, current_value, max_value, description, stats=None):
        """Atualiza a barra de progresso e os textos informativos."""
        self.gauge.SetRange(max(max_value, 1))
        self.gauge.SetValue(current_value)
        self.gauge.SetDrawValue(draw=True, drawPercent=False, formatString=f"{current_value}/{max_value}")
        self.gauge.Refresh()

        self.description_text.SetLabel(description)

        if stats is not None:
            self._update_stats(stats)

        self._update_button(current_value, max_value)

        if current_value >= max_value:
            if self.auto_close:
                self.Hide()
                wx.MessageBox(description, "Task Completed", wx.OK | wx.ICON_INFORMATION)

    def _update_stats(self, stats):
        self.tokens_in_value.SetLabel(_format_tokens(getattr(stats, 'tokens_in', 0)))
        self.tokens_out_value.SetLabel(_format_tokens(getattr(stats, 'tokens_out', 0)))
        self.bytes_in_value.SetLabel(_format_bytes(getattr(stats, 'bytes_in', 0)))
        self.bytes_out_value.SetLabel(_format_bytes(getattr(stats, 'bytes_out', 0)))
        cost_current, cost_max = _format_cost_pair(
            getattr(stats, 'cost', 0),
            getattr(stats, 'max_cost', 0),
        )
        self.cost_current_value.SetLabel(cost_current)
        self.cost_max_value.SetLabel(cost_max)
        self.panel.Layout()

    def _update_button(self, current_value=-1, max_value=0):
        if current_value >= max_value:
            self.button.SetLabel("Concluir")
            self.button.Unbind(wx.EVT_BUTTON)
            self.button.Bind(wx.EVT_BUTTON, self.on_finish)
        else:
            self.button.SetLabel("Cancelar")
            self.button.Unbind(wx.EVT_BUTTON)
            self.button.Bind(wx.EVT_BUTTON, self.on_cancel)



    def on_cancel(self, event):
        self.running = False
        print("Task canceled")

        if self.task_thread is None:
            self.Hide()
            return

        # FIXME SegFault 
        if self.task_thread.is_alive():
            print("Waiting for thread to finish")
            self.task_thread.join()

        print("Thread finished", self.running)
        self.Hide()

    def on_finish(self, event):
        """Manipulador para o botão Concluir após a conclusão da tarefa."""
        self.Hide()

if __name__ == '__main__':
    class _DemoStats:
        tokens_in = 0
        tokens_out = 0
        bytes_in = 0
        bytes_out = 0
        cost = 0.0
        max_cost = 10.0

    def dummy_task(dialog):
        """Simula uma tarefa com progresso de 1 a 100."""
        stats = _DemoStats()
        for i in range(1, 100):
            stats.tokens_in += 12345
            stats.tokens_out += 3456
            stats.bytes_in += 5120
            stats.bytes_out += 1300
            stats.cost += 0.03123
            if not dialog.update_progress(i, 100, "Processando itens...", stats):
                break  # Cancelado
            time.sleep(0.05)

        dialog.update_progress(100, 100, "Concluído com sucesso", stats)
    
    app = wx.App(False)
    dialog = ProgressDialog(None, 'Progresso da Tarefa')
    dialog.run_task(lambda: dummy_task(dialog), auto_close=True)
    app.MainLoop()
