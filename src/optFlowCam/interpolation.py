import math

import numpy as np
import bisect
import copy
from functools import partial
from multiprocessing.pool import Pool
from typing import Any

from pygeodesic import geodesic

import bpy
import bmesh
from mathutils import Vector, Quaternion

from .math import get_rotation, normalized, get_orthonormal_basis
from .objects.path_geometry import add_path_object, update_path
from .utility import unpack_camera

from .objects.GoogleEarthFile import GoogleEarthStudio, extract_rotation, camMatrixByPosition


def slerp(p1, p2, t, arc_length):
    angle_between = math.acos(arc_length)
    if angle_between < math.pi / 180 / 4:
        return (1 - t) * p1 + t * p2

    return (math.sin((1 - t) * angle_between) / math.sin(angle_between) * p1
            + math.sin(t * angle_between) / math.sin(angle_between) * p2)


def interpolate_points_spherical(p1, p2, middle, t, arc_length, radius):
    p1_n, p2_n = normalized(p1 - middle), normalized(p2 - middle)
    p = slerp(p1_n, p2_n, t, arc_length)
    # return p / np.linalg.norm(p) * radius + middle
    return normalized(p) * radius + middle


def weighted_decasteljeau(points, weights, t):
    p = [[Vector([0, 0, 0]) for _ in range(1, n + 1)] for n in range(len(points), 0, -1)]
    p[0] = points[::]
    w = [[0 for _ in range(0, n)] for n in range(len(weights), 0, -1)]
    w[0] = weights[::]
    # copyto!(w[1], weights)
    for idx in range(1, len(points) + 1):
        for i in range(0, len(points) - idx):
            w[idx][i] = (1 - t) * w[idx - 1][i] + t * w[idx - 1][i + 1]
            p[idx][i] = (w[idx - 1][i] * (1 - t) * p[idx - 1][i] + w[idx - 1][i + 1] * t * p[idx - 1][i + 1]) / w[idx][
                i]
    return p[-1][0]


def calculate_north_alignment(cam, earth_radius):
    # maybe dir is just vector to in plane of current height
    # forward = cam["view"]
    """
    up = Vector([0, 0, 1])
    x,y,z = cam["position"]
    forward = -Vector([x,y,0]).normalized()
    # forward = Vector([forward[0], forward[1], 0]).normalized()
    right = normalized(np.cross(up, forward))
    return {
        'view': list(forward),
        'up': list(up),
        'right': list(right),
        'position': cam["position"],
        'focal': 1.639344262295082,
        'frustum_scale': cam["frustum_scale"]
    }
    # right = up x forward
    """
    # calculate spherical coordinates
    longitude, latitude, altitude, _, _, _ = extract_rotation(cam, earth_radius=earth_radius)
    """
    # E_pio = pos-earth.location
    longitude = math.atan2(E_pio[1], E_pio[0])
    latitude = math.atan2(E_pio[2], E_pio[0] / cos(longitude))
    altitude = Vector(E_pio).length  # - earth_radius  # for resulting file ist must be scaled to earth scale
    altitude = get_height(altitude, earth_radius)
    """
    # calculate rotation-matrix from these values with pan/tilt/roll = 0
    matrix, distance = camMatrixByPosition(math.degrees(latitude), math.degrees(longitude), altitude, 0, 0, 0,
                                           r=earth_radius)
    """
    cam_obj.matrix_world = matrix
    cam_obj.scale = scale * Vector((1, 1, 1))
    """
    """
    mat = cam.matrix_world
    pos, rot, _ = mat.decompose()
    forw = rot @ Vector((0,0,-1))
    up = rot @ Vector((0,1,0))
    c = {
        'position': list(pos),
        'view' : list(forw),
        'up' : list(up),
        'focal' : get_focal_length(cam),
        'frustum_scale' : max(list(cam.scale))
    }
    """

    """
    f = 1.639344262295082
    scale = -distance/f

    cam_obj.data.lens = f * cam_obj.data.sensor_width
    cam_obj.matrix_world = matrix
    cam_obj.scale = scale * Vector((1, 1, 1))
    
    
    mat = cam.matrix_world
    pos, rot, _ = mat.decompose()
    forw = rot @ Vector((0,0,-1))
    up = rot @ Vector((0,1,0))

    c = {
        'position': list(pos),
        'view' : list(forw),
        'up' : list(up),
        'focal' : get_focal_length(cam),
        'frustum_scale' : max(list(cam.scale))
    }
    """

    f = 1.639344262295082
    scale = -distance / f

    # mat = cam.matrix_world
    pos, rot, _ = matrix.decompose()
    forw = normalized(rot @ Vector((0, 0, -1)))
    up = normalized(rot @ Vector((0, 1, 0)))

    right = normalized(np.cross(up, forw))
    cam = {
        'position': list(pos),
        'view': list(forw),
        'up': list(up),
        'right': list(right),
        'focal': 1.639344262295082,
        'frustum_scale': scale
    }
    return cam


def interpolate_matrices(start, end, earth_radius, weight, t):
    start_north = calculate_north_alignment(start, earth_radius)
    end_north = calculate_north_alignment(end, earth_radius)
    cam = weighted_rotation_interpolation([start, start_north, end_north, end], [1, weight, weight, 1], t)
    vecs = [cam[key] for key in ["view", "right", "up"]]

    # pos, view, up, right, s = unpack_camera(cam)
    # vecs =

    # basis matrix for start
    R = np.array([vecs[1], vecs[2], vecs[0]]).T
    """
    right = cam["right"]
    up = cam["up"]
    view = cam["view"]
    R = np.array([right, up, view]).T
    """
    """
        up = R[:, 1]
    view = R[:, 2]
    right = R[:, 0]
    """
    return R


def interpolate_matrices_2(start, end, t):
    print(f"Rotation between: {start} and \n{end} \nat t={t}")
    _, R_f = get_rotation(start, end)
    R = R_f(t)
    up = R[:, 1]
    view = R[:, 2]
    right = R[:, 0]
    # _, _, right = get_orthonormal_basis({"view": view, "up": up})
    return {"view": view, "up": up, "right": right}


def weighted_rotation_interpolation(matrices, weights, t):
    w = [i for i in weights]
    for idx in range(1, len(matrices) + 1):
        for i in range(0, len(matrices) - idx):
            t_normalized = (w[i + 1] * t) / ((1 - t) * w[i] + t * w[i + 1])
            matrices[i] = interpolate_matrices_2(matrices[i], matrices[i + 1], t)
            w[i] = (1 - t) * w[i] + t * w[i + 1]
    return matrices[0]


def export_geoposition_data(cams, num_frames, metric, file_path, earth_center=Vector((0, 0, 0)), earth_radius=10):
    if num_frames != len(cams):
        num_frames = len(cams)
    studio = GoogleEarthStudio(num_frames, metric, 30, earth_center, earth_radius)
    for idx, cam in enumerate(cams):
        if not np.isnan(cam["position"][0]):
            studio.append_frame(cam, idx)

    studio.createAnimation(f"{file_path}\\{metric}.esp")


def new_face(face, insert_idx):
    face_0 = (face[0], face[1], insert_idx)
    face_1 = (face[0], face[2], insert_idx)
    face_2 = (face[1], face[2], insert_idx)
    return face_0, face_1, face_2


def shortest_path_of(path, min_distance=2):
    """
    Greedy modification of the path to remove parts of the curve that does not intersect with the mesh"""
    """
    1. find all lines that have no intersection with the mesh
    2. don't take the ones tha are fully inside another line (but potentially they are also necessary)
    3. sort lines from longest to shortest
    4. remove the shorter lines with intersections to longer lines
    5. remove the corresponding points of the path
    """
    # simple idea
    context = bpy.context
    vl = context.view_layer
    scene = context.scene
    # worst case: O(n^3/6) or O(n/3 * n * n/2)
    # more likely: O(k * n^2/2) or O(k * n * n/2) with k << n
    while True:
        # print(len(path))
        longest_line = None
        for idx, coord in enumerate(path):
            for i in range(len(path) - 1, idx + (min_distance - 1), -1):
                if longest_line and longest_line[2] > i - idx:
                    break
                direction = Vector(path[i] - coord)
                length = direction.length
                hit, loc, norm_0, face_idx, obj_0, mw_0 = scene.ray_cast(vl.depsgraph, coord,
                                                                         direction, distance=length)
                if not hit or (loc - coord).length > length:
                    if not longest_line:
                        longest_line = (idx, i, i - idx)
                    elif longest_line and i - idx > longest_line[2]:
                        longest_line = (idx, i, i - idx)
                    break
        if not longest_line:
            return path
        else:
            del path[longest_line[0] + 1:longest_line[1]]
        if len(path) < 3:
            return path


def lift_path(path, obj, factor=0.00001):
    """
    Lift the given points by a small factor along the normal
    """
    result = []
    mat_inv = obj.matrix_world.inverted()
    mat = obj.matrix_world
    for step in path:
        hit, pos, normal, face_idx = obj.closest_point_on_mesh(mat_inv @ Vector(step))
        result.append(mat @ (pos + normal * factor))
    return result


def calculate_sphere_lookat(position, view_direction, center, radius) -> Vector:
    forward = -view_direction
    E = position - center
    A = forward
    ae = np.cross(A, E)
    print(ae, A)
    dd = -np.dot(A, E) + math.sqrt(radius ** 2 * np.dot(A, A) - np.dot(ae, ae))
    lookat = position + forward * dd
    return lookat  # , lookat.length, dd


class InterpolateGeodesic:
    """
    Class to calculate and interpolate the geodesic between two camera look-at points
    """

    def __init__(self, start_cam: dict, end_cam: dict, focal: float, greedy_method=False,
                 min_greedy_point_difference=2, is_sphere=False):
        """
        Initialized attributes and calculates the geodesic between start and end cam
        """
        self.is_sphere = is_sphere
        self.start = None
        self.end = None
        start_eyepoint = Vector(start_cam["position"])
        start_view_direction = Vector(start_cam["view"])
        end_eyepoint = Vector(end_cam["position"])
        end_view_direction = Vector(end_cam["view"])
        self.greedy_geodesic = greedy_method
        if self.greedy_geodesic:
            self.min_greedy_point_difference = min_greedy_point_difference

        context = bpy.context
        vl = context.view_layer
        self.distance = None
        self.path = []

        if not is_sphere:
            # print("initializing")
            obj, start_face_idx, start_loc = self.raycast(start=start_eyepoint, direction=start_view_direction)
            obj2, end_face_idx, end_loc = self.raycast(start=end_eyepoint, direction=end_view_direction)
            if obj and obj == obj2 and obj.type == "MESH":
                self.mesh = obj.evaluated_get(vl.depsgraph).to_mesh()
                self.obj = obj
            else:
                raise ValueError("Start-/Endkamera müssen auf dasselbe Objekt gerichtet sein")

            if start_face_idx == end_face_idx:
                self.path = [(start_loc, 0), (end_loc, 1)]
                self.distance = (start_loc - end_loc).length
            else:
                faces = [i.vertices for i in self.mesh.polygons if
                         i.index != start_face_idx and i.index != end_face_idx]
                start_face = self.mesh.polygons[start_face_idx].vertices
                end_face = self.mesh.polygons[end_face_idx].vertices
                faces += new_face(start_face, len(self.mesh.vertices))
                faces += new_face(end_face, len(self.mesh.vertices) + 1)
                self.geodesic_calc = geodesic.PyGeodesicAlgorithmExact(
                    [self.obj.matrix_world @ i.co for i in self.mesh.vertices] + [start_loc, end_loc], faces)
                self.calculate(0, 1, len(self.mesh.vertices))
        else:
            center = Vector([0, 0, 0])  # self.obj.location
            radius = 100  # self.obj.scale[0]  # (self.obj.matrix_world@self.mesh.vertices[0].co-center).length
            self.sphere_data = (center, radius)

            self.start_loc = calculate_sphere_lookat(start_eyepoint, start_view_direction, center, radius)
            self.end_loc = calculate_sphere_lookat(end_eyepoint, end_view_direction, center, radius)
            # self.arc_length = (self.start_loc - center).normalized() @ (self.end_loc - center).normalized()
            self.arc_length = normalized(self.start_loc - center) @ normalized(self.end_loc - center)
            self.arc_length = max(min(self.arc_length, 1), -1)
            print(f"arc length: {self.arc_length}")
            self.distance = radius * math.acos(
                self.arc_length)  # np.linalg.norm(self.end_loc - self.start_loc)#.length  # back radius * math.acos(self.arc_length)

        print("Distance: ", self.distance, is_sphere)

    def calculate(self, start_t, end_t, idx):
        """
        Calculate the geodesic path between start and end and combine path with time.
        """
        assert start_t < end_t

        path = self.find_geodesic_path_between(idx, idx + 1)
        # print(f"Length of {'modified' if self.greedy_geodesic else ''} path: {len(path)}")
        self.mix_path_with_time(path, start_t, end_t)

    def set_start_end(self, start, end):
        self.start = start
        self.end = end

    def get_distance(self):
        return self.distance

    def interpolate(self, t):
        """
        Interpolates a point of the geodesic path by t (0 <= t <= 1)
        structure of self.path[i] = (coordinates, time)
        """
        if not self.is_sphere:
            # print(f"interpolation {t}")
            idx = self.find_t_idx(t)
            idx = min(max(0, idx), len(self.path) - 1)
            next_element = self.path[idx]
            next_t = next_element[1]
            if next_t != t:
                last_element = self.path[idx - 1]
                last_t = last_element[1]
                t_diff = next_t - last_t
                t_part = (t - last_t) / t_diff
                return (1 - t_part) * last_element[0] + t_part * next_element[0]
            else:
                return next_element[0]
        else:
            center, radius = self.sphere_data
            return interpolate_points_spherical(self.start_loc, self.end_loc, center, t, self.arc_length, radius)
            # return self.sphere_data[0]*Vector(slerpQuaternion(self.q1, self.q2, t)[1:])

    def raycast(self, start, direction) -> tuple[Any, Any, Any]:
        context = bpy.context
        vl = context.view_layer
        scene = context.scene

        hit, loc, norm_0, face_idx, obj_0, mw_0 = scene.ray_cast(vl.depsgraph, start, direction)
        assert hit, "Cameras must be pointed at an object"
        return obj_0, face_idx, loc

    def find_geodesic_path_between(self, start_idx, end_idx):
        distance, path = self.geodesic_calc.geodesicDistance(end_idx, start_idx)
        if self.greedy_geodesic:
            path = lift_path(path, self.obj, 0.00001)
            path = shortest_path_of(path, self.min_greedy_point_difference)
            distance = 0
            for i in range(1, len(path)):
                distance += np.linalg.norm(path[i] - path[i - 1])

        self.distance = distance
        # print("path calculated")
        return path

    def mix_path_with_time(self, path, start_t, end_t):
        t_diff = end_t - start_t
        self.path.append((path[0], start_t))
        for idx in range(1, len(path) - 1):
            current_dist = np.linalg.norm(path[idx] - path[idx - 1])
            self.path.append((path[idx], self.path[idx - 1][1] + t_diff * current_dist / self.distance))
        self.path.append((path[-1], end_t))

    def find_t_idx(self, t):
        return bisect.bisect_left(self.path, t, key=lambda x: x[1])

    def update_path_object(self, path_object):
        if self.is_sphere:
            update_path(path_object,
                        [{"position": i[0]} for i in [self.interpolate(t) for t in np.linspace(0, 1, 100)]])
        else:
            update_path(path_object, [{"position": i[0]} for i in self.path])


interpolate_geodesics: list[InterpolateGeodesic] = []


def get_zoom_pan_parameter_functions(w0: float, w1: float,
                                     u0: float, u1: float,
                                     rho: float = np.sqrt(2)) -> tuple:
    '''
    Returns the parameter functions u and w as well as the path length S in the
    zoom and panning metric. With rho=sqrt(2), this is equivalent to the
    formulas we used in our paper.
    '''
    # see
    # J. J. van Wijk and W. A. A. Nuij, “Smooth and efficient zooming and panning,”
    # in IEEE Symposium on Information Visualization 2003 (IEEE Cat. No.03TH8714), 2003-10, pp. 15–23.
    # doi: 10.1109/INFVIS.2003.1249004.

    # no panning
    if np.isclose(u1 - u0, 0, atol=1e-14):
        us = lambda s: u0

        # also no zooming
        if np.isclose(w1 - w0, 0, atol=1e-14):
            return us, lambda s: w0, 1

        S = np.abs(np.log(w1 / w0)) / rho

        k = -1 if w1 < w0 else 1
        ws = lambda s: w0 * np.exp(k * rho * s)

        return us, ws, S

    # avoid ws being close to 0
    # because of numerical issues
    w0 = max(w0, 1e-6)
    w1 = max(w1, 1e-6)

    bi = lambda i: (w1 ** 2 - w0 ** 2 + (-1) ** i * rho ** 4 * (u1 - u0) ** 2) / (
            2 * [w0, w1][i] * rho ** 2 * (u1 - u0))

    def ri(bi):
        if np.abs(bi) > 1e6:
            return -np.sign(bi) * np.log(2 * np.abs(bi))
        else:
            return np.log(-bi + np.sqrt(bi ** 2 + 1))

    b0 = bi(int(0))
    b1 = bi(int(1))

    r0 = ri(b0)
    r1 = ri(b1)

    # reinnehmen assert not np.isnan(r0) and not np.isnan(r1)
    if np.isnan(r0) or np.isnan(r1):
        print(r0, r1, w0, w1, u0, u1)
        assert False

    S = (r1 - r0) / rho

    us = lambda s: w0 / (rho ** 2) * np.cosh(r0) * np.tanh(rho * s + r0) - w0 / (rho ** 2) * np.sinh(r0) + u0
    ws = lambda s: w0 * np.cosh(r0) / np.cosh(rho * s + r0)

    return us, ws, S


def get_zoom_pan_parameter(t: float, w0: float, w1: float,
                           u0: float, u1: float,
                           rho: float = np.sqrt(2)) -> tuple:
    '''
    Returns the parameter u and w for the path parameter t, where t0=0
    gives w0 and u0 and t1=1 gives w1 and u1.
    '''

    us, ws, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)
    return us(t * S), ws(t * S)


def get_zoom_pan_parameters(n: int, w0: float, w1: float,
                            u0: float, u1: float,
                            rho: float = np.sqrt(2)) -> tuple:
    '''
    Returns the parameter list for u and w for the range [0,1] divided
    into n samples.
    '''

    us, ws, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)

    ss = np.linspace(0, S, n)
    return us(ss), ws(ss)


"""
def shortest_dist_on_surface(start_point, end_point, meshes):
    pass


def find_good_way_between(look1: np.ndarray, look2: np.ndarray, meshes=None) -> int:
    ## Idee: Das nur 1x berechnen lassen und dann nur noch aufrufen
    points = raycast_between(look1, look2)
    best_ways = [look1]
    distances = []

    for i,point in enumerate(points):
        best_ways.append(point)
        if i%2==0:
            distances.append(np.linalg.norm(point-best_ways[-1]))
        else:
            distances.append(shortest_dist_on_surface(point, best_ways[-1], meshes))

    return sum(distances)


"""


def m(t: float, idx: int):
    assert len(interpolate_geodesics) > idx
    return interpolate_geodesics[idx].interpolate(t)


def find_fitting_geodesic(start: dict, end: dict) -> int:
    # global interpolate_geodesics
    """
    print(len(interpolate_geodesics))
    print("wanna find", start, end)
    print("in", [(g.start, g.end) for g in interpolate_geodesics])
    """
    for idx, geodesic in enumerate(interpolate_geodesics):
        if geodesic.start == start and geodesic.end == end:
            return idx
    return -1


def interpolate_along_earth_axis(start, end, earth_radius, weight):
    return lambda t: interpolate_matrices(start, end, earth_radius, weight, t)


def interpolate_t(t: float, focal: float, metric: str, **kwargs) -> dict:
    print(t)
    if "start" in kwargs and "end" in kwargs:
        start = kwargs["start"]
        end = kwargs["end"]

        if "3DImageFlowGeodesic" in metric:
            idx = find_fitting_geodesic(start, end)
            if idx == -1:
                interpolate_geodesics.append(
                    InterpolateGeodesic(start, end, greedy_method=False, focal=start["focal"],
                                        is_sphere="3DImageFlowGeodesicEarthRot" in metric or kwargs.get('is_earth',
                                                                                                        False)))
                start = resize(start, 0, interpolate_geodesics[-1])
                end = resize(end, 1, interpolate_geodesics[-1])
                interpolate_geodesics[-1].set_start_end(start, end)
                idx = len(interpolate_geodesics) - 1

        # assure orthonormal camera reference frame
        pos1, view1, up1, right1, s1 = unpack_camera(start)
        pos2, view2, up2, right2, s2 = unpack_camera(end)

    else:
        for arg in ["pos1", "view1", "up1", "right1", "s1", "pos2", "view2", "up2", "right2", "s2"]:
            if not arg in kwargs:
                raise ValueError(
                    f"Function 'interpolate_t' needs keyword argument '{arg}' if no 'start' and 'end' are given.")

        pos1 = kwargs["pos1"]
        view1 = kwargs["view1"]
        up1 = kwargs["up1"]
        right1 = kwargs["right1"]
        s1 = kwargs["s1"]

        pos2 = kwargs["pos2"]
        view2 = kwargs["view2"]
        up2 = kwargs["up2"]
        right2 = kwargs["right2"]
        s2 = kwargs["s2"]

    if (  # False and   # for Debugging purpose
            ("3DImageFlowGeodesicEarthRot" in metric
             and "earth_radius" in kwargs and kwargs["earth_radius"]
             and "weight" in kwargs and kwargs["weight"])):
        # u, _ = get_zoom_pan_parameter(1 / 3, 1, 1, 0, 1, kwargs["rho"])
        idx = find_fitting_geodesic(start, end)
        assert idx > -1, "No fitting geodesic found"
        lookat_start = m(0, idx)
        lookat_end = m(1, idx)
        R_f = interpolate_along_earth_axis(
            {"view": view1, "up": up1, "right": right1, "position": lookat_start, "frustum_scale": s1},
            {"view": view2, "up": up2, "right": right2, "position": lookat_end, "frustum_scale": s2},
            kwargs["earth_radius"], kwargs["weight"])
    else:
        if not "R_f" in kwargs:
            _, R_f = get_rotation({"view": view1, "up": up1, "right": right1},
                                  {"view": view2, "up": up2, "right": right2})
        else:
            R_f = kwargs["R_f"]

    # interpolating look at points
    look1 = pos1 + s1 * focal * view1
    look2 = pos2 + s2 * focal * view2

    look_diff = look2 - look1

    if metric == "LookatLinear":
        pos = (1 - t) * pos1 + t * pos2
        look = (1 - t) * look1 + t * look2
        view = normalized(look - pos)
        up = normalized((1 - t) * up1 + t * up2)

        cam = {
            "position": pos.tolist(),
            "view": view.tolist(),
            "up": up.tolist(),
            "frustum_scale": np.linalg.norm(look - pos) / focal,
            "focal": focal
        }

        return cam

    elif metric == "TransformationsLinear":
        u = t
        w = (1 - t) * s1 + t * s2

        cam = cam_from_params(u, w, R_f(t), focal, look1, look_diff)
        return cam

    elif "3DImageFlowGeodesic" in metric:
        rho = kwargs["rho"]

        # reinnehmen assert not np.isnan(s1), start
        w0 = s1
        w1 = s2
        u0 = 0
        """
        if "original_start" in kwargs:
            start = kwargs["original_start"]
        if "original_end" in kwargs:
            end = kwargs["original_end"]
        """

        # u1 = 1
        u1 = interpolate_geodesics[idx].get_distance()  # np.linalg.norm(look_diff)
        # assert u1 != 0, f"start: {start}    end: {end}"
        # look_diff_n = np.zeros(3) if u1 < 1e-14 else normalized(look_diff)
        u, w = get_zoom_pan_parameter(t, w0, w1, u0, u1, rho)
        if w == 0:
            print("error potential: ", start, end)
        # look_at_point = m(u)
        # look_diff_n = interpolate_geodesics.get_distance()
        # cam = cam_from_params2(u, w, R_f(t), focal, look_at_point, look_diff_n)
        cam = cam_from_params2(u / u1 if u1 != 0 else t, w, R_f(t), focal, idx)
        # cam = cam_from_params2(u / u1, w, R_f(t), focal, idx)
        # cam = cam_from_params2(u / u1, w, R_f(t), focal)

        return cam
    elif metric == "3DImageFlow":
        rho = kwargs["rho"]

        w0 = s1;
        w1 = s2
        u0 = 0;
        u1 = np.linalg.norm(look_diff)

        look_diff_n = np.zeros(3) if u1 < 1e-14 else normalized(look_diff)

        u, w = get_zoom_pan_parameter(t, w0, w1, u0, u1, rho)
        cam = cam_from_params(u, w, R_f(t), focal, look1, look_diff_n)

        return cam

    else:
        raise ValueError(f"Unknown metric {metric}")


def get_camera_distance(start: dict, end: dict,
                        focal: float, metric: str,
                        **kwargs) -> float:
    # assure orthonormal camera reference frame
    pos1, view1, up1, right1, s1 = unpack_camera(start)
    pos2, view2, up2, right2, s2 = unpack_camera(end)

    axisangle, _ = get_rotation({"view": view1, "up": up1, "right": right1},
                                {"view": view2, "up": up2, "right": right2})
    beta_end = axisangle.angle

    # interpolating look at points
    look1 = pos1 + s1 * focal * view1
    look2 = pos2 + s2 * focal * view2

    look_diff = look2 - look1

    dist = 0

    if metric == "LookatLinear" or metric == "TransformationsLinear":
        # this could be enhanced by determining the Riemannian metrics
        # for both metrics, but we will just use the distance one would
        # normally use
        dist = np.linalg.norm(pos2 - pos1)
    elif metric == "3DImageFlow":

        rho = kwargs["rho"]
        w0 = s1;
        w1 = s2
        u0 = 0;
        u1 = np.linalg.norm(look_diff)

        _, _, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)

        dist = np.sqrt((S * S) / 2 + (beta_end * beta_end) / 6)
    elif "3DImageFlowGeodesic" in metric:
        rho = kwargs["rho"]
        w0 = s1;
        w1 = s2
        u0 = 0;
        idx = find_fitting_geodesic(start, end)
        assert idx > -1, "No fitting geodesic found"
        u1 = interpolate_geodesics[idx].get_distance()
        # u1 = 1  # interpolate_geodesics.get_distance()

        _, _, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)
        dist = np.sqrt((S * S) / 2 + (beta_end * beta_end) / 6)
    else:
        raise ValueError(f"Unknown metric {metric}")

    return dist


def cam_from_params2(u: float, w: float,
                     R: np.ndarray, focal: float, idx: int) -> dict:
    # , start: np.ndarray, end: np.ndarray) -> dict:
    up = R[:, 1]
    view = R[:, 2]
    scale = w

    lookat = m(u, idx)
    # print("lookat", lookat)
    pos = np.array(lookat) - np.array(scale * focal * view)

    cam = {
        "position": pos.tolist(),
        "view": view.tolist(),
        "up": up.tolist(),
        "frustum_scale": scale,
        "focal": focal
    }
    # reinnehmen assert scale != 0, print(cam)
    return cam


def cam_from_params(u: float, w: float,
                    R: np.ndarray, focal: float,
                    lookat_pos: np.ndarray, lookat_dir: np.ndarray) -> dict:
    up = R[:, 1]
    view = R[:, 2]
    scale = w

    lookat = lookat_pos + u * lookat_dir
    pos = lookat - scale * focal * view

    cam = {
        "position": pos.tolist(),
        "view": view.tolist(),
        "up": up.tolist(),
        "frustum_scale": scale,
        "focal": focal
    }
    return cam


def clone_cam(cam):
    return {
        "position": cam["position"].copy(),
        "view": cam["view"].copy(),
        "up": cam["up"].copy(),
        "frustum_scale": cam["frustum_scale"],
        "focal": cam["focal"]
    }


def resize(cam, t, geodesic):
    # pos = lookat - scale * focal * view
    # => scale = (pos - lookat)/(focal*view)
    if geodesic:
        coords = Vector(geodesic.interpolate(t))

    pos = Vector(cam["position"])
    # cam["frustum_scale"] = (coords - pos).length / cam["focal"]
    cam["frustum_scale"] = np.linalg.norm(coords - pos) / cam["focal"]
    return cam


def interpolate_simple(start: dict, end: dict,
                       focal: float, metric: str,
                       n: int = 101, **kwargs) -> list:
    '''
    Simply interpolate between a start and end camera with n sample points
    according to the given metric.

    kwargs should contain the parameter rho if metric==3DImageFlow.
    '''
    """
    if "3DImageFlowGeodesic" in metric:
        global interpolate_geodesics
        greedy = metric == "3DImageFlowGeodesicGreedy"
        min_greedy_point_difference = 2
        if "min_greedy_point_difference" in kwargs:
            min_greedy_point_difference = kwargs["min_greedy_point_difference"]
        interpolate_geodesics = [InterpolateGeodesic(start_cam=start, end_cam=end, focal=focal, greedy_method=greedy,
                                                    min_greedy_point_difference=min_greedy_point_difference)]
        if "geodesic_path_object" in kwargs and kwargs["geodesic_path_object"]:
            interpolate_geodesics[0].update_path_object(kwargs["geodesic_path_object"])
        start_cam = clone_cam(start)
        end_cam = clone_cam(end)
        print("scale before: start = ", start_cam["frustum_scale"], ", end = ", end_cam["frustum_scale"])
        resize(start_cam, 0)
        resize(end_cam, 1)
        print("scale after: start = ", start_cam["frustum_scale"], ", end = ", end_cam["frustum_scale"])
        cams = [interpolate_t(t, focal, metric,
                              start=start_cam, end=end_cam,
                              **kwargs)
                for t in np.linspace(0, 1, n)]
    else:
        cams = [interpolate_t(t, focal, metric,
                              start=start, end=end,
                              **kwargs)
                for t in np.linspace(0, 1, n)]
    """
    cams = [interpolate_t(t, focal, metric,
                          start=start, end=end,
                          **kwargs)
            for t in np.linspace(0, 1, n)]
    return cams


def interpolate_deCasteljau(t: float, control_points: list,
                            focal: float, metric: str, **kwargs) -> dict:
    if len(control_points) == 1:
        return control_points[0]

    new_control_points = [interpolate_t(t, focal, metric, start=cp, end=control_points[i + 1], **kwargs)
                          for i, cp in enumerate(control_points[:-1])]

    return interpolate_deCasteljau(t, new_control_points, focal, metric, **kwargs)


def interpolate_bezier(control_points: list, focal: float, metric: str, n: int = 101, **kwargs) -> list:
    if len(control_points) == 2:
        return interpolate_simple(control_points[0], control_points[1], focal, metric, n, **kwargs)

    cams = [interpolate_deCasteljau(t, control_points, focal, metric, **kwargs)[0]
            for t in np.linspace(0, 1, n)]

    return cams


def get_segment_index(t: float, knots: list) -> int:
    segment_index = bisect.bisect_left(knots, t) - 1
    return segment_index


def interpolate_CatmullRom(t: float, control_points: list, knots: list,
                           focal: float, metric: str, **kwargs) -> dict:
    assert len(control_points) == len(knots), f"Number of control points and number of knots do not match"

    if len(control_points) == 1:
        return control_points[0]

    if t <= knots[0]:
        return control_points[0]
    if t >= knots[-1]:
        return control_points[-1]

    segment_index = get_segment_index(t, knots)

    cpy_index_min = np.max([segment_index - 1, 0])
    cpy_index_max = np.min([segment_index + 3, len(control_points)])

    segment_control_points = copy.deepcopy(control_points[cpy_index_min:cpy_index_max])
    segment_knots = copy.deepcopy(knots[cpy_index_min:cpy_index_max])

    # need additional control points at the start and end to do Catmull-Rom
    if segment_index == 0:
        augmentation_point = copy.deepcopy(control_points[0])
        segment_control_points.insert(0, augmentation_point)

        augmentation_knot = -knots[1] + 2 * knots[0]
        segment_knots = np.insert(segment_knots, 0, augmentation_knot)

    if segment_index >= len(knots) - 2:
        augmentation_point = copy.deepcopy(control_points[-1])
        segment_control_points.append(augmentation_point)

        augmentation_knot = -knots[-2] + 2 * knots[-1]
        segment_knots = np.append(segment_knots, augmentation_knot)

    assert len(segment_control_points) == 4 and len(
        segment_knots) == 4, f"Should be 4 but is {len(segment_control_points)} and {len(segment_knots)}"

    # see
    # C. Yuksel, S. Schaefer, and J. Keyser, “On the parameterization of Catmull-Rom curves,”
    # in 2009 SIAM/ACM Joint Conference on Geometric and Physical Modeling, 2009-10.
    # doi: 10.1145/1629255.1629262.
    for j in range(3):
        for i in range(len(segment_control_points) - j - 1):
            if j <= 1:
                s = (t - segment_knots[i]) / (segment_knots[i + 1 + j] - segment_knots[i])
            else:
                s = (t - segment_knots[1]) / (segment_knots[2] - segment_knots[1])

            start = segment_control_points[i]
            end = segment_control_points[i + 1]
            """
            if "3DImageFlowGeodesic" in metric and find_fitting_geodesic(start, end) == -1:
                interpolate_geodesics.append(
                    InterpolateGeodesic(start, end, greedy_method=True, focal=start["focal"],
                                        is_sphere="3DImageFlowGeodesicEarthRot" in metric or kwargs.get('is_earth',
                                                                                                        False)))
                start = resize(start, 0, interpolate_geodesics[-1])
                end = resize(end, 1, interpolate_geodesics[-1])
                interpolate_geodesics[-1].set_start_end(start, end)

            if interpolate_geodesics and start == end:
                cam = interpolate_t(s, focal, metric, start=original_start, end=original_end, **kwargs)
            else:
            """
            cam = interpolate_t(s, focal, metric, start=start, end=end, **kwargs)
            # , original_start=original_start, original_end=original_end, original_start_t=current_t[i], original_end_t=current_t[i + 1])
            """
            if np.isnan(cam["position"][0]):
                print(j, i, segment_control_points, cam)
            """
            segment_control_points[i] = cam

    return segment_control_points[0]


def disambiguate_spline(control_points: list, knots: list, spline: list):
    """
    Inserts new control points and knots to resolve any gaps/discontinuities
    that may be present in the spline.

    Depending on the original control points, this function may not detect
    the discontinuities reliably or detect some that are not present.
    """

    # this could be further improved because the current implementation
    # is prone to false positives/negatives due to absolute tolerances

    spline_positions = [np.array(c["position"]) for c in spline]

    last_fixed_segment = -1

    new_control_points = copy.deepcopy(control_points)
    new_knots = np.copy(knots)

    for i in range(1, len(spline) - 2):

        t = i / (len(spline) + 1)
        segment_index = get_segment_index(t, knots)

        # insert a maximum of one control point per segment
        # to avoid forcing the path to join
        # incompatible segments
        if last_fixed_segment == segment_index:
            continue

        di_1 = spline_positions[i] - spline_positions[i - 1]
        di = spline_positions[i + 1] - spline_positions[i]
        di1 = spline_positions[i + 2] - spline_positions[i + 1]

        norm_di_1 = np.linalg.norm(di_1)
        norm_di = np.linalg.norm(di)
        norm_di1 = np.linalg.norm(di1)

        dot_di_di_1 = np.dot(di_1, di) / (norm_di * norm_di_1)
        dot_di_di1 = np.dot(di1, di) / (norm_di * norm_di1)

        angle_discontinuous = (not np.isclose(dot_di_di_1, 1, atol=0.2) and \
                               not np.isclose(dot_di_di1, 1, atol=0.2))

        length_discontinuous = (not np.isclose(norm_di, norm_di_1, rtol=0.2) and \
                                not np.isclose(norm_di, norm_di1, rtol=0.2) and \
                                not np.isclose(norm_di, 0, atol=0.01))

        if angle_discontinuous or length_discontinuous:

            print(f"i:{i} t:{t} segment:{segment_index} angle:{angle_discontinuous} length:{length_discontinuous}")
            print(f"cos angle di-1 and di: {dot_di_di_1} di+1 and di: {dot_di_di1}")
            print(f"norms di-1: {norm_di_1} di: {norm_di} di+1: {norm_di1}")

            if np.any(list(map(lambda knot: np.isclose(t, knot), new_knots))):
                # if t is close to a knot (or the same) inserting
                # the new point can cause problems when computing the
                # spline and is probably a false positive
                continue

            cam = spline[i]

            new_segment_index = get_segment_index(t, new_knots)

            new_control_points.insert(new_segment_index + 1, cam)
            new_knots = np.insert(new_knots, new_segment_index + 1, t)

            last_fixed_segment = segment_index

    return new_control_points, new_knots


def interpolate_keyframes(control_points: list, knots: list,
                          focal: float, metric: str, method: str,
                          n: int = 101, **kwargs) -> list:
    if (
            metric == "3DImageFlow" or metric == "3DImageFlowGeodesic" or metric == "3DImageFlowGeodesicGreedy") and not "rho" in kwargs:
        kwargs["rho"] = np.sqrt(2)
        print("No named argument rho given for metric 3DImageFlow. Using default parameter sqrt(2).")

    if len(control_points) != len(knots):
        raise ValueError("Number of control points and number of knots are not equal")

    new_control_points = []
    if "3DImageFlowGeodesic" in metric:
        greedy = metric == "3DImageFlowGeodesicGreedy"
        min_greedy_point_difference = 2
        if "min_greedy_point_difference" in kwargs:
            min_greedy_point_difference = kwargs["min_greedy_point_difference"]

        new_control_points = [clone_cam(cam) for cam in control_points]
        for i in range(0, len(control_points) - 1):
            interpolate_geodesics.append(
                InterpolateGeodesic(start_cam=control_points[i], end_cam=control_points[i + 1], focal=focal,
                                    greedy_method=greedy,
                                    min_greedy_point_difference=min_greedy_point_difference,
                                    is_sphere="3DImageFlowGeodesicEarthRot" in metric or kwargs.get('is_earth', False)))
            new_control_points[i] = resize(new_control_points[i], 0, interpolate_geodesics[i])
            if i > 0:
                interpolate_geodesics[i - 1].set_start_end(new_control_points[i - 1], new_control_points[i])
        new_control_points[-1] = resize(new_control_points[-1], 1, interpolate_geodesics[-1])
        interpolate_geodesics[-1].set_start_end(new_control_points[-2], new_control_points[-1])
    else:
        new_control_points = control_points

    if len(new_control_points) == 2:
        return interpolate_simple(new_control_points[0], new_control_points[1], focal, metric, n, **kwargs)

    normalized_knots = np.array(copy.deepcopy(knots))
    normalized_knots -= knots[0]
    normalized_knots = normalized_knots / (knots[-1] - knots[0])

    cams = None
    if method == "Linear":
        cams = []
        for i, knot in enumerate(knots[:-1]):
            nn = knots[i + 1] - knot
            cams.extend(
                interpolate_simple(new_control_points[i], new_control_points[i + 1], focal, metric, nn, **kwargs))
        return cams

    # with Pool() as pool:
    if True:
        if method == "CatmullRom":
            n_control_points = len(new_control_points)
            """
            cams = pool.map(partial(interpolate_CatmullRom, control_points=new_control_points, knots=normalized_knots,
                                    focal=focal, metric=metric, **kwargs),
                            np.linspace(0, 1, n))
            """
            cams = [interpolate_CatmullRom(t=t, control_points=new_control_points, knots=normalized_knots,
                                           focal=focal, metric=metric, **kwargs) for t in np.linspace(0, 1, n)]

            for i in range(4):
                control_points, normalized_knots = disambiguate_spline(control_points, normalized_knots, cams)
                # print("Kontrollpunkte:", n_control_points, len(control_points), len(normalized_knots))
                if n_control_points == len(control_points):
                    break

                n_control_points = len(control_points)
                """
                cams = pool.map(partial(interpolate_CatmullRom, control_points=control_points, knots=normalized_knots,
                                        focal=focal, metric=metric, **kwargs),
                                np.linspace(0, 1, n))
                """
                """
                if any([np.isnan(i["position"][0]) for i in control_points]):
                    print(control_points)
                """
                cams = [interpolate_CatmullRom(t=t, control_points=control_points, knots=normalized_knots,
                                               focal=focal, metric=metric, **kwargs) for t in np.linspace(0, 1, n)]
        elif method == "Bezier":
            """
            cams = pool.map(partial(interpolate_deCasteljau, control_points=new_control_points, focal=focal,
                                    metric=metric, **kwargs),
                            np.linspace(0, 1, n))
            """
            cams = [interpolate_deCasteljau(t=t, control_points=new_control_points, focal=focal,
                                            metric=metric, **kwargs) for t in np.linspace(0, 1, n)]
        else:
            raise ValueError(f"Method {method} unknown")

        """
        pool.close()
        pool.join()
        """
    interpolate_geodesics.clear()

    if "generate_earth_file" in kwargs and kwargs["generate_earth_file"]:
        print("Exporting data...")
        earth = kwargs["move_around_object"]
        earth_position = earth.location
        earth_radius = (earth.matrix_world @ (earth.data.vertices[0].co - earth.location)).length
        export_geoposition_data(cams, n, metric, kwargs["file_path"], earth_center=earth_position,
                                earth_radius=earth_radius)
        print("Exporting finished")
    return cams
