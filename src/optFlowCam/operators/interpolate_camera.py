import bpy
from mathutils import Vector
import traceback

from ..objects.camera import add_camera_object, update_camera, animate_camera
from ..objects.path_geometry import add_path_object, update_path
from ..objects.frustum_geometry import add_frustum_object, animate_frustum
from ..objects.render import render_scene

from ..utility import cam_to_sample, lookat_path_from_camera_path
from ..interpolation import interpolate_keyframes
from random import randint, random

def create_cam(position, view, up, scale, focal):
    return {
        "position": [i for i in position],
        "view": [i for i in view],
        "up": [i for i in up],
        "frustum_scale": scale,
        "focal": focal
    }

def get_shortest_bb_diagonal(bounding_box):
    min_length = None
    for i in range(2, len(bounding_box)):
        length = (Vector(bounding_box[i])-Vector(bounding_box[(i+2)%len(bounding_box)])).length
        print(length)
        if not min_length or length < min_length:
            min_length = length
    return min_length

def create_cams(object_mesh, matrix, min_scale, max_scale):
    # pos = matrix@vertex.co + vertex.normal * (8 + random() * 4)
    # copy from params-fucntion: pos = lookat - scale * focal * view
    vertices = object_mesh.data.vertices
    start_idx = randint(0, len(vertices) - 1)
    while (end_idx := randint(0, len(vertices) - 1)) == start_idx:
        pass

    start_vert = vertices[start_idx]
    end_vert = vertices[end_idx]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, enter_editmode=False, align='WORLD', location=matrix @ start_vert.co,scale=(.1, .1, .1))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, enter_editmode=False, align='WORLD', location=matrix @ end_vert.co,scale=(.1, .1, .1))

    scale_base = get_shortest_bb_diagonal(object_mesh.bound_box)/2
    start_dist = scale_base * ((max_scale - min_scale)*random()+min_scale)
    end_dist = scale_base * ((max_scale - min_scale)*random()+min_scale)
    focal = 1.3888888888888888
    start_cam = create_cam(matrix@start_vert.co - start_dist * focal * -start_vert.normal,-start_vert.normal, (-start_vert.normal[1], -start_vert.normal[0], 0) ,scale_base, focal)
    end_cam = create_cam(matrix@end_vert.co - end_dist * focal * -end_vert.normal,-end_vert.normal, (-end_vert.normal[1], -end_vert.normal[0], 0) ,scale_base, focal)
    return start_cam,end_cam
    # TODO: scale-factor variable
    # Faktor im Verhältnis der Diagonale der BB (z.B. 1-3)
    # BB berechnen: https://blender.stackexchange.com/questions/223858/how-do-i-get-the-bounding-box-of-all-objects-in-a-scene
    # pos = matrix@vertex.co - 1 * focal * view
    # up = (-view[1], view[0], 0)
    """
    cam = {
        "position": [i for i in pos],
        "view": [i for i in view],
        "up": [i for i in up],
        "frustum_scale": 1,
        "focal": focal
    }
    return cam
    """

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
        return True

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
        return self.generate_random_cam(context, event)
    """
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

        # calculate path
        try:
            self._path = interpolate_keyframes(cam_samples, knots, cam_samples[0]["focal"],
                                               props.metric, props.method, n_frames,
                                               rho=props.rho)
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
            sample = self._path[curr_frame - frame_start]
            update_camera(sample, cam_obj)

        wm.progress_end()

        # want to make the camera permanent
        if event.type in {'RET'}:
            coll = bpy.data.collections.new("OptimizedCamera")
            bpy.context.scene.collection.children.link(coll)

            new_cam = add_camera_object(coll.name, camera_name="OptFlowCam")
            animate_camera(self._path, new_cam, start_frame=frame_start)
            render_scene(new_cam, f"C:\\Users\\nonoa\\Desktop\\renderings\\{new_cam.name}.mp4", start_frame=frame_start, end_frame=frame_end)
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
        """

    def quit(self, context):
        coll = bpy.data.collections[self.temp_collection]

        for obj in coll.objects:
            print(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

        bpy.data.collections.remove(coll)

        context.scene.OFC.op_props.operator_running = False
        context.scene.OFC.op_props.property_unset("temp_cam")

    def generate_random_cam(self, context, event):
        metrics = ["3DImageFlow", "TransformationsLinear", "3DImageFlow2"]
        # Preparation
        coll = bpy.data.collections.new(f"random_cams")
        bpy.context.scene.collection.children.link(coll)
        random_coll_name = coll.name

        # create cams with paths
        cams = []
        paths = []
        for metric in metrics:
            cam = add_camera_object(random_coll_name, camera_name=f"random_cam_{metric}")
            # random_cam_name = cam.name
            cams.append(cam)
            random_cam_path = f"random_path_{metric}"
            path = add_path_object(2, random_coll_name, random_cam_path)
            paths.append(path)


        # op_props = context.scene.OFC.op_props
        props = context.scene.OFC.init_props

        # read properties
        move_around_object = bpy.context.selected_objects[0]  ### TODO: props.object
        generate_earth_file = props.generate_earth_file #True ### TODO: props.google_earth_file
        exporting_path = props.export_dir
        min_scale = props.min_scale
        max_scale = props.max_scale
        if min_scale > max_scale:
            self.report({'ERROR_INVALID_INPUT'}, "min_scale must be smaller than max_scale")
            self.quit(context)
            return {'CANCELLED'}

        context = bpy.context
        vl = context.view_layer

        # add cams to scene
        mesh = move_around_object.evaluated_get(vl.depsgraph).to_mesh()

        assert len(mesh.polygons) > 0 and len(mesh.polygons[0].vertices) == 3, "Must be a triangle mesh"

        mat = move_around_object.matrix_world
        start_cam,end_cam = create_cams(move_around_object, mat, min_scale, max_scale)

        n_frames = props.n_frames
        knots = [0, n_frames - 1]
        cam_samples = [start_cam, end_cam]

        for i, metric in enumerate(metrics):
            print(metric)
            # interpolate between cams
            try:
                self._path = interpolate_keyframes(cam_samples, knots, cam_samples[0]["focal"],
                                                   metric, props.method, n_frames,
                                                   rho=props.rho, generate_earth_file=generate_earth_file, collection_name=random_coll_name)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.report({'ERROR_INVALID_INPUT'}, "Could not compute path")
                self.quit(context)
                return {'CANCELLED'}

            # update paths
            cam_path_obj = paths[i] # bpy.data.objects[self.cam_path]
            update_path(cam_path_obj, self._path)

            # animate cam
            animate_camera(self._path, cams[i])
            """
            # get animated cam
            coll = bpy.data.collections.new("OptimizedCamera")
            bpy.context.scene.collection.children.link(coll)

            new_cam = add_camera_object(coll.name, camera_name="OptFlowCam_"+metric)
            animate_camera(self._path, new_cam, start_frame=frame_start)
            """

            # generate video + export video
            if not generate_earth_file:
                render_scene(cams[i], f"{exporting_path}\\{metric}.mp4", end_frame=n_frames)

        self.quit(context)
        return {'FINISHED'}

    """
        cams = calculate_cams(methods, interpolation_methods)
        for Cam in cams:
            scene.render(Cam)

        def calculate_cams(methods, interpolation_methods):
            for i, elem in enumerate(Interpolation_methods):
                positions = calculate_cam_position(methods[i])
                if google_earth:
                    save_as_eartfile(positions)
        """

    """
    def make_auto_animation():
    # input = mesh
    mesh = bpy.data.meshes[0]
    vert_count = len(mesh.vertices)
    start_vert = mesh.vertices[randint(0, vert_count)]
    while (end_vert := mesh.vertices[randint(0, vert_count)]) != start_vert:
        pass

    start_cam_pos = start_vert.co + randint(2, 5) * start_vert.normal
    end_cam_pos = end_vert.co + randint(2, 5) * end_vert.normal

    cam1 = {
        "position": start_cam_pos.tolist(),
        "view": -start_vert.normal,
        "up": (0, 0, 1),  # ??? up.tolist(),
        "frustum_scale": 1,
        "focal": 1  # ????
    }
    cam2 = {
        "position": end_cam_pos.tolist(),
        "view": -end_vert.normal,
        "up": (0, 0, 1),  # ??? up.tolist(),
        "frustum_scale": 1,  # ???
        "focal": 1  # ????
    }

    # add cams to scene
    # interpolate between cams
    # get keyframe_cam
    # generate video
    # export video
    # repeat for different methods
    """


# ------------------------------------------------------------------------------

classes = [OFC_OT_InterpolateCamera]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
