import numpy as np
import bisect
import copy
from functools import partial
from multiprocessing.pool import Pool
from typing import Any

import bmesh
import bpy

from pygeodesic import geodesic

from mathutils import Vector

from .math import get_rotation, normalized
from .objects.path_geometry import add_path_object, update_path
from .utility import unpack_camera

from .objects.GoogleEarthFile import GoogleEarthStudio


def export_geoposition_data(cams, num_frames, metric, file_path, earth_center=Vector((0, 0, 0)), earth_radius=10):
    if num_frames != len(cams):
        num_frames = len(cams)
    studio = GoogleEarthStudio(num_frames, metric, 30, earth_center, earth_radius)
    for idx, cam in enumerate(cams):
        studio.append_frame(cam, idx)

    studio.createAnimation(f"{file_path}\\{metric}.esp")


def new_face(face, insert_idx):
    face_0 = (face[0], face[1], insert_idx)
    face_1 = (face[0], face[2], insert_idx)
    face_2 = (face[1], face[2], insert_idx)
    return face_0, face_1, face_2


def shortest_path_of(path, min_distance=2):
    # better idea (maybe => less intersection calculations)
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
        print(len(path))
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


def lift_up(path, obj, factor=0.00001):

    result = []
    mat_inv = obj.matrix_world.inverted()
    mat = obj.matrix_world
    for step in path:
        hit, pos, normal, face_idx = obj.closest_point_on_mesh(mat_inv @ Vector(step))
        result.append(mat @ (pos + normal * factor))
    return result


class InterpolateGeodesic:
    def __init__(self, start_cam, end_cam, focal, greedy_method=False, min_greedy_point_difference=2):
        """
        Initialized attributes and calculates the geodesic between start and end cam
        """
        start_eyepoint = start_cam["position"]
        start_view_direction = start_cam["view"]
        end_eyepoint = end_cam["position"]
        end_view_direction = end_cam["view"]
        self.greedy_geodesic = greedy_method
        if self.greedy_geodesic:
            self.min_greedy_point_difference = min_greedy_point_difference

        context = bpy.context
        vl = context.view_layer
        obj, start_face_idx, start_loc = self.raycast(start=start_eyepoint, direction=start_view_direction)
        obj2, end_face_idx, end_loc = self.raycast(start=end_eyepoint, direction=end_view_direction)
        print("-----Startposition auf dem Mesh----------")
        print(start_loc)
        print("-----Endposition auf dem Mesh----------")
        print(end_loc)
        if obj and obj == obj2 and obj.type == "MESH":
            self.mesh = obj.evaluated_get(vl.depsgraph).to_mesh()
            self.obj = obj
        else:
            raise ValueError("Start-/Endkamera müssen auf dasselbe Objekt gerichtet sein")
        self.distance = None
        self.path = []
        if start_face_idx == end_face_idx:
            self.path = [(start_loc, 0), (end_loc, 1)]
            self.distance = (start_loc - end_loc).length
        else:
            faces = [i.vertices for i in self.mesh.polygons if i.index != start_face_idx and i.index != end_face_idx]

            start_face = self.mesh.polygons[start_face_idx].vertices  # faces.pop(start_face_idx)
            end_face = self.mesh.polygons[end_face_idx].vertices  # faces.pop(end_face_idx)
            faces += new_face(start_face, len(self.mesh.vertices))
            faces += new_face(end_face, len(self.mesh.vertices) + 1)
            self.geodesic_calc = geodesic.PyGeodesicAlgorithmExact(
                [self.obj.matrix_world @ i.co for i in self.mesh.vertices] + [start_loc, end_loc], faces)
            # [i for i in bpy.data.meshes["Icosphere"].polygons[0].vertices] )# self.mesh.polygons)
            self.calculate(0, 1, len(self.mesh.vertices))

    def calculate(self, start_t, end_t, idx):
        """
        Calculate the geodesic path between start and end and combine path with time.
        """
        assert start_t < end_t

        path = self.find_geodesic_path_between(idx, idx + 1)
        print(f"Length of {'modified' if self.greedy_geodesic else ''} path: {len(path)}")
        self.mix_path_with_time(path, start_t, end_t)

    def get_distance(self):
        return self.distance

    def interpolate(self, t):
        """
        Interpolates a point of the geodesic path by t (0 <= t <= 1)
        """
        # structure of self.path[i] = (coordinates, time)
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

    def raycast(self, start, direction) -> tuple[Any, Any, Any]:
        context = bpy.context
        vl = context.view_layer
        scene = context.scene

        hit, loc, norm_0, face_idx, obj_0, mw_0 = scene.ray_cast(vl.depsgraph, start, direction)
        assert hit, "Cameras must be pointed at an object"
        return obj_0, face_idx, loc

    def find_geodesic_path_between(self, start_idx, end_idx):
        distance, path = self.geodesic_calc.geodesicDistance(end_idx, start_idx)
        print("From", start_idx)
        print("to", end_idx)
        print("Distance", distance)
        if self.greedy_geodesic:
            path = lift_up(path, self.obj)
            print("before modification:", path[0], path[-1])
            path = shortest_path_of(path)
            print("after modification:", path[0], path[-1])
            distance = 0
            for i in range(1, len(path)):
                distance += np.linalg.norm(path[i] - path[i - 1])

        self.distance = distance
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
        update_path(path_object, [{"position": i[0]} for i in self.path])


interpolate_geodesics: InterpolateGeodesic = None


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

    assert not np.isnan(r0) and not np.isnan(r1)

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


def m(t):
    assert interpolate_geodesics is not None
    return interpolate_geodesics.interpolate(t)


def interpolate_t(t: float, focal: float, metric: str, **kwargs) -> dict:
    if "start" in kwargs and "end" in kwargs:
        start = kwargs["start"]
        end = kwargs["end"]

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

        w0 = s1
        w1 = s2
        u0 = 0
        # u1 = 1
        u1 = interpolate_geodesics.get_distance()  # np.linalg.norm(look_diff)
        # look_diff_n = np.zeros(3) if u1 < 1e-14 else normalized(look_diff)
        u, w = get_zoom_pan_parameter(t, w0, w1, u0, u1, rho)

        # look_at_point = m(u)
        # look_diff_n = interpolate_geodesics.get_distance()
        # cam = cam_from_params2(u, w, R_f(t), focal, look_at_point, look_diff_n)
        cam = cam_from_params2(u / u1, w, R_f(t), focal)
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
    elif metric == "3DImageFlowGeodesic":
        rho = kwargs["rho"]
        w0 = s1;
        w1 = s2
        u0 = 0;
        u1 = 1  # interpolate_geodesics.get_distance()

        _, _, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)
        # TODO: Die geodätische Länge mit einbeziehen
        dist = np.sqrt((S * S) / 2 + (beta_end * beta_end) / 6)
    # elif metric == "3DImageFlowGeodesic":
    #    lookat_point = m(t, start=pos1, end=pos2)
    #    look_diff = lookat_point - look1
    #    rho = kwargs["rho"]
    #    w0 = s1;
    #    w1 = s2
    #    u0 = 0;
    #    u1 = np.linalg.norm(look_diff)
    #    _, _, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)
    #    dist = np.sqrt((S * S) / 2 + (beta_end * beta_end) / 6)
    else:
        raise ValueError(f"Unknown metric {metric}")

    return dist


def cam_from_params2(u: float, w: float,
                     R: np.ndarray, focal: float) -> dict:
    # , start: np.ndarray, end: np.ndarray) -> dict:
    up = R[:, 1]
    view = R[:, 2]
    scale = w

    lookat = m(u)
    print("lookat", lookat)
    pos = np.array(lookat) - np.array(scale * focal * view)

    cam = {
        "position": pos.tolist(),
        "view": view.tolist(),
        "up": up.tolist(),
        "frustum_scale": scale,
        "focal": focal
    }
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


def resize(cam, t):
    # pos = lookat - scale * focal * view
    # => scale = (pos - lookat)/(focal*view)
    coords = Vector(interpolate_geodesics.interpolate(t))
    pos = Vector(cam["position"])
    cam["frustum_scale"] = (coords - pos).length / cam["focal"]
    return cam


def interpolate_simple(start: dict, end: dict,
                       focal: float, metric: str,
                       n: int = 101, **kwargs) -> list:
    '''
    Simply interpolate between a start and end camera with n sample points
    according to the given metric.

    kwargs should contain the parameter rho if metric==3DImageFlow.
    '''
    if "3DImageFlowGeodesic" in metric:
        global interpolate_geodesics
        greedy = metric == "3DImageFlowGeodesicGreedy"
        min_greedy_point_difference = 2
        if "min_greedy_point_difference" in kwargs:
            min_greedy_point_difference = kwargs["min_greedy_point_difference"]
        interpolate_geodesics = InterpolateGeodesic(start_cam=start, end_cam=end, focal=focal, greedy_method=greedy,
                                                    min_greedy_point_difference=min_greedy_point_difference)
        if "geodesic_path_object" in kwargs and kwargs["geodesic_path_object"]:
            interpolate_geodesics.update_path_object(kwargs["geodesic_path_object"])
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

    if "generate_earth_file" in kwargs and kwargs["generate_earth_file"]:
        print("Exporting data...")
        earth = kwargs["move_around_object"]
        earth_position = earth.location
        earth_radius = (earth.matrix_world @ (earth.data.vertices[0].co - earth.location)).length
        export_geoposition_data(cams, n, metric, kwargs["file_path"], earth_center=earth_position,
                                earth_radius=earth_radius)  # [np.array(cam["position"]) for cam in cams])
        print("Exporting finished")
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

            cam = interpolate_t(s, focal, metric, start=segment_control_points[i], end=segment_control_points[i + 1],
                                **kwargs)
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

    if len(control_points) == 2:
        return interpolate_simple(control_points[0], control_points[1], focal, metric, n, **kwargs)

    normalized_knots = np.array(copy.deepcopy(knots))
    normalized_knots -= knots[0]
    normalized_knots = normalized_knots / (knots[-1] - knots[0])

    cams = None

    if method == "Linear":
        cams = []
        for i, knot in enumerate(knots[:-1]):
            nn = knots[i + 1] - knot
            cams.extend(interpolate_simple(control_points[i], control_points[i + 1], focal, metric, nn, **kwargs))
        return cams

    with Pool() as pool:
        if method == "CatmullRom":
            n_control_points = len(control_points)
            cams = pool.map(partial(interpolate_CatmullRom, control_points=control_points, knots=normalized_knots,
                                    focal=focal, metric=metric, **kwargs),
                            np.linspace(0, 1, n))

            for i in range(4):
                control_points, normalized_knots = disambiguate_spline(control_points, normalized_knots, cams)
                if n_control_points == len(control_points):
                    break
                n_control_points = len(control_points)
                cams = pool.map(partial(interpolate_CatmullRom, control_points=control_points, knots=normalized_knots,
                                        focal=focal, metric=metric, **kwargs),
                                np.linspace(0, 1, n))
        elif method == "Bezier":
            cams = pool.map(partial(interpolate_deCasteljau, control_points=control_points, focal=focal,
                                    metric=metric, **kwargs),
                            np.linspace(0, 1, n))
        else:
            raise ValueError(f"Method {method} unknown")

        pool.close()
        pool.join()

    return cams
