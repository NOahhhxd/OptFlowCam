import bpy

def render_scene(cam, file_path, start_frame=0, end_frame=100):
    scene = bpy.context.scene
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
"""
import moviepy as mp
from random import shuffle

def combineClips(result_path, clips):
    if not  3 <= len(clips) <= 4:
        raise ValueError("It must be between 3 and 4 clips")

    clip_list = [mp.VideoFileClip(i).resized(height=360) for i in clips]

    shuffle(clip_list)
    if len(clips) == 3:
        dummy = mp.ColorClip(size=clip_list[0].size, color=(0,0,0), duration=clip_list[0].duration)
        combined = mp.clips_array([[clip_list[0], clip_list[1]], [clip_list[2], dummy]])
    else:
        combined = mp.clips_array([[clip_list[0], clip_list[1]],[clip_list[2], clip_list[3]]])
    combined.write_videofile(result_path+"\\"+"result.mp4")
    with open(result_path+"\\"+"solution.txt", "w+") as f:
        f.write(",".join([clip.filename for clip in clip_list]))
"""