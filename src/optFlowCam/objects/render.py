import bpy

def render_scene(cam, file_path, start_frame=0, end_frame=100):
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.filepath = file_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.frame_start = start_frame
    scene.frame_end = end_frame
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'

    bpy.ops.render.render(animation=True)

"""
scene = bpy.context.scene
scene.camera = bpy.data.objects["OptFlowCam.001"]
scene.render.filepath = "C:\\Users\\nonoa\\Desktop\\test.mp4"# file_path
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.frame_start = 0
scene.frame_end = 100
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'

bpy.ops.render.render(animation=True)
"""