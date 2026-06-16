import bpy

import traceback

from ..objects.camera import add_camera_object, update_camera, animate_camera
from ..objects.path_geometry import add_path_object, update_path
from ..objects.frustum_geometry import add_frustum_object, animate_frustum

from ..utility import cam_to_sample, lookat_path_from_camera_path
from ..interpolation import interpolate_keyframes


class OFC_OT_InterpolateCamera(bpy.types.Operator):
    # custom ID
    bl_idname = "ofc.interpolate_camera"
    bl_label = "Interpolate Optimal Camera"
    bl_options = {'INTERNAL'}

    temp_collection: bpy.props.StringProperty(
        default='OFC_Temp_AnimatedCameraCollection',
        options={'HIDDEN'}
    )

    cam: bpy.props.StringProperty(
        default='OFC_Temp_AnimatedCamera',
        options={'HIDDEN'}
    )

    cam_path: bpy.props.StringProperty(
        default='OFC_Temp_CameraPath',
        options={'HIDDEN'}
    )

    lookat_path: bpy.props.StringProperty(
        default='OFC_Temp_LookAtPath',
        options={'HIDDEN'}
    )

    _timer = None
    _path = None

    @classmethod
    def poll(cls, context):
        props = context.scene.OFC.init_props

        ## Uncomment for debug purposes if the operator crashed
        ## and cannot be started from UI anymore
        # return True

        if (len(props.keyframes) >= 2 and
                all([k.cam != None for k in props.keyframes]) and
                not context.scene.OFC.op_props.operator_running):
            return True

        return False

    # used to initialize the operator from the context at the moment the operator
    # is called. invoke() is typically used to assign properties which are
    # then used by execute or modal
    def invoke(self, context, event):

        op_props = context.scene.OFC.op_props

        coll = bpy.data.collections.new(self.temp_collection)
        bpy.context.scene.collection.children.link(coll)
        self.temp_collection = coll.name

        # make new camera object
        cam = add_camera_object(self.temp_collection, camera_name=op_props.temp_cam)
        op_props.temp_cam = cam.name

        # make new path object
        add_path_object(2, self.temp_collection, self.cam_path)
        add_path_object(2, self.temp_collection, self.lookat_path)

        # couple modal to window events
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        op_props.operator_running = True

        return {'RUNNING_MODAL'}

    # the "update" method of the operator
    def modal(self, context, event):
        if event.type in {'ESC'}:
            self.quit(context)
            return {'CANCELLED'}

        op_props = context.scene.OFC.op_props
        props = context.scene.OFC.init_props

        keyframes = props.keyframes

        frame_start = keyframes[0].frame
        frame_end = keyframes[-1].frame

        n_frames = (frame_end - frame_start) + 1
        curr_frame = context.scene.frame_current

        min_greedy_point_difference = props.min_greedy_point_difference

        if (not event.type in {'RET', 'SPACE'} or
                (event.type in {'RET', 'SPACE'} and not event.shift)):

            # do not need to recalculate path
            # only update camera according to frame
            if self._path is not None:
                cam_obj = bpy.data.objects[op_props.temp_cam]

                sample = self._path[max(min(len(self._path) - 1, curr_frame - frame_start), 0)]
                update_camera(sample, cam_obj)

            return {"PASS_THROUGH"}

        wm = context.window_manager
        wm.progress_begin(0, 100)

        cam_samples = [cam_to_sample(k.cam) for k in keyframes]
        knots = [k.frame for k in keyframes]

        wm.progress_update(20)

        if "geodesic" in props.metric and props.method != 'Linear' and not props.is_earth:
            self.report({'ERROR_INVALID_INPUT'}, "No extrapolation of general geodesics implemented.")
            self.quit(context)
            return {'CANCELLED'}

        earth_radius = None
        if props.is_earth or props.metric == "3DImageFlowGeodesicEarthRot":
            # later change
            earth_radius = 100

        print("begin")

        # calculate path
        try:
            self._path = interpolate_keyframes(cam_samples, knots, cam_samples[0]["focal"],
                                               props.metric, props.method, n_frames,
                                               rho=props.rho,
                                               min_greedy_point_difference=min_greedy_point_difference,
                                               is_earth=props.is_earth, earth_radius=earth_radius, weight=props.weight)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.report({'ERROR_INVALID_INPUT'}, "Could not compute path")
            self.quit(context)
            return {'CANCELLED'}

        wm.progress_update(80)

        # update paths
        cam_path_obj = bpy.data.objects[self.cam_path]
        update_path(cam_path_obj, self._path)

        # safe view,up,right in a file
        # for each save x,y,z-coordinate -> plot each of them individually


        look_path = lookat_path_from_camera_path(self._path)
        lookat_path_obj = bpy.data.objects[self.lookat_path]
        update_path(lookat_path_obj, look_path)

        # update new camera
        cam_obj = bpy.data.objects[op_props.temp_cam]

        if curr_frame < frame_start:
            update_camera(cam_samples[0], cam_obj)
        elif curr_frame > frame_end:
            update_camera(cam_samples[-1], cam_obj)
        else:
            if 0 <= curr_frame - frame_start < len(self._path):
                sample = self._path[curr_frame - frame_start]
                update_camera(sample, cam_obj)
            else:
                print(f"{curr_frame - frame_start} is invalid idx for path with len = {len(self._path)}")

        wm.progress_end()

        # want to make the camera permanent
        if event.type in {'RET'}:
            coll = bpy.data.collections.new("OptimizedCamera")
            bpy.context.scene.collection.children.link(coll)

            new_cam = add_camera_object(coll.name, camera_name="OptFlowCam")
            animate_camera(self._path, new_cam, start_frame=frame_start)
            if props.make_frustum_permanent:
                new_frustum = add_frustum_object(coll.name, object_name="OptFlowFrustum")
                animate_frustum(self._path, new_frustum, start_frame=frame_start)

            if props.make_path_permanent:
                # path already exists, just need to move it to new collection
                for obj, name in zip((cam_path_obj, lookat_path_obj), ("CameraPath", "LookAtPath")):
                    for c in obj.users_collection:
                        c.objects.unlink(obj)

                    obj.name = name
                    coll.objects.link(obj)

                bpy.context.view_layer.update()
            self.quit(context)
            return {'FINISHED'}

        # modal will be run the next time an UI event is triggered
        return {'RUNNING_MODAL'}

    def quit(self, context):
        coll = bpy.data.collections[self.temp_collection]

        for obj in coll.objects:
            print(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

        bpy.data.collections.remove(coll)

        context.scene.OFC.op_props.operator_running = False
        context.scene.OFC.op_props.property_unset("temp_cam")


# ------------------------------------------------------------------------------

classes = [OFC_OT_InterpolateCamera]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
