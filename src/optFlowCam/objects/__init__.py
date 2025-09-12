modules = ['camera', 'frustum_geometry', 'path_geometry', 'look_at_camera', 'render', 'GoogleEarthFile']

from .. import register_modules

def register():
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.register(full_names)

def unregister():
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.unregister(full_names)

if __name__ == "__main__":
    register()