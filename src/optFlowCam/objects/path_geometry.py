import bpy
from mathutils import Matrix

def add_path_object(n_points, collection_name, curve_name='CameraCurve'):
    '''
    Adds a new curve object to the scene
    '''

    # create the curve data block
    curve_data = bpy.data.curves.new('Curve', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 2

    # create object
    curve_obj = bpy.data.objects.new(curve_name, curve_data)
    curve_obj.matrix_world = Matrix.Identity(4)

    # map coords to spline
    polyline = curve_data.splines.new('POLY')
    polyline.points.add(n_points - 1)

    bpy.data.collections[collection_name].objects.link(curve_obj)

    return curve_obj


def update_path(path_obj, coords, type="POLY"):
    '''
    Updates the vertices of an existing path object.
    '''

    # the object has no spline data, not enough or too many vertices
    if len(path_obj.data.splines) == 0 or \
            len(path_obj.data.splines[0].points) != len(coords):

        path_obj.data.splines.clear()
        polyline = path_obj.data.splines.new(type)
        polyline.points.add(len(coords) - 1)

    else:
        polyline = path_obj.data.splines[0]

    # update curve vertices
    for i, coord in enumerate(coords):
        x, y, z = coord["position"]
        polyline.points[i].co = (x, y, z, 1)
