bl_info = {
    "name": 'OptFlowCam',
    "author": "Lisa Piotrowski",
    "co-author": "Noah Apelt",
    "version": (0, 0, 2),
    "blender": (3, 50, 0),
    "location": "View3D > N-Panel > OptFlowCam",
    "description": "An add-on for interpolating smooth camera paths.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Animation",
}

modules = ['utility', 'math', 'interpolation', 'ui', 'properties', 
           'objects', 'operators']
import sys, os
print("version:",sys.version)
from . import register_modules
def register():
    lib_path = os.path.join(os.path.dirname(__file__), "pygeodesic_lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    """
    lib_path = os.path.join(os.path.dirname(__file__), "moviepy")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    """
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.register(full_names)

def unregister():
    full_names = register_modules.get_full_module_names(modules, __name__)
    register_modules.unregister(full_names)

if __name__ == "__main__":
    register()