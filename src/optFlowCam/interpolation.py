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

"""
class InterpolateGoogleEarth:
    def __init__(self, start: ndarray, start_up: ndarray, end_up: ndarray, end: ndarray, earth: ndarray,
                 earth_radius: float, t_begin: float, t_end: float, focal: float, num_points: int):
        self.start = start
        self.start_up = start_up
        self.end = end
        self.end_up = end_up
        self.earth = earth
        self.earth_radius = earth_radius
        self.t_begin = t_begin
        self.t_end = t_end
        self.t_difference = self.t_end - self.t_begin
        self.position = start
        self.distance = self.calculate_distance_on_earth()
        self.move_matrix = self.calculate_move_matrix()
        self.moving_factor = 1
        self.moving_value = normalized(self.position - self.earth)
        self.focal = focal
        self.num_points = num_points

    def interpolate(self, t):
        percentage = (t - self.t_begin) / self.t_difference
        if 0 < percentage < 0.3:
            return self.move_out()
        elif 0.3 < percentage < 0.7:
            return self.move_to_end()
        else:
            return self.move_in()

    def cam_from_params(self, position: np.ndarray, view: np.ndarray, up: np.ndarray) -> dict:
        cam = {
            "position": position.tolist(),
            "view": view.tolist(),
            "up": up.tolist(),
            "frustum_scale": 1,
            "focal": self.focal
        }
        return cam

    def move_out(self):
        # cam rotation to earth
        # cam distance to earth increases
        # self.position += value
        self.position -= self.moving_value * self.moving_factor
        # in this method --> take initial up vector of end-cam
        return self.cam_from_params(self.position, self.moving_value * (-1), self.start_up)

    def move_to_end(self):
        # project position on earth
        # multiply (projected) position with matrix => multiply with distance
        # return new cam
        # up vector = rotated up vector with rot-matrix???
        pass

    def move_in(self):
        # cam rotation to earth
        # cam distance to earth decreases
        # self.position += value
        self.position += self.moving_value * self.moving_factor
        # in this method --> take initial up vector of start-cam
        return self.cam_from_params(self.position, self.moving_value * (-1), self.end_up)

    def calculate_distance_on_earth(self):
        p1 = self.project_point_on_earth(self.start)
        p2 = self.project_point_on_earth(self.end)
        return self.earth_distance_between(p1, p2)

    def project_point_on_earth(self, end):
        return self.earth + normalized(end - self.earth) * self.earth_radius

    def earth_distance_between(self, p1, p2):
        # calculate plane of p1, p2 and self.earth
        # calculate distance
        # = Bogenlänge des Winkels zwischen Vektoren
        # cos(a) = p1*p2 / (|p1| * |p2|) => a = cos^-1( p1*p2 / (|p1| * |p2|) )
        return math.acos(p1 * p2 / (np.abs(p1) * np.abs(p2))) * self.earth_radius

    def calculate_move_matrix(self):
        # calculate plane of p1, p2 and self.earth
        # --p-r-o-j-e-c-t--p-o-i-n-t-s--i-n-t-o--p-l-a-n-e--
        # divide dist by self.t_difference => get vector how far to move in one step
        # transform vector back => get matrix => return
        pass
"""


def export_geoposition_data(cams, num_frames, metric, earth_center=Vector((0, 0, 0)), earth_radius=10):
    if num_frames != len(cams):
        num_frames = len(cams)
    studio = GoogleEarthStudio(num_frames, metric, 24, earth_center, earth_radius)
    for idx, cam in enumerate(cams):
        studio.append_frame(cam, idx)

    studio.createAnimation(f"C:\\Users\\nonoa\\Desktop\\renderings\\{metric}.esp")


def new_face(face, insert_idx):
    face_0 = (face[0], face[1], insert_idx)
    face_1 = (face[0], face[2], insert_idx)
    face_2 = (face[1], face[2], insert_idx)
    return face_0, face_1, face_2


class InterpolateGeodesic:
    def __init__(self, start_cam, end_cam, focal):
        start_eyepoint = start_cam["position"]
        start_view_direction = start_cam["view"]
        end_eyepoint = end_cam["position"]
        end_view_direction = end_cam["view"]

        context = bpy.context
        vl = context.view_layer
        print("-----Ausgangspunkt + Richtung----------")
        print(start_eyepoint, start_view_direction)
        print("-----Endpunktpunkt + Richtung----------")
        print(end_eyepoint, end_view_direction)
        obj, start_face_idx, start_loc = self.raycast(start=start_eyepoint, direction=start_view_direction)
        obj2, end_face_idx, end_loc = self.raycast(start=end_eyepoint, direction=end_view_direction)
        print("-----Startposition auf dem Mesh----------")
        print(start_loc)
        print("-----Endposition auf dem Mesh----------")
        print(end_loc)
        if obj and obj == obj2 and obj.type == "MESH":
            self.mesh = obj.evaluated_get(vl.depsgraph).to_mesh()
            self.obj = obj
            # [(bpy.data.objects['Sphere'].matrix_world @ i.co) for i in bpy.data.objects['Sphere'].data.vertices]
        else:
            raise ValueError("Start-/Endkamera müssen auf dasselbe Objekt gerichtet sein")
        self.distance = None
        self.path = []
        faces = [i.vertices for i in self.mesh.polygons]
        start_face = faces.pop(start_face_idx)
        end_face = faces.pop(end_face_idx)
        faces += new_face(start_face, len(self.mesh.vertices))
        faces += new_face(end_face, len(self.mesh.vertices) + 1)
        self.geodesic_calc = geodesic.PyGeodesicAlgorithmExact(
            [self.obj.matrix_world @ i.co for i in self.mesh.vertices] + [start_loc, end_loc], faces)
        # [i for i in bpy.data.meshes["Icosphere"].polygons[0].vertices] )# self.mesh.polygons)
        self.calculate(start_cam, end_cam, 0, 1, len(self.mesh.vertices), focal)

    def calculate(self, start, end, start_t, end_t, idx, focal):
        """
        cam = {
        "position": pos.tolist(),
        "view": view.tolist(),
        "up": up.tolist(),
        "frustum_scale": scale,
        "focal": focal
        }
        """
        assert start_t < end_t
        """
        start_eyepoint = start["position"]
        start_view_direction = start["view"]
        end_eyepoint = end["position"]
        end_view_direction = end["view"]
        _, start_face_idx, start_loc = self.raycast(start_eyepoint, start_view_direction)
        start_idx = self.get_idx(start_face_idx, start_loc)
        _, end_face_idx, end_loc = self.raycast(end_eyepoint, end_view_direction)
        end_idx = self.get_idx(end_face_idx, end_loc)
        path = self.find_geodesic_path_between(start_idx, end_idx)
        """
        ### Idee: Pfad durch BSpline der Punkte interpolieren lassen
        path = self.find_geodesic_path_between(idx, idx + 1)

        self.mix_path_with_time(path, start_t, end_t)
        # self.mix_advanced_path_with_time(path, start, start_t, end, end_t, focal)

    def get_distance(self):
        return self.distance

    def interpolate(self, t):
        print(t)
        # assert self.path[0][1] <= t <= self.path[-1][1] , f"{t} is not in {self.path[0][1]} - {self.path[-1][1]}"
        idx = self.find_t_idx(t)  #
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
        # return last_element[0] + (next_element[1]-last_element[0])*((t-last_t) / t_diff)

    def raycast(self, start, direction) -> tuple[Any, Any, Any]:
        context = bpy.context
        vl = context.view_layer
        scene = context.scene

        hit, loc, norm_0, face_idx, obj_0, mw_0 = scene.ray_cast(vl.depsgraph, start, direction)
        assert hit, "Kameras müssen auf ein Objekt gerichtet sein"
        return obj_0, face_idx, loc

    def get_idx(self, face_idx, loc):
        faces = self.mesh.polygons[face_idx]
        nearest_vert = None
        for v in faces.vertices:
            vert = self.mesh.vertices[v]
            if not nearest_vert or nearest_vert[0] > (vert.co - loc).length:
                nearest_vert = ((vert.co - loc).length, vert)
        return nearest_vert[1].index

    def find_geodesic_path_between(self, start_idx, end_idx):
        distance, path = self.geodesic_calc.geodesicDistance(end_idx, start_idx)

        # path = [np.array(Vector(i) @ self.obj.matrix_world) for i in path]
        summed_path = 0
        for idx in range(1, len(path)):
            summed_path += np.linalg.norm(path[idx] - path[idx - 1])

        self.distance = summed_path
        print("From", start_idx)
        print("to", end_idx)
        print("Distances", distance, "Summed distance: ", summed_path)
        # print("Path", path)
        """
        TODO: add starting POV and ending POV to path
            look1 = pos1 + s1 * focal * view1
            look2 = pos2 + s2 * focal * view2
        """
        return path

    def mix_path_with_time(self, path, start_t, end_t):
        t_diff = end_t - start_t
        self.path.append((path[0], start_t))
        for idx in range(1, len(path) - 1):
            current_dist = np.linalg.norm(path[idx] - path[idx - 1])
            self.path.append((path[idx], self.path[idx - 1][1] + t_diff * current_dist / self.distance))
        self.path.append((path[-1], end_t))
        # print(self.path)
        # self.path = list(zip(path, np.linspace(start_t, end_t, len(path))))

    def find_t_idx(self, t):
        return bisect.bisect_left(self.path, t, key=lambda x: x[1])

    def mix_advanced_path_with_time(self, path, start, start_t, end, end_t, focal):
        # look1 = pos1 + s1 * focal * view1
        pos1, view1, up1, right1, s1 = unpack_camera(start)
        look1 = pos1 + s1 * focal * view1
        start_diff = np.linalg.norm(path[0] - look1)
        pos2, view2, up2, right2, s2 = unpack_camera(end)
        look2 = pos2 + s2 * focal * view2
        end_diff = np.linalg.norm(path[-1] - look2)

        self.distance = self.distance + start_diff + end_diff
        start_part = start_diff / self.distance
        end_part = end_diff / self.distance
        t_after_start_part = start_t + (end_t - start_t) * start_part
        t_before_end_part = end_t - (end_t - start_t) * end_part
        self.path = list(zip(np.vstack((look1, path, look2)),
                             [start_t] + list(np.linspace(t_after_start_part, t_before_end_part, len(path))) + [end_t]))
        # print(self.path)

    def create_path_object(self, collection_name):
        # from ..objects.path_geometry import add_path_object, update_path
        path_object = add_path_object(2, collection_name, "geodesic_path")
        update_path(path_object, [{"position": i[0]} for i in self.path], 'NURBS')


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

    elif metric == "3DImageFlowGeodesic":
        rho = kwargs["rho"]

        w0 = s1
        w1 = s2
        u0 = 0
        u1 = 1
        # u1 = interpolate_geodesics.get_distance()  # np.linalg.norm(look_diff)
        # look_diff_n = np.zeros(3) if u1 < 1e-14 else normalized(look_diff)
        u, w = get_zoom_pan_parameter(t, w0, w1, u0, u1, rho)

        # look_at_point = m(u)
        # look_diff_n = interpolate_geodesics.get_distance()
        # cam = cam_from_params2(u, w, R_f(t), focal, look_at_point, look_diff_n)
        cam = cam_from_params2(u, w, R_f(t), focal)
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
        w0 = s1; w1 = s2
        u0 = 0;  u1 = np.linalg.norm(look_diff)

        _, _, S = get_zoom_pan_parameter_functions(w0, w1, u0, u1, rho)

        dist = np.sqrt((S * S) / 2 + (beta_end * beta_end) / 6)
    elif metric == "3DImageFlowGeodesic":
        rho = kwargs["rho"]
        w0 = s1;
        w1 = s2
        u0 = 0;
        u1 = 1 # interpolate_geodesics.get_distance()

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
    pos = lookat - scale * focal * view

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
    cam["frustum_scale"] = (coords-pos).length / cam["focal"]
    return cam


def interpolate_simple(start: dict, end: dict,
                       focal: float, metric: str,
                       n: int = 101, **kwargs) -> list:
    '''
    Simply interpolate between a start and end camera with n sample points
    according to the given metric.

    kwargs should contain the parameter rho if metric==3DImageFlow.
    '''
    if metric == "3DImageFlowGeodesic":
        global interpolate_geodesics
        interpolate_geodesics = InterpolateGeodesic(start_cam=start, end_cam=end, focal=focal)
        if "collection_name" in kwargs and kwargs["collection_name"]:
            interpolate_geodesics.create_path_object(kwargs["collection_name"])
        start_cam = clone_cam(start)
        resize(start_cam, 0)
        end_cam = clone_cam(end)
        resize(end_cam, 1)
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
        export_geoposition_data(cams, n, metric)  # [np.array(cam["position"]) for cam in cams])
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
    if (metric == "3DImageFlow" or metric == "3DImageFlowGeodesic") and not "rho" in kwargs:
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
