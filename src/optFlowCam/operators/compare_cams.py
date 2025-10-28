import bpy
from mathutils import Vector
import traceback

from ..objects.camera import add_camera_object, animate_camera, update_camera
from ..objects.path_geometry import add_path_object, update_path
from ..objects.render import render_scene, render_single_image, combine_clips  # , combineClips

from ..interpolation import interpolate_keyframes
from random import randint, random, shuffle
import bmesh
from math import pi, sin, cos, radians

from ..utility import cam_to_sample


def create_convex_hull_object(obj, collection_name):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ch = bmesh.ops.convex_hull(bm, input=bm.verts)
    # len(obj.data.polygons) + len(obj.data.vertices) + len(obj.data.edges)
    # types = list(set([type(i) for i in ch["geom"]]))
    # [list(filter(lambda x: type(x)==i, ch["geom"])) for i in types]
    vertices = []
    faces = []
    edges = []
    for elem in ch["geom"]:
        typestring = str(type(elem))
        if typestring.find("BMVert") > -1:
            vertices.append(elem)
        elif typestring.find("BMFace") > -1:
            faces.append(elem)
        elif typestring.find("BMEdge") > -1:
            edges.append(elem)
    idx_map = {elem.index: i for i, elem in enumerate(vertices)}
    coords = [obj.matrix_world @ vert.co for vert in vertices]
    faces_mesh = [[idx_map[i.index] for i in face.verts] for face in faces]
    edges_mesh = [[idx_map[i.index] for i in edge.verts] for edge in edges]
    # https://b3d.interplanety.org/en/how-to-create-mesh-through-the-blender-python-api/
    new_mesh = bpy.data.meshes.new('convex_hull')
    new_mesh.from_pydata(coords, edges_mesh, faces_mesh)
    new_mesh.update()
    # make object from mesh
    new_object = bpy.data.objects.new('convex_hull', new_mesh)
    # add object to scene collection
    bpy.data.collections[collection_name].objects.link(new_object)
    return new_object


def create_cam(position, view, up, scale, focal):
    return {
        "position": [i for i in position],
        "view": [i for i in view],
        "up": [i for i in up],
        "frustum_scale": scale,
        "focal": focal
    }


def get_shortest_bb_diagonal(bounding_box, matrix):
    min_length = None
    for i in range(2, len(bounding_box)):
        length = (matrix @ Vector(bounding_box[i]) - matrix @ Vector(bounding_box[(i + 2) % len(bounding_box)])).length
        if not min_length or length < min_length:
            min_length = length
    return min_length


def create_cam_2(vertex, matrix, focal, scale_base, min_scale, max_scale):
    dist = scale_base * ((max_scale - min_scale) * random() + min_scale)
    direction = -vertex.normal
    look_at_position = matrix @ vertex.co
    position = look_at_position - direction * dist * focal
    if direction[1] < 0:
        return create_cam(position, direction, (0, direction[2], -direction[1]), dist, focal)
    else:
        return create_cam(position, direction, (0, -direction[2], direction[1]), dist, focal)


def create_cam_from_face(face, matrix, focal, scale_base, min_scale, max_scale, vertices, other_face):
    """
    u = random()
    v = random() * (1 - u)
    z = 1 - u - v
    """
    u, v, w = Vector(random(), random(), random()).normalized()

    other_coords = [matrix @ vertices[idx].co for idx in other_face.vertices]
    vert_coords = [vertices[idx].co for idx in face.vertices]

    look_at_position = w * other_coords[0] + v * other_coords[1] + u * other_coords[2]

    dist = scale_base * ((max_scale - min_scale) * random() + min_scale)
    position = matrix @ (vert_coords[0] + dist * focal * face.normal)
    direction = look_at_position - position
    direction_n = direction.normalized()
    scale = direction.length / focal
    if direction[1] < 0:
        return create_cam(position, direction_n, Vector([0, direction_n[2], -direction_n[1]]).normalized(), scale,
                          focal)
    else:
        return create_cam(position, direction_n, Vector([0, -direction_n[2], direction_n[1]]).normalized(), scale,
                          focal)


def add_material(objects, color, transparent=False):
    mat = bpy.data.materials.new(name="TransparentMaterial")
    if transparent:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        for n in nodes:
            nodes.remove(n)

        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Alpha"].default_value = color[3]
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (200, 0)

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    else:
        mat.diffuse_color = color

    for obj in objects:
        obj.data.materials.append(mat)
    return mat


def random_pos_squared2(vertex_co, vertex_normal, matrix, r):
    x = random()
    theta = (x ** 2 + x ** (1 / 2)) / 2 * radians(80)
    phi = random() * 2 * pi
    x = r * sin(theta) * cos(phi)
    y = r * sin(theta) * sin(phi)
    z = cos(theta)
    rotation_vec = Vector([x, y, z])
    rotation_vec.rotate(Vector([0, 0, 1]).rotation_difference(matrix @ vertex_normal))
    cam_pos = matrix @ vertex_co + rotation_vec
    return cam_pos, -rotation_vec

def get_up(view):
    return view.cross([0, 0, 1]).cross(view)

def create_cams(object_mesh, matrix, min_scale, max_scale, is_earth_cam=False):
    scale_base = get_shortest_bb_diagonal(object_mesh.bound_box, object_mesh.matrix_world) / 2
    if is_earth_cam:
        # 20° FOV = Google Earth standard-FOV => = 102.083 mm focal length / 36.0 mm sensor width
        focal = 2.8356410132514105
    else:
        # 39.6° = standard FOV => 50.0 mm focal length / 36.0 mm sensor width
        focal = 1.3888888888888888
    vertices = object_mesh.data.vertices
    faces = object_mesh.data.polygons
    face_idx = list(range(len(faces)))
    shuffle(face_idx)
    # shuffle(face_idx)
    cams = []
    for i in range(2):
        face = faces[face_idx[i]]
        face_vertices = [vertices[idx] for idx in face.vertices]
        vec = Vector((random(), random(), random()))
        u, v, w = vec / sum(vec)
        lookat_pos = u * face_vertices[0].co + v * face_vertices[1].co + w * face_vertices[2].co
        lookat_normal = u * face_vertices[0].normal + v * face_vertices[1].normal + w * face_vertices[2].normal
        dist = scale_base * ((max_scale - min_scale) * random() + min_scale)
        pos, view = random_pos_squared2(lookat_pos, lookat_normal, matrix, dist)
        view_n = view.normalized()
        scale = view.length / focal
        if view_n[1] < 0:
            cams.append(create_cam(pos, view_n, Vector([0, view_n[2], -view_n[1]]).normalized(), scale, focal))
        else:
            cams.append(create_cam(pos, view_n, Vector([0, -view_n[2], view_n[1]]).normalized(), scale, focal))
    return cams
    # start_idx = vertices_idx[0]
    """
    start_idx = randint(0, len(faces) - 1)  # randint(0, len(vertices) - 1)

    while (end_idx := randint(0, len(faces) - 1)) == start_idx:
        # while (end_idx := randint(0, len(vertices) - 1)) == start_idx:
        pass

    # end_idx = vertices_idx[-1]
    start_face = faces[start_idx]  # start_vert = vertices[start_idx]
    end_face = faces[end_idx]  # end_vert = vertices[end_idx]
    """

    start_face = faces[face_idx[0]]
    i = 1
    while start_face.normal.angle(faces[face_idx[i]].normal) > pi / 4:
        i += 1
    start_cam = create_cam_from_face(start_face, matrix, focal, scale_base, min_scale, max_scale, vertices,
                                     faces[face_idx[i]])
    end_face = faces[face_idx[-1]]
    i = -2
    while end_face.normal.angle(faces[face_idx[i]].normal) > pi / 4:
        i -= 1
    end_cam = create_cam_from_face(end_face, matrix, focal, scale_base, min_scale, max_scale, vertices,
                                   faces[face_idx[i]])

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


def get_look_at_points(cams):
    # pos = lookat - scale * focal * view => looakt = pos + scale*focal*view
    context = bpy.context
    vl = context.view_layer
    scene = context.scene
    # hit, loc, norm_0, face_idx, obj_0, mw_0 = scene.ray_cast(vl.depsgraph, start, direction)
    return [scene.ray_cast(vl.depsgraph, Vector(cam["position"]), Vector(cam["view"]))[1] for cam in cams]
    # return [Vector(cam["position"]) + cam["frustum_scale"] * cam["focal"] * Vector(cam["view"]) for cam in cams]


def create_spheres_at(positions, collection_name):
    spheres = []
    for position in positions:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.2, enter_editmode=False, align='WORLD', location=position,
                                             scale=(1, 1, 1))
        sphere_obj = bpy.context.active_object
        spheres.append(sphere_obj)
        if collection_name == bpy.context.scene.collection.name:
            bpy.context.scene.collection.objects.link(sphere_obj)
        else:
            bpy.data.collections[collection_name].objects.link(sphere_obj)
    return spheres


def middleOfBB(obj):
    bb = [obj.matrix_world @ Vector(i) for i in obj.bound_box]
    middle = Vector([0, 0, 0])
    for elem in bb:
        middle += elem
    return middle / len(bb)


def create_outside_cam(start_pos, end_pos, obj, collection_name):
    middle = start_pos + (end_pos - start_pos) / 2
    obj_mid = middleOfBB(obj)
    obj_mid_to_middle = middle - obj_mid
    middle_normal = Vector([obj_mid_to_middle[0], obj_mid_to_middle[1], 0]).normalized()
    """
    middle_normal = (end_pos - start_pos).normalized()
    middle_normal = Vector([middle_normal[1], -middle_normal[0], 0]).normalized()

    # if normal goes into object if dist to mid point > 0 (then inverse direction)
    
    if (obj_mid - middle) @ middle_normal > 0:
        middle_normal *= -1
    """
    dist = get_shortest_bb_diagonal(obj.bound_box, obj.matrix_world)
    cam_position = middle + 2.5 * dist * middle_normal
    # Ausrichtung auf Mitte des Objekts
    cam_position[2] = obj_mid[2]
    cam_direction = (obj_mid - cam_position).normalized()
    # cam_direction = (middle - cam_position).normalized()
    """
    if cam_direction[1] < 0:
        up_vec = Vector([0,cam_direction[2], -cam_direction[1]]).normalized()
    else:
        up_vec = Vector([0, -cam_direction[2], cam_direction[1]]).normalized()
    """
    # solange es auf den Mittelpunkt auf gleich Höhe gerichtet ist, kann up-Vector einfach nach oben gerichtet sein
    up_vec = Vector([0, 0, 1])
    cam = create_cam(cam_position, cam_direction, up_vec, 1, 1.3888888888888888)
    cam_obj = add_camera_object(collection_name, "singleShot")
    update_camera(cam, cam_obj)
    return cam_obj


class OFC_OT_CompareInterpolateCamera(bpy.types.Operator):
    """
    Operator to compare different metrics for interpolating cameras.
    """
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
        metrics = ["3DImageFlowGeodesic", "3DImageFlowGeodesicGreedy", "3DImageFlow", "TransformationsLinear"]

        # op_props = context.scene.OFC.op_props
        props = context.scene.OFC.init_props

        # read properties
        move_around_object = props.selected_object
        render_animation = props.render_animation
        generate_earth_file = props.generate_earth_file
        exporting_path = props.export_dir
        min_scale = props.min_scale
        max_scale = props.max_scale
        random_cams = props.random_cams
        min_greedy_point_difference = props.min_greedy_point_difference
        if min_scale > max_scale:
            self.report({'ERROR_INVALID_INPUT'}, "min_scale must be smaller than max_scale")
            return {'CANCELLED'}

        # Preparation
        coll = bpy.data.collections.new(f"compare_cams")
        bpy.context.scene.collection.children.link(coll)
        random_coll_name = coll.name

        # create cams with paths
        cams = []
        geodesic_paths = [add_path_object(2, random_coll_name, "geodesic_path"),
                          add_path_object(2, random_coll_name, "modified_geodesic_path")]
        paths = []
        for metric in metrics:
            cam = add_camera_object(random_coll_name, camera_name=f"compare_cam_{metric}")
            if generate_earth_file:
                # FOV = 20°
                cam.data.lens = 102.083 # focal length in mm
            cams.append(cam)
            random_cam_path = f"compare_path_{metric}"
            path = add_path_object(2, random_coll_name, random_cam_path)
            paths.append(path)

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
        """ convex hull part no longer needed
        move_around_object.hide_set(True)
        convex_hull_obj = create_convex_hull_object(move_around_object, random_coll_name)
        convex_hull_obj.hide_render = True
        start_cam, end_cam = create_cams(convex_hull_obj, convex_hull_obj.matrix_world, min_scale, max_scale)
        """
        start_cam, end_cam = None, None
        n_frames = 100
        knots = None

        if random_cams:
            start_cam, end_cam = create_cams(move_around_object, move_around_object.matrix_world, min_scale, max_scale, is_earth_cam=generate_earth_file)
            n_frames = props.n_frames
            knots = [0, n_frames - 1]
        else:
            keyframes = props.keyframes
            if len(keyframes) != 2:
                self.report({'ERROR_INVALID_INPUT'}, "Only 2 keyframes possible for comparison!")
                return {'CANCELLED'}

            frame_start = keyframes[0].frame
            frame_end = keyframes[-1].frame

            n_frames = (frame_end - frame_start)+1

            start_cam, end_cam = [cam_to_sample(k.cam) for k in keyframes]
            knots = [k.frame for k in keyframes]

        cam_samples = [start_cam, end_cam]
        filenames = []

        wm.progress_update(3)

        for i, metric in enumerate(metrics):
            """
            convex_hull_obj.hide_set(False)
            move_around_object.hide_set(True)
            """
            print(metric)
            try:
                self._path = interpolate_keyframes(cam_samples, knots, cam_samples[0]["focal"],
                                                   metric, props.method, n_frames,
                                                   rho=props.rho, generate_earth_file=generate_earth_file,
                                                   move_around_object=move_around_object,
                                                   geodesic_path_object=geodesic_paths[i % 2],
                                                   min_greedy_point_difference=min_greedy_point_difference,
                                                   file_path=exporting_path)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.report({'ERROR_INVALID_INPUT'}, "Could not compute path")

                return {'CANCELLED'}

            cam_path_obj = paths[i]
            update_path(cam_path_obj, self._path)

            animate_camera(self._path, cams[i])

            if render_animation:
                """
                convex_hull_obj.hide_set(True)
                move_around_object.hide_set(False)
                """
                filenames.append(f"{exporting_path}\\{metric}.mp4")
                render_scene(cams[i], filenames[-1], end_frame=n_frames)
            wm.progress_update(3 + 90 / len(metrics) * (i + 1))

        if render_animation:
            start_pos, end_pos = get_look_at_points([start_cam, end_cam])
            start_sphere, end_sphere = create_spheres_at([start_pos, end_pos], random_coll_name)
            start_cam_sphere, end_cam_sphere = create_spheres_at([start_cam["position"], end_cam["position"]],
                                                                 random_coll_name)
            # copy state before
            mat_copy = move_around_object.data.materials[:]
            # make object
            added_materials = [add_material([move_around_object], (1, 1, 1, 0.6), False),
                               # mark path
                               # add_material([geodesic_path], (1, 0.46, 0, 1), False),
                               # mark start and end point (colored)
                               add_material([start_sphere, end_sphere], (1, 0, 0, 1), False),
                               add_material([start_cam_sphere, end_cam_sphere], (0, 0, 1, 1), False)]
            # geodesic_path.data.bevel_depth = 0.05
            # create and positioning cam
            cam = create_outside_cam(start_pos, end_pos, move_around_object, random_coll_name)
            # make photo
            image_path = f"{exporting_path}\\overview.png"
            render_single_image(cam, image_path)
            # undo everything
            move_around_object.data.materials.clear()
            for mat in mat_copy:
                move_around_object.data.materials.append(mat)
            # geodesic_path.data.bevel_depth = 0
            for mat in added_materials:
                bpy.data.materials.remove(mat)

            bpy.data.objects.remove(start_sphere)
            bpy.data.objects.remove(cam)
            bpy.data.objects.remove(end_sphere)

            combine_clips(filenames, image_path, exporting_path)

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
