# Preferences dialog (wx)
# Options: cache dir, maximum number of allowed combinations, maximum cost per execution (in dollars), timeout per request (in seconds)

import os
import wx
import json
from prompt_blender import info

PREFERENCE_FILE_VERSION = "1.0"
PREFERENCE_FILE = "prompt_blender.config"

class Preferences():
    def __init__(self):
        self._preferences = {
            'app_name': info.APP_NAME,
            'app_version': info.__version__,
            'preference_file_version': PREFERENCE_FILE_VERSION,
            'cache_dir': os.path.join(os.path.expanduser("~"), ".prompt_blender"),
            'max_combinations': 1024,
            'max_rows': 1000,
            'max_cost': 1.50,
            'timeout': 30,
            'recent_files': [],
        }

    def clone(self):
        new_obj =  Preferences()
        new_obj._preferences = self._preferences.copy()

        return new_obj
    
    @staticmethod
    def load_from_file(filename=None):
        print("Loading preferences from file: ", filename)
        preferences = Preferences()

        if filename is None:
            filename = PREFERENCE_FILE
            raise_if_not_found = False
        else:
            raise_if_not_found = True

        if not os.path.exists(filename):
            if raise_if_not_found:
                raise FileNotFoundError(f"Preferences file not found: {filename}")
            else:
                print("Preferences file not found, using default preferences.")
                return preferences
            
        with open(filename, 'r', encoding='utf-8') as f:
            preference_data = json.load(f)

        # Verify version
        preference_file_version = preference_data.get('preference_file_version', None)
        if preference_file_version != PREFERENCE_FILE_VERSION:
            print(f"Warning: Preferences file version is different from the current version ({preference_file_version}!={PREFERENCE_FILE_VERSION}). Using default preferences.")
        else:
            # Sanity check
            if 'cache_dir' not in preference_data or not preference_data['cache_dir']:
                preference_data['cache_dir'] = preferences.cache_dir
            if 'max_combinations' not in preference_data:
                preference_data['max_combinations'] = preferences.max_combinations
            if 'max_cost' not in preference_data:
                preference_data['max_cost'] = preferences.max_cost
            if 'timeout' not in preference_data:
                preference_data['timeout'] = preferences.timeout
            if 'recent_files' not in preference_data:
                preference_data['recent_files'] = preferences.recent_files
            if 'max_rows' not in preference_data:
                preference_data['max_rows'] = preferences.max_rows

            print("Preferences loaded from file: ", filename)
            preferences._preferences = preference_data

        return preferences
    
    def save_to_file(self, filename=None):
        if filename is None:
            filename = PREFERENCE_FILE

        print("Saving preferences to file: ", filename)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self._preferences, f, indent=4)

    @property
    def cache_dir(self):
        return self._preferences['cache_dir']
    
    @cache_dir.setter
    def cache_dir(self, value):
        self._preferences['cache_dir'] = value

    @property
    def max_combinations(self):
        return self._preferences['max_combinations']
    
    @max_combinations.setter
    def max_combinations(self, value):
        self._preferences['max_combinations'] = value

    @property
    def max_cost(self):
        return self._preferences['max_cost']
    
    @max_cost.setter
    def max_cost(self, value):
        self._preferences['max_cost'] = value

    @property
    def timeout(self):
        return self._preferences['timeout']
    
    @timeout.setter
    def timeout(self, value):
        self._preferences['timeout'] = value

    @property
    def recent_files(self):
        return self._preferences['recent_files']

    @property
    def max_rows(self):
        return self._preferences['max_rows']
    
    @max_rows.setter
    def max_rows(self, value):
        self._preferences['max_rows'] = value

    def add_recent_file(self, filename, preference_file=None):
        # Only add if not already present
        if filename in self._preferences['recent_files']:
            return
        self._preferences['recent_files'].append(filename)
        MAX_FILES = 10
        if len(self._preferences['recent_files']) > MAX_FILES:
            self._preferences['recent_files'] = self._preferences['recent_files'][-MAX_FILES:]

        self.save_to_file(preference_file)

    def remove_recent_file(self, filename, preference_file=None):
        self._preferences['recent_files'].remove(filename)
        self.save_to_file(preference_file)

    def __eq__(self, other):
        return self._preferences == other._preferences

