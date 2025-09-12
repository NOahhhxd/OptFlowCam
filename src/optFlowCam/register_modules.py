import sys
import importlib
import traceback

def get_full_module_names(modules, name):
    modules_full_names = {}
    for module in modules:
        if 'DEBUG_MODE' in sys.argv:
            modules_full_names[module] = ('{}'.format(module))
        else:
            modules_full_names[module] = ('{}.{}'.format(name, module))

    traceback.print_stack()
    print(modules_full_names)

    for module in modules_full_names.values():
        if module in sys.modules:
            importlib.reload(sys.modules[module])
        else:
            globals()[module] = importlib.import_module(module)
            setattr(globals()[module], 'all_modules', modules_full_names)

    return modules_full_names

def register(modules):
    for module in modules.values():
        print(sys.modules[module])
        if module in sys.modules:
            if hasattr(sys.modules[module], 'register'):
                sys.modules[module].register()

def unregister(modules):
    for module in modules.values():
        if module in sys.modules:
            if hasattr(sys.modules[module], 'unregister'):
                sys.modules[module].unregister()