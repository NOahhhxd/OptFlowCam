import math, json, numpy as np
from ..math import make_lookAt_matrix
from mathutils import Vector, Matrix

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
    return real_distance - 6371_000 # nur Distanz bis zur Erdoberfläche



def map_to_plane(position, earth_center):
    # https://en.wikipedia.org/wiki/UV_mapping
    d = (position - earth_center).normalized()
    # if y = up-vector
    # u = 0.5 + (np.arctan2(d[2], d[0])) / (2 * math.pi)
    # v = 0.5 + np.arcsin(d[1]) / math.pi
    # if z = up-vector
    x,y,z = d
    """
    u = 0.5 + (np.arctan2(d[1], d[0])) / (2 * math.pi)
    v = 0.5 + np.arcsin(d[2]) / math.pi
    """
    """
    lat = math.atan2(z, math.hypot(x, y))  # [-pi/2, pi/2]
    long = math.atan2(y, x)
    """
    long, lat = math.acos(z), otherATan2(x,y)
    return long, lat


def map_uv_to_longlat(u, v):
    # longitude = (u * 360) - 180
    # latitude = (v * 180) - 90
    return 90-math.degrees(u), math.degrees(v)

def extract_2d_position(position, earth_center, earth_radius):
    return *map_uv_to_longlat(*map_to_plane(position, earth_center)), get_height(position, earth_center, earth_radius)

def otherATan2(x,y):
    if x > 0:
        return math.atan(y/x)
    if x == 0:
        math.pi/2*(-1*y<0)
    if x < 0 and y >= 0:
        return math.atan(y/x) + math.pi
    if x < 0 and y < 0:
        return math.atan(y/x) - math.pi
    return 0


def extract_rotation(pos, forward, up, earth):
    """
    # 1. get world_matrix out of forward and up
    matrix = make_lookAt_matrix(pos, forward, up)
    # 2. multiplay earth-point with this matrix
    rotated_earth_pos = matrix@earth
    only_x_and_y = Vector([rotated_earth_pos.x, rotated_earth_pos.y])
    rot_z = only_x_and_y.angle_signed(Vector([0,1]))
    rotated_earth_pos.rotate(Matrix.Rotation(rot_z, 4, 'Z'))
    only_y_z = Vector([rotated_earth_pos.y, rotated_earth_pos.z])
    rot_x = only_y_z.angle_signed(Vector([0,1]))

    # https://space.stackexchange.com/questions/59489/determine-yaw-pitch-roll-from-two-vectors
    #rot_y = math.atan2(x, z)
    #rot_x = math.atan2(y, math.hypot(x, z))
    # rot_z = math.atan2(y, x)
    # rot_x = math.atan2(math.hypot(x, y), z)
    # rot_y = math.atan2(math.hypot(y, x), z)
    # -, weil es bisher besser passt
    # z, weil das die View-Achse der Kamera ist => das ist die XRotation laut Google-Earth
    #
    # return -rot_z, rot_y
    return rot_z,rot_x
    """
    matrix = make_lookAt_matrix(pos, forward, up)
    # 2. multiplay earth-point with this matrix
    rotated_earth_pos = matrix.inverted() @ earth
    # pos_to_earth = (earth-pos).normalized()
    # -z = vorne   y = oben   x = rechts
    x, z, y = rotated_earth_pos.normalized()
    """
    u = 0.5 + (np.arctan2(d[1], d[0])) / (2 * math.pi)
    v = 0.5 + np.arcsin(d[2]) / math.pi
    """
    """
    lat = math.atan2(z, math.hypot(x, y))  # [-pi/2, pi/2]
    long = math.atan2(y, x)
    """
    long, lat = math.pi/2-math.acos(z), otherATan2(x, y)
    return long, lat


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
    view = Vector(cam["view"])
    up = Vector(cam["up"])
    long, lat, height = extract_2d_position(position, earth_center, earth_radius)
    rotX, rotY = extract_rotation(position, view, up, earth_center)
    return long,lat,height,rotX,rotY


def get_relative_value(value, min_value, max_value):
    return (value - min_value) / (max_value - min_value)


class GoogleEarthStudio:
    def __init__(self, frames=100, name="GoogleEarth", frame_rate=24, earth_center=Vector([0,0,0]), earth_radius=10):
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

    def createAnimation(self, path):
        json_data = json.loads(template.replace("{frames}", str(self.frames)).replace("{frame_rate}", str(self.frame_rate)).replace("{name}", self.name))
        positions = json_data["scenes"][0]["attributes"][0]["attributes"][0]["attributes"][0]["attributes"]
        rotations = json_data["scenes"][0]["attributes"][0]["attributes"][2]["attributes"]

        positions[0]["keyframes"] = self.longitudes
        positions[1]["keyframes"] = self.latitudes
        positions[2]["keyframes"] = self.distances
        rotations[0]["keyframes"] = self.rotationsX
        rotations[1]["keyframes"] = self.rotationsY

        with open(path, "w", encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False)

    def append_frame(self, cam, frame):
        long, lat, dist, rotX, rotY = extract_data_from_cam(cam, self.earth_center, self.earth_radius)
        time = frame/self.frames
        self.longitudes.append({"time":time, "value":get_relative_value(long, -180, 180)}) # -180 bis +180
        self.latitudes.append({"time":time, "value":get_relative_value(lat, -90, 90)}) # -90 bis +90
        self.distances.append({"time":time, "value":get_relative_value(dist, -500, 65117481)}) # -500 bis 65117481
        self.rotationsX.append({"time":time, "value":get_relative_value(rotX, -math.pi,math.pi)}) # ??? -359,9° bis -359,9° ?? vlt auch nur 0-359,9°
        self.rotationsY.append({"time":time, "value":get_relative_value(rotY, 0,math.pi/2)}) # 0° bis 180° || 0 - PI


