import bpy
from mathutils import Vector
import traceback

from ..objects.camera import add_camera_object, animate_camera
from ..objects.path_geometry import add_path_object, update_path
from ..objects.render import render_scene#, combineClips


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
        length = (Vector(bounding_box[i]) - Vector(bounding_box[(i + 2) % len(bounding_box)])).length
        if not min_length or length < min_length:
            min_length = length
    return min_length


def create_cam_2(vertex, matrix, focal, scale_base, min_scale, max_scale):
    dist = scale_base * ((max_scale - min_scale) * random() + min_scale)
    direction = -vertex.normal
    look_at_position = matrix @ vertex.co
    position = look_at_position - direction * dist * focal
    return create_cam(position, direction, (0, direction[2], -direction[1]), dist, focal)


def create_cams(object_mesh, matrix, min_scale, max_scale):
    vertices = object_mesh.data.vertices
    start_idx = randint(0, len(vertices) - 1)
    while (end_idx := randint(0, len(vertices) - 1)) == start_idx:
        pass

    start_vert = vertices[start_idx]
    end_vert = vertices[end_idx]

    # Faktor im Verhältnis der Diagonale der BB (z.B. 1-3)
    scale_base = get_shortest_bb_diagonal(object_mesh.bound_box) / 2
    focal = 1.3888888888888888
    start_cam = create_cam_2(start_vert, matrix, focal, scale_base, min_scale, max_scale)
    end_cam = create_cam_2(end_vert, matrix, focal, scale_base, min_scale, max_scale)

    return start_cam, end_cam


def is_triangle_mesh(mesh):
    if len(mesh.polygons) == 0:
        return False
    min_face_count, max_face_count = 4, 2
    for face in mesh.polygons:
        n_vertices = len(face.vertices)
        if n_vertices < min_face_count:
            min_face_count = n_vertices
        if n_vertices > max_face_count:
            max_face_count = n_vertices
    return max_face_count == 3 and min_face_count == max_face_count


class OFC_OT_CompareInterpolateCamera(bpy.types.Operator):
    # custom ID
    bl_idname = "ofc.compare_interpolate_camera"
    bl_label = "Compare Interpolate Optimal Camera"
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
        # couple modal to window events
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # the "update" method of the operator
    def modal(self, context, event):
        return self.generate_random_cam(context, event)



    def generate_random_cam(self, context, event):
        wm = context.window_manager
        wm.progress_begin(0, 100)
        metrics = ["3DImageFlow", "TransformationsLinear", "3DImageFlowGeodesic"]
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
        move_around_object = props.selected_object
        render_animation = props.render_animation
        generate_earth_file = props.generate_earth_file
        exporting_path = props.export_dir
        min_scale = props.min_scale
        max_scale = props.max_scale
        if min_scale > max_scale:
            self.report({'ERROR_INVALID_INPUT'}, "min_scale must be smaller than max_scale")
            return {'CANCELLED'}

        context = bpy.context
        vl = context.view_layer

        # add cams to scene
        if move_around_object.type != 'MESH':
            self.report({'ERROR_INVALID_INPUT'}, "Selected object must be a triangle mesh")
            return {'CANCELLED'}

        mesh = move_around_object.evaluated_get(vl.depsgraph).to_mesh()
        if not is_triangle_mesh(mesh):
            self.report({'ERROR_INVALID_INPUT'}, "Selected object be a triangle mesh")
            return {'CANCELLED'}

        mat = move_around_object.matrix_world
        start_cam, end_cam = create_cams(move_around_object, mat, min_scale, max_scale)

        n_frames = props.n_frames
        knots = [0, n_frames - 1]
        cam_samples = [start_cam, end_cam]
        filenames = []

        wm.progress_update(3)

        for i, metric in enumerate(metrics):
            print(metric)
            try:
                self._path = interpolate_keyframes(cam_samples, knots, cam_samples[0]["focal"],
                                                   metric, props.method, n_frames,
                                                   rho=props.rho, generate_earth_file=generate_earth_file,
                                                   collection_name=random_coll_name)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.report({'ERROR_INVALID_INPUT'}, "Could not compute path")

                return {'CANCELLED'}

            cam_path_obj = paths[i]
            update_path(cam_path_obj, self._path)

            animate_camera(self._path, cams[i])

            if render_animation:
                filenames.append(f"{exporting_path}\\{metric}.mp4")
                render_scene(cams[i], filenames[-1] , end_frame=n_frames)
            wm.progress_update(3+90/len(metrics)*(i+1))

        """
        if len(filenames)>1:
            combineClips(exporting_path, filenames)
        """

        wm.progress_end()
        return {'FINISHED'}


# ------------------------------------------------------------------------------

classes = [OFC_OT_CompareInterpolateCamera]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
