import random

import bpy


def render_scene(cam, file_path, context, start_frame=0, end_frame=100):
    """
    Renders a video
    """
    scene = context.scene
    scene.render.use_sequencer = False
    scene.camera = cam
    scene.render.filepath = file_path
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.filepath = file_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.frame_start = start_frame
    scene.frame_end = end_frame
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    context.view_layer.update()
    scene.update_tag()
    scene.update_render_engine()
    bpy.ops.render.render(animation=True, write_still=False, scene=scene.name)


def render_single_image(cam, file_path, context):
    """
    Renders a single image
    """
    scene = context.scene
    scene.render.use_sequencer = False
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.camera = cam
    scene.render.filepath = file_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.file_format = 'PNG'
    context.view_layer.update()
    scene.update_tag()
    scene.update_render_engine()
    bpy.ops.render.render(animation=False, write_still=True, scene=scene.name)


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
        clip.transform.origin[0] = 0
        clip.transform.origin[1] = 1
    elif num == 2:
        clip.transform.origin[0] = 1
        clip.transform.origin[1] = 1
    elif num == 3:
        clip.transform.origin[0] = 0
        clip.transform.origin[1] = 0
    else:
        clip.transform.origin[0] = 1
        clip.transform.origin[1] = 0
    return clip


def add_image(filepath, num, scene, end):
    img = scene.sequence_editor.strips.new_image(
        name=f"Image_{num}",
        filepath=filepath,
        channel=num,
        frame_start=0,
    )
    img.transform.scale_x = 1
    img.transform.scale_y = 1
    for i in range(end):
        img.transform.keyframe_insert("scale_x", frame=i)
        img.transform.keyframe_insert("scale_y", frame=i)
    img.frame_final_duration = end

    return img


def combine_clips(file_paths, overview_path, path, context):
    """
    Combines different clips and an image to one clip
    """
    START_OFFSET = 48
    random.shuffle(file_paths)
    scene = context.scene
    scene.render.use_sequencer = True
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
    img = add_image(overview_path, 3, scene, START_OFFSET)

    bpy.ops.render.render(animation=True)
    scene.sequence_editor_clear()
    with open(f"{path}\\solution.txt", "w+") as f:
        f.write("\n".join([f"{idx + 1}{clip.split("\\")[-1]}" for idx, clip in enumerate(file_paths)]))
