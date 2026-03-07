import importlib.util
import os
import traceback

from colorama import Fore, Style

def load_modules_generic(paths, module_type, validation_func, info_attribute, exclude_file):
    """
    Generic module loader with colored output.

    Args:
        paths: List of paths to search for modules
        module_type: String describing the type of modules (e.g., "LLM", "analysis")
        validation_func: Function that takes (module, module_name) and returns the value to store, or raises ValueError on validation failure
        info_attribute: String name of the attribute on module that contains info dict with 'name' and 'description'
        exclude_file: File path to exclude from loading (usually __file__)

    Returns:
        Dictionary of loaded modules
    """
    if paths is None:
        paths = []

    # Read all modules in the directories
    paths = [path for path in paths if os.path.exists(path)]
    paths.append(os.path.dirname(exclude_file))
    candidate_modules = [os.path.join(path, file) for path in paths for file in os.listdir(path) if file.endswith('.py') and file not in ['__init__.py']]
    candidate_modules.remove(exclude_file)

    print(f'Loading {module_type} modules/plugins:')

    # list all modules loaded. Load it dynamically
    modules = {}
    for module_file in candidate_modules:
        module_name = os.path.basename(module_file).split('.')[0]
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            print(f'{Fore.RED}[ FAIL ]{Style.RESET_ALL} {module_name:20s} - Error loading module: {e}')
            # dump stack trace if it's not an ImportError
            if not isinstance(e, ImportError):
                traceback.print_exc()
            continue


        try:
            value = validation_func(module)
        except ValueError as e:
            print(f'{Fore.YELLOW}[ SKIP ]{Style.RESET_ALL} {module_name:20s} - {e}')
            continue

        if not hasattr(module, info_attribute):
            print(f'{Fore.YELLOW}[ SKIP ]{Style.RESET_ALL} {module_name:20s} - Missing module attribute {info_attribute}')
            continue

        # Get info for display
        info = getattr(module, info_attribute, {})
        name = info.get('name', module_name)
        description = info.get('description', 'No description available')

        print(f'{Fore.GREEN}[  OK  ]{Style.RESET_ALL} {name:20s} - {description}')
        modules[name] = value

    return modules