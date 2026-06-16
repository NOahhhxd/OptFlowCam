import bpy
from mathutils import Vector
import traceback

from .. import utility
from ..objects import GoogleEarthFile
from ..objects.camera import add_camera_object, animate_camera, update_camera
from ..objects.path_geometry import add_path_object, update_path
from ..objects.render import render_scene, render_single_image, combine_clips  # , combineClips

from ..interpolation import interpolate_keyframes, export_geoposition_data
from random import randint, random, shuffle
import bmesh
from math import pi, sin, cos, radians

from ..utility import cam_to_sample


class OFC_OT_GenerateEarthFileFromCamera(bpy.types.Operator):
    """
    Operator to compare different metrics for interpolating cameras.
    """
    # custom ID
    bl_idname = "ofc.earthfile_from_cam"
    bl_label = "Generate earth-file from camera"
    bl_options = {'INTERNAL'}

    _timer = None
    _path = None

    @classmethod
    def poll(cls, context):
        return True

    # used to initialize the operator from the context at the moment the operator
    # is called. invoke() is typically used to assign properties which are
    # then used by execute or modal
    def invoke(self, context, event):
        # couple modal to window events
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # the "update" method of the operator
    def modal(self, context, event):
        wm = context.window_manager
        props = context.scene.OFC.convert_cam_props # vlt anpassen
        scene = context.scene
        cam = props.cam
        cams = []
        for i in range(0,props.num_frames+1):
            scene.frame_set(i)
            cams.append(cam_to_sample(cam))

        export_geoposition_data(cams, len(cams), props.name, props.file_path, earth_center=Vector((0,0,0)),
                                    earth_radius=100)
        wm.progress_end()
        return {'FINISHED'}


classes = [OFC_OT_GenerateEarthFileFromCamera]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
