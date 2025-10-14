import math, json, numpy as np
from ..math import make_lookAt_matrix
from mathutils import Vector, Matrix
from math import sin,cos,atan2,acos,asin

template = """{
  "modelVersion": 18,
  "settings": {
    "name": "{name}",
    "frameRate": {frame_rate},
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "duration": {frames},
    "timeFormat": "frames"
  },
  "scenes": [
    {
      "animationModel": {
        "roving": false,
        "logarithmic": false,
        "groupedPosition": true
      },
      "duration": {frames},
      "attributes": [
        {
          "type": "cameraGroup",
          "inTimeline": true,
          "attributes": [
            {
              "type": "cameraPositionGroup",
              "inTimeline": true,
              "attributes": [
                {
                  "type": "position",
                  "inTimeline": true,
                  "attributes": [
                    {
                      "type": "longitude",
                      "value": {
                        "relative": 0.21857031742092137
                      },
                      "keyframes": [],
                      "inTimeline": true
                    },
                    {
                      "type": "latitude",
                      "value": {
                        "relative": 0.6073165784530837
                      },
                      "keyframes": [],
                      "inTimeline": true
                    },
                    {
                      "type": "altitude",
                      "value": {
                        "maxValueRange": 65117481,
                        "minValueRange": -500,
                        "relative": 0.2484709838881655,
                        "logarithmic": false
                      },
                      "keyframes": [],
                      "inTimeline": true
                    }
                  ]
                }
              ]
            },
            {
              "type": "cameraTargetEffect",
              "attributes": [
                {
                  "type": "enabled",
                  "value": {}
                },
                {
                  "type": "poi",
                  "attributes": [
                    {
                      "type": "longitudePOI",
                      "value": {}
                    },
                    {
                      "type": "latitudePOI",
                      "value": {}
                    },
                    {
                      "type": "altitudePOI",
                      "value": {
                        "maxValueRange": 65117481,
                        "minValueRange": -500,
                        "logarithmic": false
                      }
                    }
                  ]
                },
                {
                  "type": "influence",
                  "value": {}
                }
              ]
            },
            {
              "type": "cameraRotationGroup",
              "inTimeline": true,
              "attributes": [
                {
                  "type": "rotationX",
                  "value": {
                    "relative": 0.9319780806323318
                  },
                  "keyframes": [],
                  "inTimeline": true
                },
                {
                  "type": "rotationY",
                  "value": {
                    "relative": 0.06555555555555556
                  },
                  "keyframes": [],
                  "inTimeline": true
                },
                {
                  "type": "rotationZ",
                  "value": {}
                }
              ]
            },
            {
              "type": "cameraLensGroup",
              "attributes": [
                {
                  "type": "fov",
                  "value": {}
                },
                {
                  "type": "exposure",
                  "value": {}
                },
                {
                  "type": "aperture",
                  "value": {}
                },
                {
                  "type": "minFocusLength",
                  "value": {}
                }
              ]
            }
          ]
        },
        {
          "type": "environmentGroup",
          "attributes": [
            {
              "type": "sunGroup",
              "attributes": [
                {
                  "type": "sunVisibility",
                  "value": {}
                },
                {
                  "type": "worldTime",
                  "value": {
                    "relative": 0.5,
                    "minValueRange": 1754381663593,
                    "maxValueRange": 1754554463593
                  }
                }
              ]
            },
            {
              "type": "cloudGroup",
              "attributes": [
                {
                  "type": "cloudVisibility",
                  "value": {}
                },
                {
                  "type": "cloudopacity",
                  "value": {}
                },
                {
                  "type": "cloudheight",
                  "value": {}
                },
                {
                  "type": "clouddate",
                  "value": {
                    "relative": 0.9545454545454546,
                    "minValueRange": 1754380800000,
                    "maxValueRange": 1754460000000
                  }
                }
              ]
            },
            {
              "type": "starsPlanetsGroup",
              "attributes": [
                {
                  "type": "starsEnabled",
                  "value": {}
                }
              ]
            },
            {
              "type": "seawaterGroup",
              "attributes": [
                {
                  "type": "seawater",
                  "value": {}
                },
                {
                  "type": "influence",
                  "value": {
                    "relative": 1
                  }
                }
              ]
            },
            {
              "type": "buildingsEnabled",
              "value": {}
            }
          ]
        }
      ],
      "cameraExport": {
        "logarithmic": false,
        "modelVersion": 2
      }
    }
  ],
  "playbackManager": {
    "range": {
      "start": 0,
      "end": {frames}
    }
  }
}"""


def get_height(position, center, radius):
    distance = (position - center).length
    """
    radius/distance = 6371_000 / real_distance
    ======>
    real_distance = 6371_000 * distance/radius
    """
    # Distanz des Erdmittelpunkts zur Kamera "in echt"
    real_distance = 6371_000 * distance / radius
    return real_distance - 6371_000  # nur Distanz bis zur Erdoberfläche


def otherATan2(x, y):
    if x > 0:
        return math.atan(y / x)
    if x == 0:
        math.pi / 2 * (-1 * y < 0)
    if x < 0 and y >= 0:
        return math.atan(y / x) + math.pi
    if x < 0 and y < 0:
        return math.atan(y / x) - math.pi
    return 0


def map_to_plane(position, earth_center):
    # https://en.wikipedia.org/wiki/UV_mapping
    d = (position - earth_center).normalized()
    # if y = up-vector
    # u = 0.5 + (np.arctan2(d[2], d[0])) / (2 * math.pi)
    # v = 0.5 + np.arcsin(d[1]) / math.pi
    # if z = up-vector
    x, y, z = d
    """
    u = 0.5 + (np.arctan2(d[1], d[0])) / (2 * math.pi)
    v = 0.5 + np.arcsin(d[2]) / math.pi
    """
    """
    lat = math.atan2(z, math.hypot(x, y))  # [-pi/2, pi/2]
    long = math.atan2(y, x)
    """
    # long, lat = math.acos(z), otherATan2(x,y)
    lat, long = math.pi / 2 - math.acos(z), otherATan2(x, y)
    return long, lat


def map_uv_to_longlat(u, v):
    # longitude = (u * 360) - 180
    # latitude = (v * 180) - 90
    return math.degrees(u), math.degrees(v)


def extract_2d_position(position, earth_center, earth_radius):
    return *map_uv_to_longlat(*map_to_plane(position, earth_center)), get_height(position, earth_center, earth_radius)


def project_point_into_ebene(point, vec, normal):
    return point + (normal @ (vec - point)) * normal


def theiselsIdee(pos, dir, earth_center, earth_radius):
    """
    1. Schnittpunkt der Sichtachse auf der Erde finden
    hh := Multiply( Transpose(E+t*A),E+t*A)-r^2;

    #solve(hh=0,t);

    dd :=
    -Multiply( Transpose(A),E)
    + sqrt(
    + r^2*Multiply( Transpose(A),A)
    -Multiply( Transpose(A&xE),A&xE)
    );
    simplify(eval(hh,t=dd));

    M := simplify(E+dd*A);

    2. Spiegel Matrix aufstellen
    MM_mirror := Matrix([
    [-1,0,0],
    [0,1,0],
    [0,0,-1]]);

###
    3. Skalierung berechnen
    s_pio := -dd/f;
    M_pio := M;
    RM_pio := Multiply( RM, MM_mirror);

###

A_pio := Vector([ RM_pio[1,3],RM_pio[2,3],RM_pio[3,3] ]);
E_pio := M_pio - f*s_pio*A_pio;

Longitude_pio := simplify(arctan( E_pio[2],E_pio[1]));
Latitude_pio  := arctan( E_pio[3] , E_pio[1]/cos(Longitude_pio) );
Altitude_pio := sqrt(Multiply( Transpose(E_pio),E_pio)) - r;

RMO_pio := Matrix(3, 3, [
[-sin(Longitude_pio), -sin(Latitude_pio)*cos(Longitude_pio), cos(Longitude_pio)*cos(Latitude_pio)],
[cos(Longitude_pio), -sin(Latitude_pio)*sin(Longitude_pio), sin(Longitude_pio)*cos(Latitude_pio)],
[0, cos(Latitude_pio), sin(Latitude_pio)]]);


RM1_pio := Multiply( Transpose(RMO_pio) , Multiply( RM_pio, MM_mirror));
== Weltmatrix ???

#Tilt_pio := arccos(RM1_pio[3,3]);
Tilt_pio := arctan( sqrt(RM1_pio[1,3]^2 + RM1_pio[2,3]^2) , RM1_pio[3,3] );
Roll_pio := arctan( -RM1[3,1],RM1[3,2]);
Pan_pio := arctan(-RM1[1,3],-RM1[2,3]);


    """


def camMatrixByPosition(lat, long, alt, pan, tilt, roll, r=6371, focal=2):
    from math import sin, cos, radians
    lat, long, pan, tilt, roll = [radians(i) for i in [lat, long, pan, tilt, roll]]
    """
    A0 = Vector([cos(long) * cos(lat),
                 sin(long) * cos(lat),
                 sin(lat)
                 ])
    E = (alt + r) * A0
    HY = Vector([0, 0, 1])
    #
    R0 = (HY.cross(A0)).normalized()
    #
    U0 = A0.cross(R0)
    #
    RM0 = Matrix([
        [R0[0], U0[0], A0[0]],
        [R0[1], U0[1], A0[1]],
        [R0[2], U0[2], A0[2]]])
    #
    RM_Pan = Matrix([
        [cos(pan), sin(pan), 0],
        [-sin(pan), cos(pan), 0],
        [0, 0, 1]])
    #
    RM_Tilt = Matrix([
        [1, 0, 0],
        [0, cos(tilt), -sin(tilt)],
        [0, sin(tilt), cos(tilt)]])
    #
    RM_Roll = Matrix([
        [cos(roll), sin(roll), 0],
        [-sin(roll), cos(roll), 0],
        [0, 0, 1]])
    #
    RM1 = ((RM_Pan @ RM_Tilt) @ RM_Roll)
    #
    RM = (RM0 @ RM1)
    ## das hier war nicht mehr drinne
    MM_mirror = Matrix([
        [-1, 0, 0],
        [0, 1, 0],
        [0, 0, -1]])
    #
    RM_pio = RM @ MM_mirror
    # RM1_pio := Multiply( Transpose(RMO_pio) , Multiply( RM_pio, MM_mirror));
    # RM1_pio = RMO_pio.transposed() @ Multiply(RM_pio, MM_mirror));
    ## bis hier
    """
    A0 = np.array([cos(long) * cos(lat),
                   sin(long) * cos(lat),
                   sin(lat)
                   ])

    # radius/distance           = 6371_000 / real_distance
    # earth_radius/scale_factor = 6371_000 / (alt+6371_000)
    # => scale_factor = earth_radius*(alt+6371_000)/6371_000
    # before: E = Vector((alt+r) * A0)
    E = Vector((r * (alt + 6371_000) / 6371_000) * A0)
    HY = np.array([0, 0, 1])
    R0 = np.cross(HY, A0)
    R0 = R0 / np.linalg.norm(R0)
    #
    U0 = np.cross(A0, R0)
    #
    RM0 = np.array([
        [R0[0], U0[0], A0[0]],
        [R0[1], U0[1], A0[1]],
        [R0[2], U0[2], A0[2]]
    ])
    RM_Pan = np.array([
        [cos(pan), sin(pan), 0],
        [-sin(pan), cos(pan), 0],
        [0, 0, 1]])
    #
    RM_Tilt = np.array([
        [1, 0, 0],
        [0, cos(tilt), -sin(tilt)],
        [0, sin(tilt), cos(tilt)]])
    #
    RM_Roll = np.array([
        [cos(roll), sin(roll), 0],
        [-sin(roll), cos(roll), 0],
        [0, 0, 1]])
    #
    RM1 = ((RM_Pan @ RM_Tilt) @ RM_Roll)
    #
    RM = (RM0 @ RM1)
    #print(np.cross(RM[:, 1], RM[:, 2]))
    up = Vector(RM[:, 1])
    forward = -Vector(RM[:, 2])
    #print(RM)
    # return RM_pio, E
    return make_lookAt_matrix(E, forward, up)# , E, forward, up
    # mat,pos = camMatrixByPosition(0,45,20,20,11,23,2,2)
    # mat= camMatrixByPosition(0,0,20,180,15,180,2,2)


def extract_rotation(cam, earth_position=np.array((0, 0, 0)), earth_radius=10):
    """
    Method to extract the rotation of the camera in Google Earth Studio Format
    """
    """
        cam = {
            "position": pos.tolist(),
            "view": view.tolist(),
            "up": up.tolist(),
            "frustum_scale": scale,
            "focal": focal
        }
        """
    # forward = -forward
    # forward = -np.array(cam["view"])
    forward = -np.array(cam["view"])
    up = np.array(cam["up"])
    pos = np.array(cam["position"]) - earth_position
    # RIGHT = np.cross(up, forward)
    #
    # np.array([np.cross(RM[:, 1], RM[:, 2]), RM[:, 1], RM[:, 2]]).T
    RM = np.array([np.cross(up, forward), up, forward]).T
    print(RM)
    E_pio = pos
    """
    Longitude_pio := simplify(arctan( E_pio[2],E_pio[1]));
    Latitude_pio  := arctan( E_pio[3] , E_pio[1]/cos(Longitude_pio) );
    Altitude_pio := sqrt(Multiply( Transpose(E_pio),E_pio)) - r;
    
    RMO_pio := Matrix(3, 3, [
    [-sin(Longitude_pio), -sin(Latitude_pio)*cos(Longitude_pio), cos(Longitude_pio)*cos(Latitude_pio)], 
    [cos(Longitude_pio), -sin(Latitude_pio)*sin(Longitude_pio), sin(Longitude_pio)*cos(Latitude_pio)], 
    [0, cos(Latitude_pio), sin(Latitude_pio)]]);
    
    
    RM1_pio := Multiply( Transpose(RMO_pio) , Multiply( RM_pio, MM_mirror));
    
    
    #Tilt_pio := arccos(RM1_pio[3,3]);
    Tilt_pio := arctan( sqrt(RM1_pio[1,3]^2 + RM1_pio[2,3]^2) , RM1_pio[3,3] );
    Roll_pio := arctan( -RM1[3,1],RM1[3,2]);
    Pan_pio := arctan(-RM1[1,3],-RM1[2,3]);
    """
    longitude = math.atan2(E_pio[1], E_pio[0])
    latitude = math.atan2(E_pio[2], E_pio[0] / cos(longitude))
    altitude = Vector(E_pio).length - earth_radius  # for resulting file ist must be scaled to earth scale
    RMO_pio = np.array([
        [-sin(longitude), -sin(latitude) * cos(longitude), cos(longitude) * cos(latitude)],
        [cos(longitude), -sin(latitude) * sin(longitude), sin(longitude) * cos(latitude)],
        [0, cos(latitude), sin(latitude)]])
    #
    RM1_pio = RMO_pio.T @ RM
    # RM = (RM0 @ RM1)
    # => RM1 = RM0 ^ -1 @ RM = RM0^T @ RM
    Tilt_pio = math.atan2(math.sqrt(RM1_pio[0, 2] ** 2 + RM1_pio[1, 2] ** 2), RM1_pio[2, 2])
    Roll_pio = math.atan2(-RM1_pio[2, 0], RM1_pio[2, 1])
    Pan_pio = math.atan2(-RM1_pio[0, 2], -RM1_pio[1, 2])
    return Pan_pio, Tilt_pio, Roll_pio


def extract_data_from_cam(cam, earth_center, earth_radius):
    """
    cam = {
        "position": pos.tolist(),
        "view": view.tolist(),
        "up": up.tolist(),
        "frustum_scale": scale,
        "focal": focal
    }
    """
    position = Vector(cam["position"])
    long, lat, height = extract_2d_position(position, earth_center, earth_radius)
    rotX, rotY, rotZ = extract_rotation(cam, earth_center, earth_radius)
    return long, lat, height, rotX, rotY, rotZ


def get_relative_value(value, min_value, max_value):
    return (value - min_value) / (max_value - min_value)


class GoogleEarthStudio:
    def __init__(self, frames=100, name="GoogleEarth", frame_rate=24, earth_center=Vector([0, 0, 0]), earth_radius=10):
        self.frames = frames
        self.name = name
        self.frame_rate = frame_rate
        self.earth_center = earth_center
        self.earth_radius = earth_radius
        self.longitudes = []
        self.latitudes = []
        self.distances = []
        self.rotationsX = []
        self.rotationsY = []
        self.rotationsZ = []

    def createAnimation(self, path):
        json_data = json.loads(
            template.replace("{frames}", str(self.frames-1)).replace("{frame_rate}", str(self.frame_rate)).replace(
                "{name}", self.name))
        positions = json_data["scenes"][0]["attributes"][0]["attributes"][0]["attributes"][0]["attributes"]
        rotations = json_data["scenes"][0]["attributes"][0]["attributes"][2]["attributes"]

        positions[0]["keyframes"] = self.longitudes
        positions[1]["keyframes"] = self.latitudes
        positions[2]["keyframes"] = self.distances
        rotations[0]["keyframes"] = self.rotationsX
        rotations[1]["keyframes"] = self.rotationsY
        rotations[2]["keyframes"] = self.rotationsZ

        with open(path, "w", encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False)

    def append_frame(self, cam, frame):
        long, lat, dist, rotX, rotY, rotZ = extract_data_from_cam(cam, self.earth_center, self.earth_radius)
        time = frame / self.frames
        self.longitudes.append({"time": time, "value": get_relative_value(long, -180, 180)})  # -180 bis +180
        self.latitudes.append({"time": time, "value": get_relative_value(lat, -90, 90)})  # -90 bis +90
        self.distances.append({"time": time, "value": get_relative_value(dist, -500, 65117481)})  # -500 bis 65117481
        self.rotationsX.append({"time": time, "value": get_relative_value(rotX, 0,
                                                                          2 * math.pi)})  # ??? -359,9° bis -359,9° ?? vlt auch nur 0-359,9°
        self.rotationsY.append({"time": time, "value": get_relative_value(rotY, 0, math.pi)})  # 0° bis 180° || 0 - PI
        self.rotationsZ.append({"time": time, "value": get_relative_value(rotZ, 0, 2*math.pi)})  # 0° bis 180° || 0 - PI
