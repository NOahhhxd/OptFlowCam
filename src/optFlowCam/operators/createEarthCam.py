import bpy

from ..objects.GoogleEarthFile import camMatrixByPosition
from ..objects.camera import add_camera_object


class OFC_OT_CreateEarthCam(bpy.types.Operator):
    # custom ID
    bl_idname = "ofc.create_earth_cam"
    bl_label = "Create a cam by Google Earth Data"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        earth_cam_props = context.scene.OFC.earth_cam_props
        cam_obj = add_camera_object(bpy.context.scene.collection.name, "GoogleEarthCam")
        earth = bpy.context.selected_objects[0]
        earth_radius = (earth.matrix_world @ (earth.data.vertices[0].co - earth.location)).length
        matrix = camMatrixByPosition(earth_cam_props.latitude, earth_cam_props.longitude, earth_cam_props.altitude,
                                     earth_cam_props.rotX, earth_cam_props.rotY, earth_cam_props.rotZ, earth_radius)
        cam_obj.matrix_world = matrix
        # for a fov of 20° like in Google Earth Studio
        cam_obj.data.lens = 102.08307647705078
        return {'FINISHED'}


# ------------------------------------------------------------------------------

classes = [OFC_OT_CreateEarthCam]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
