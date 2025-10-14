modules = ['insert_keyframe', 'interpolate_camera', 'redistribute_frames',
           'reset_property', 'compare_cams', 'createEarthCam']

from .. import register_modules


def register():
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.register(full_names)


def unregister():
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.unregister(full_names)


if __name__ == "__main__":
    register()
