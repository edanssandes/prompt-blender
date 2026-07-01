import re
import wx
import wx.grid


# Available field types and how they map to the generated JSON value.
# ``string`` is rendered as a quoted value, ``numeric/logical`` is unquoted.
TYPES = ['string', 'numeric/logical']


def fields_to_json(fields, multiple=False, indent='\t'):
    """Generate a (pseudo) JSON string from a list of field definitions.

    Each field is a dict with keys: name, type, description.
    For ``string`` fields the value is rendered as ``"<description>"`` (quoted),
    otherwise the value is rendered as ``<description>`` (unquoted).

    When ``multiple`` is True the object is wrapped as
    ``{"result": [ { ... } ]}``.
    """
    inner_indent = indent * 2 if multiple else indent

    lines = []
    for field in fields:
        name = field['name'].strip()
        if not name:
            continue
        desc = field['description'].strip()
        ftype = field['type']
        if ftype == 'string':
            value = f'"<{desc}>"'
        else:
            value = f'<{desc}>'
        lines.append(f'{inner_indent}"{name}": {value}')

    body = ',\n'.join(lines)

    if multiple:
        return (
            '{\n'
            f'{indent}"result": [\n'
            f'{indent}{{\n'
            f'{body}\n'
            f'{indent}}}\n'
            f'{indent}]\n'
            '}'
        )
    return '{\n' + body + '\n}'


def json_to_fields(text):
    """Best-effort parse of a (pseudo) JSON object into field definitions.

    Returns a tuple ``(fields, multiple)`` where ``fields`` is a list of dicts
    with keys name/type/description and ``multiple`` indicates whether the text
    used the ``{"result": [ ... ]}`` wrapper.

    Raises ``ValueError`` when no fields could be extracted.
    """
    if text is None:
        raise ValueError("No text to parse.")

    stripped = text.strip()
    if not stripped:
        raise ValueError("Selection is empty.")

    multiple = False
    # Detect the multiple-records wrapper: {"result": [ { ... } ]}
    wrapper = re.search(
        r'"result"\s*:\s*\[\s*\{(?P<body>.*)\}\s*\]',
        stripped,
        re.DOTALL,
    )
    if wrapper:
        multiple = True
        body = wrapper.group('body')
    else:
        first = stripped.find('{')
        last = stripped.rfind('}')
        if first == -1 or last == -1 or last <= first:
            raise ValueError("Selection does not contain a JSON object.")
        body = stripped[first + 1:last]

    fields = []
    # Match "name": value  (value runs until a comma that ends the entry or end of body)
    pattern = re.compile(r'"(?P<name>[^"]+)"\s*:\s*(?P<value>.+?)\s*(?:,\s*)?$', re.MULTILINE)
    for match in pattern.finditer(body):
        name = match.group('name').strip()
        value = match.group('value').strip().rstrip(',').strip()
        if not name or value in ('{', '['):
            continue

        if (value.startswith('"') and value.endswith('"')) and len(value) >= 2:
            ftype = 'string'
            inner = value[1:-1].strip()
        else:
            ftype = 'numeric/logical'
            inner = value.strip()

        # Strip the angle brackets used for placeholders.
        inner = inner.strip()
        if inner.startswith('<') and inner.endswith('>'):
            inner = inner[1:-1].strip()

        fields.append({'name': name, 'type': ftype, 'description': inner})

    if not fields:
        raise ValueError("No fields could be parsed from the selection.")

    return fields, multiple


class JsonWizardDialog(wx.Dialog):
    """Visual editor to build an output JSON specification from a table of
    variable / type / description rows.
    """

    COL_NAME = 0
    COL_TYPE = 1
    COL_DESC = 2
    COL_UP = 3
    COL_DOWN = 4
    COL_DELETE = 5

    def __init__(self, parent, fields=None, multiple=False, title="JSON Output Wizard"):
        super().__init__(parent, title=title,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.result = None
        self.init_ui()

        if fields:
            for field in fields:
                self._append_row(field.get('name', ''),
                                 field.get('type', 'string'),
                                 field.get('description', ''))
        else:
            self._append_row('', 'string', '')

        self.multiple_cb.SetValue(bool(multiple))
        self._update_preview()
        self.SetSize((640, 480))
        self.CentreOnParent()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            panel, label="Define the fields of the output JSON.")
        vbox.Add(info, flag=wx.ALL | wx.EXPAND, border=10)

        # Grid with name / type / description columns plus inline action columns
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 6)
        self.grid.SetColLabelValue(self.COL_NAME, "Variable Name")
        self.grid.SetColLabelValue(self.COL_TYPE, "Type")
        self.grid.SetColLabelValue(self.COL_DESC, "Description")
        self.grid.SetColLabelValue(self.COL_UP, "")
        self.grid.SetColLabelValue(self.COL_DOWN, "")
        self.grid.SetColLabelValue(self.COL_DELETE, "")
        self.grid.SetColSize(self.COL_NAME, 180)
        self.grid.SetColSize(self.COL_TYPE, 110)
        self.grid.SetColSize(self.COL_DESC, 260)
        self.grid.SetColSize(self.COL_UP, 26)
        self.grid.SetColSize(self.COL_DOWN, 26)
        self.grid.SetColSize(self.COL_DELETE, 26)
        self.grid.SetRowLabelSize(30)
        self.grid.DisableDragRowSize()
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self._on_cell_changed)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self._on_cell_left_click)
        vbox.Add(self.grid, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        # Buttons to manage rows
        row_box = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(panel, label="Add Field")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add)
        row_box.Add(add_btn)
        vbox.Add(row_box, flag=wx.ALL, border=10)

        # Multiple records option
        self.multiple_cb = wx.CheckBox(panel, label='Allow multiple records')
        self.multiple_cb.Bind(wx.EVT_CHECKBOX, lambda e: self._update_preview())
        vbox.Add(self.multiple_cb, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Preview
        prev_label = wx.StaticText(panel, label="Preview:")
        vbox.Add(prev_label, flag=wx.LEFT, border=10)
        self.preview = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.preview.SetFont(wx.Font(wx.FontInfo(9).Family(wx.FONTFAMILY_TELETYPE)))
        vbox.Add(self.preview, proportion=1,
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Dialog buttons
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, label="OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        btn_box.Add(ok_btn, flag=wx.RIGHT, border=5)
        btn_box.Add(cancel_btn)
        vbox.Add(btn_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        panel.SetSizer(vbox)

    def _make_type_editor(self):
        editor = wx.grid.GridCellChoiceEditor(TYPES, allowOthers=False)
        return editor

    def _append_row(self, name='', ftype='string', description=''):
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        self.grid.SetCellValue(row, self.COL_NAME, name)
        if ftype not in TYPES:
            ftype = 'string'
        self.grid.SetCellValue(row, self.COL_TYPE, ftype)
        self.grid.SetCellEditor(row, self.COL_TYPE, self._make_type_editor())
        self.grid.SetCellValue(row, self.COL_DESC, description)
        self._setup_action_cells(row)

    def _setup_action_cells(self, row):
        for col, symbol, colour in (
            (self.COL_UP, "\u25b2", wx.Colour(0, 0, 0)),
            (self.COL_DOWN, "\u25bc", wx.Colour(0, 0, 0)),
            (self.COL_DELETE, "\u2715", wx.Colour(180, 0, 0)),
        ):
            self.grid.SetCellValue(row, col, symbol)
            self.grid.SetReadOnly(row, col, True)
            self.grid.SetCellAlignment(row, col, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            self.grid.SetCellTextColour(row, col, colour)

    def _on_add(self, event):
        self._append_row('', 'string', '')
        self._update_preview()

    def _on_cell_left_click(self, event):
        col, row = event.GetCol(), event.GetRow()
        if col == self.COL_DELETE:
            self._delete_row(row)
        elif col == self.COL_UP:
            self._move_row(row, -1)
        elif col == self.COL_DOWN:
            self._move_row(row, 1)
        else:
            event.Skip()

    def _delete_row(self, row):
        if row < 0 or row >= self.grid.GetNumberRows():
            return
        name = self.grid.GetCellValue(row, self.COL_NAME).strip()
        label = f'field "{name}"' if name else "this field"
        if wx.MessageBox(f"Delete {label}?", "Delete Field",
                         wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        self.grid.DeleteRows(row, 1)
        self._update_preview()

    def _move_row(self, row, direction):
        if self.grid.IsCellEditControlEnabled():
            self.grid.SaveEditControlValue()
        target = row + direction
        if row < 0 or target < 0 or target >= self.grid.GetNumberRows():
            return
        for col in (self.COL_NAME, self.COL_TYPE, self.COL_DESC):
            a = self.grid.GetCellValue(row, col)
            b = self.grid.GetCellValue(target, col)
            self.grid.SetCellValue(row, col, b)
            self.grid.SetCellValue(target, col, a)
        self.grid.SetGridCursor(target, self.COL_NAME)
        self._update_preview()

    def _on_cell_changed(self, event):
        self._update_preview()
        event.Skip()

    def _collect_fields(self):
        fields = []
        for row in range(self.grid.GetNumberRows()):
            name = self.grid.GetCellValue(row, self.COL_NAME).strip()
            ftype = self.grid.GetCellValue(row, self.COL_TYPE).strip() or 'string'
            desc = self.grid.GetCellValue(row, self.COL_DESC).strip()
            if not name:
                continue
            fields.append({'name': name, 'type': ftype, 'description': desc})
        return fields

    def _update_preview(self):
        # Commit any in-progress cell edit before reading values.
        if self.grid.IsCellEditControlEnabled():
            self.grid.SaveEditControlValue()
        fields = self._collect_fields()
        self.preview.SetValue(fields_to_json(fields, self.multiple_cb.GetValue()))

    def _on_ok(self, event):
        if self.grid.IsCellEditControlEnabled():
            self.grid.SaveEditControlValue()
        fields = self._collect_fields()
        if not fields:
            wx.MessageBox("Please add at least one field with a name.",
                          "Invalid", wx.OK | wx.ICON_WARNING)
            return
        self.result = fields_to_json(fields, self.multiple_cb.GetValue())
        self.EndModal(wx.ID_OK)

    def GetJson(self):
        return self.result
