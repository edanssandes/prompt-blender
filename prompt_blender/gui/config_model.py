class ConfigModel:
    def __init__(self, name="", module_id="", module_name="", module_args=None):
        self.name = name
        self.module_id = module_id
        self.module_name = module_name
        self.module_args = module_args if module_args is not None else {}
        self._enabled = True

    def to_dict(self):
        return {
            #'name': self.name,
            'module_id': self.module_id,
            'module_name': self.module_name,
            'module_args': self.module_args
        }

    @staticmethod
    def from_dict(name, data):
        return ConfigModel(
            name=name,
            module_id=data.get('module_id', ""),
            module_name=data.get('module_name', ""),
            module_args=data.get('module_args', {})
        )

    @property
    def enabled(self):
        return self._enabled
    
    @enabled.setter
    def enabled(self, value):
        self._enabled = value

    def is_valid(self, available_modules):
        return self.module_id in available_modules
    