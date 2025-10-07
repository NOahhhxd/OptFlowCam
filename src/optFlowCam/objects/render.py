import random

import bpy


def render_scene(cam, file_path, start_frame=0, end_frame=100):
    scene = bpy.context.scene
    scene.sequence_editor_clear()
    scene.camera = cam
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.filepath = file_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.frame_start = start_frame
    scene.frame_end = end_frame
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    bpy.ops.render.render(animation=True)


def render_single_image(cam, file_path):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.camera = cam
    scene.render.filepath = file_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(animation=False, write_still=True)


def add_video(filepath, start, num, scene):
    clip = scene.sequence_editor.strips.new_movie(
        name=f"Video{num}",
        filepath=filepath,
        channel=num,
        frame_start=start
    )
    clip.transform.scale_x = 0.5
    clip.transform.scale_y = 0.5
    if num == 1:
        clip.transform.origin[0] = 0  # scene.render.resolution_x/8
        clip.transform.origin[1] = 1
    elif num == 2:
        clip.transform.origin[0] = 1  # scene.render.resolution_x/8
        clip.transform.origin[1] = 1
    else:
        clip.transform.origin[0] = 0  # scene.render.resolution_x/8
        clip.transform.origin[1] = 0
    return clip


def add_image(filepath, offset, num, scene, end):
    img = scene.sequence_editor.strips.new_image(
        name=f"Image_{num}",
        filepath=filepath,
        channel=num,
        frame_start=0
    )
    img.transform.scale_x = 0.5
    img.transform.scale_y = 0.5
    for i in range(offset, end + 1):
        img.transform.keyframe_insert("scale_x", frame=i)
        img.transform.keyframe_insert("scale_y", frame=i)
    img.transform.scale_x = 1
    img.transform.scale_y = 1
    for i in range(offset // 2 + 1):
        img.transform.keyframe_insert("scale_x", frame=i)
        img.transform.keyframe_insert("scale_y", frame=i)
    img.frame_final_duration = end
    img.transform.origin[0] = 1
    img.transform.origin[1] = 0

    return img


def combine_clips(file_paths, overview_path, path):
    START_OFFSET = 48
    random.shuffle(file_paths)
    scene = bpy.context.scene
    scene.sequence_editor_clear()
    scene.sequence_editor_create()

    scene.render.filepath = f"{path}\\output.mp4"
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = 24
    scene.frame_start = 1
    clips = [add_video(file, START_OFFSET, idx + 1, scene) for idx, file in enumerate(file_paths)]
    scene.frame_end = max([clip.frame_final_end for clip in clips])
    img = add_image(overview_path, START_OFFSET, 3, scene, scene.frame_end)

    bpy.ops.render.render(animation=True)
    with open(f"{path}\\solution.txt", "w+") as f:
        f.write("\n".join([f"{idx + 1}{clip}" for idx, clip in enumerate(file_paths)]))


"""
video1 = "C:\\Users\\nonoa\\Downloads\\tests\\tests\\Hase\\Test1\\TransformationsLinear.mp4"
video2 = "C:\\Users\\nonoa\\Downloads\\tests\\tests\\Hase\\Test1\\3DImageFlowGeodesic.mp4"
video3 = "C:\\Users\\nonoa\\Downloads\\tests\\tests\\Hase\\Test1\\3DImageFlow.mp4"
image1 = "C:\\Users\\nonoa\\Downloads\\tests\\tests\\Hase\\Test1\\overview.png"
combine_clips([video1, video2, video3], image1, "C:\\Users\\nonoa\\Downloads\\tests\\tests\\Hase\\Test1")
"""
