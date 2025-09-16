import bpy
from .ui import keyframe_list

# ------------------------------------------------------------------------------

class OFC_PG_OptimalPathInitialization(bpy.types.PropertyGroup):
    def camera_poll(self, object):
        return object.type == 'CAMERA'
    
    interpolation_methods = [
        #(identifier, name, description, icon, number)
        ("CatmullRom", "Catmull-Rom", "Interpolate with Catmull Rom spline (recommended)", "RNDCURVE", 0),
        ("Bezier", "Bezier", "Create Bezier spline. WARNING! This does only interpolate the first and last keyframe!", "IPO_BEZIER", 1),
        ("Linear", "Linear", "Interpolate as series of linear parts", "IPO_LINEAR", 2),
    ]

    interpolation_metrics = [
        #(identifier, name, description, icon, number)
        ("3DImageFlow", "3DImageFlow", "Optimal spline based on minimizing 3D image flow in camera frustum", "MESH_CUBE", 0),
        ("LookatLinear", "Look-at Interpolation", "Spline based on linearly interpolating the lookat point, position and up vector of the camera", "PARTICLE_TIP", 1),
        ("TransformationsLinear", "Transformation Interpolation", "Spline base on linearly interpolating position, rotation and look-at distance", "CON_ROTLIMIT", 2),
        ("3DImageFlowGeodesic","3DImageFlow with geodesic look-at path", "Optimal spline based on minimizing 3D image flow in camera frustum with geodesic look-at path", "MESH_CUBE", 3),
    ]

    parametrization_options = [
        #(identifier, name, description, icon, number)
        ("Centripetal", "Centripetal", "Distribution proportional to square root of distance  of cameras (recommended, depends on metric)", "DRIVER_DISTANCE", 0),
        ("Chordal", "Chordal", "Distribution proportional to distance of cameras (depends on metric)", "FIXED_SIZE", 1),
        ("Uniform", "Uniform", "Distribution equally spaced between the start and end frame", "CURVE_PATH", 2),
    ]

    # this is added during registration because Blender cannot find
    # the type OFC_PG_KeyframeItem otherwise
    #keyframes: bpy.props.CollectionProperty(
    #    type= keyframe_list.OFC_PG_KeyframeItem)

    curr_keyframe_index: bpy.props.IntProperty(
        name="Current Keyframe Index",
        description="",
        default=0,
        options={'HIDDEN'})

    method: bpy.props.EnumProperty(
        name="Method",
        items=interpolation_methods,
        description="Interpolation method for the spline",
        default="CatmullRom")

    metric: bpy.props.EnumProperty(
        name="Metric",
        items=interpolation_metrics,
        description="Metric to use for the spline",
        default="3DImageFlow")

    parametrization: bpy.props.EnumProperty(
        name="Parametrization",
        items=parametrization_options,
        description="Reparametrization option to use for automatic distribution.",
        default="Centripetal")

    rho: bpy.props.FloatProperty(
        name="Rho",
        description="Factor determining how much the camera will zoom during the interpolation.",
        default=2**(1/2),
        min=0.1, max=10)
    
    make_path_permanent : bpy.props.BoolProperty(
        name="Make Paths Available",
        description="Make the path geometry of the camera and target available when confirming the path?",
        default=False)
    
    make_frustum_permanent : bpy.props.BoolProperty(
        name="Make Frustum Available",
        description="Make the frustum geometry of the camera available when confirming the path?",
        default=False)

    render_animation : bpy.props.BoolProperty(
        name="Render animation",
        description="Should the camera be rendered?",
        default=True
    )
    generate_earth_file : bpy.props.BoolProperty(
        name="Generate Earth File",
        description="Is the object of interest spherical in shape?",
        default=False)

    export_dir : bpy.props.StringProperty(
        name="Exporting Directory",
        description="Directory to save the generated videos and files",
        subtype="DIR_PATH",
        default="")

    min_scale : bpy.props.FloatProperty(
        name="Min Zoom Scale",
        description="Minimum zoom factor for random start/end camera.",
        subtype="FACTOR",
        default=0.5,
        min=0.1, max=3)

    max_scale: bpy.props.FloatProperty(
        name="Max Zoom Scale",
        description="Maximum zoom factor for random start/end camera.",
        subtype="FACTOR",
        default=0.5,
        min=0.1, max=3)

    n_frames: bpy.props.IntProperty(
        name="Number of Frames",
        description="How many frames should the generated clip have?",
        default=100,
        min=2)

    selected_object: bpy.props.PointerProperty(
        name="Selected Object",
        description="Which object should the camera pan around?",
        type=bpy.types.Object
    )

# ------------------------------------------------------------------------------

class OFC_PG_OptimalPathOperatorProperties(bpy.types.PropertyGroup):
    operator_running: bpy.props.BoolProperty(
        default=False)
    
    temp_cam: bpy.props.StringProperty(
        default='OFC_Temp_AnimatedCamera',
        options={'HIDDEN'})

# ------------------------------------------------------------------------------

class OFC_PG_PropertyCollection(bpy.types.PropertyGroup):

    init_props: bpy.props.PointerProperty(
        name="Initialization Properties",
        description=".",
        type=OFC_PG_OptimalPathInitialization)

    op_props: bpy.props.PointerProperty(
        name="Operator Properties",
        description=".",
        type=OFC_PG_OptimalPathOperatorProperties)

# ------------------------------------------------------------------------------

classes = [OFC_PG_OptimalPathInitialization,
           OFC_PG_OptimalPathOperatorProperties,
           OFC_PG_PropertyCollection]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)

    # adds the property group class to the scene context (instantiates it)
    bpy.types.Scene.OFC = bpy.props.PointerProperty(type=OFC_PG_PropertyCollection)
    
    # need to add this here instead of using it directly in the class because
    # otherwise the KeyframeItem class is not found by Blender
    OFC_PG_OptimalPathInitialization.keyframes = bpy.props.CollectionProperty(type=keyframe_list.OFC_PG_KeyframeItem)

def unregister():
    #delete the custom property pointer BEFORE unregistering classes
    del bpy.types.Scene.OFC

    for cl in classes:
        bpy.utils.unregister_class(cl)