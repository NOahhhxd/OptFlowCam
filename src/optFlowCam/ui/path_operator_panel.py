import bpy


# ------------------------------------------------------------------------------

class OFC_PT_OptimalPathOperatorPanel(bpy.types.Panel):
    bl_idname = "OFC_PT_OptimalPathOperatorPanel"
    bl_label = "Optimal Path Operator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = 'objectmode'
    bl_category = "OptFlowCam"

    def draw(self, context):
        layout = self.layout

        init_props = context.scene.OFC.init_props

        init_box = layout.row().box()

        init_box.label(text="Camera Keyframes")

        keyframe_col = init_box.column()
        keyframe_col.operator("ofc.new_keyframe", text="Add Keyframe", icon="KEY_HLT")
        keyframe_col.template_list(
            "OFC_UL_KeyframeList", "",
            init_props, "keyframes", init_props, "curr_keyframe_index",
            rows=len(init_props.keyframes) + 1, type="DEFAULT")

        reparam_row = keyframe_col.row()
        reparam_row.operator("ofc.redistribute_frames", text="Redistribute Frames", icon="CENTER_ONLY")
        reparam_row.prop(init_props, "parametrization", text="")

        layout.prop(init_props, "method")
        layout.prop(init_props, "metric")

        layout.separator()

        if context.scene.OFC.op_props.operator_running:
            keyframe_col.enabled = False
            r = layout.row()

            cmd_c = r.column()
            cmd_c.alignment = "RIGHT"
            desc_c = r.column()

            for cmd, description in [("SHIFT + SPACE", "to update"),
                                     ("SHIFT + ENTER", "to make permanent"),
                                     ("ESC", "to cancel")]:
                cmd_c.label(text=cmd)
                desc_c.label(text=description)

            r.enabled = False

            layout.operator('ofc.realize_keyframe', text='Insert Current Frame')

        layout.operator('ofc.interpolate_camera', text='Interpolate Camera')
        layout.operator('ofc.compare_interpolate_camera', text='Compare Methods')


# ------------------------------------------------------------------------------

class OFC_PT_OptimalPathAdvancedOptionsPanel(bpy.types.Panel):
    bl_idname = "OFC_PT_OptimalPathAdvancedOptionsPanel"
    bl_parent_id = "OFC_PT_OptimalPathOperatorPanel"
    bl_label = "Advanced Options"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = 'objectmode'
    bl_category = "OptFlowCam"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        init_props = context.scene.OFC.init_props

        rho_row = layout.row()
        rho_row.prop(init_props, "rho")
        reset_rho_operator = rho_row.operator('ofc.reset_property', text="", icon="LOOP_BACK")
        reset_rho_operator.target = "rho"

        layout.prop(init_props, "make_path_permanent")
        layout.prop(init_props, "make_frustum_permanent")


class OFC_PT_OptimalPathCompareOptionsPanel(bpy.types.Panel):
    bl_idname = "OFC_PT_OptimalPathCompareOptionsPanel"
    bl_parent_id = "OFC_PT_OptimalPathOperatorPanel"
    bl_label = "Compare Options"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = 'objectmode'
    bl_category = "OptFlowCam"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        init_props = context.scene.OFC.init_props

        layout.prop(init_props, "random_cams")
        layout.prop(init_props, "selected_object")
        layout.prop(init_props, "export_dir")
        layout.prop(init_props, "render_animation")
        layout.prop(init_props, "generate_earth_file")
        layout.prop(init_props, "min_scale")
        layout.prop(init_props, "max_scale")
        layout.prop(init_props, "n_frames")
        layout.prop(init_props, "min_greedy_point_difference")


class OFC_PT_CreateGoogleEarthCamPanel(bpy.types.Panel):
    bl_idname = "OFC_PT_CreateGoogleEarthCamPanel"
    bl_parent_id = "OFC_PT_OptimalPathOperatorPanel"
    bl_label = "Create Cam by Google Earth Data"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = 'objectmode'
    bl_category = "OptFlowCam"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        earth_cam_props = context.scene.OFC.earth_cam_props

        layout.prop(earth_cam_props, "longitude")
        layout.prop(earth_cam_props, "latitude")
        layout.prop(earth_cam_props, "altitude")
        layout.prop(earth_cam_props, "rotX")
        layout.prop(earth_cam_props, "rotY")
        layout.prop(earth_cam_props, "rotZ")
        layout.operator('ofc.create_earth_cam', text='Create Cam')


# ------------------------------------------------------------------------------

classes = [OFC_PT_OptimalPathOperatorPanel,
           OFC_PT_OptimalPathAdvancedOptionsPanel,
           OFC_PT_OptimalPathCompareOptionsPanel,
           OFC_PT_CreateGoogleEarthCamPanel
           ]


def register():
    for cl in classes:
        bpy.utils.register_class(cl)
        print(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
