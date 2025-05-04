import glob
import os
import subprocess
import ffmpeg
from moviepy.editor import VideoFileClip, TextClip, clips_array, CompositeAudioClip

file_paths = glob.glob('input/*.mp4')
times = 0

with open ('input/settings.txt', 'r') as file:
     data = file.read().strip()
     
value = int(data)
file_names = []

for file in file_paths:
    tmp = os.path.split(file)[1]
    file_names.append(tmp)
print(file_paths)

for i in range (value): 
    try:
        if str(times) == "0":
            #text
            input_file = file_paths[0] 
            text_to_show = "4\\^" + str(times)           
            font_path = r"C\:/Windows/Fonts/arialbd.ttf"

            video_filter = (
                f"scale=1920:1072,"
                f"drawtext=fontfile='{font_path}':"
                f"text='{text_to_show}':"
                "fontcolor=white:"
                "fontsize=160:"
                "x=(w-text_w)/2:"
                "y=h-text_h-20:"
                "borderw=3:"            
                "bordercolor=black" 
            )
            
            (
                ffmpeg
                .input(input_file)
                .output(
                    'output/layer0.mp4',
                    vf=video_filter,
                    vcodec='h264_nvenc',
                    acodec='aac', 
                    ar='48000',           
                    preset='p7',
                    video_bitrate='5000k',     
                    crf=0,  
                    **{'c:a': 'copy'}
                )
                .overwrite_output()
                .run()
            )
           
            #layer
            print(file_paths)
            clip1 = VideoFileClip(file_paths[0])
            clip2 = VideoFileClip(file_paths[0])
            clip3 = VideoFileClip(file_paths[0])
            clip4 = VideoFileClip(file_paths[0])
            
        else:     
            clip1 = VideoFileClip("output/" + times + ".mp4")
            clip2 = VideoFileClip("output/" + times + ".mp4")
            clip3 = VideoFileClip("output/" + times + ".mp4")
            clip4 = VideoFileClip("output/" + times + ".mp4")

        clip1 = clip1.set_audio(clip1.audio.volumex(0.5))
        clip2 = clip2.set_audio(clip2.audio.volumex(0.5))
        clip3 = clip3.set_audio(clip3.audio.volumex(0.5))
        clip4 = clip4.set_audio(clip4.audio.volumex(0.5))

        clip2 = clip2.set_start(0.03)
        clip3 = clip3.set_start(0.06)
        clip4 = clip4.set_start(0.09)

        final_clip = clips_array([[clip1, clip2],
                                  [clip3, clip4]])
        final_clip = final_clip.set_fps(clip1.fps)

        audio1 = clip1.audio
        audio2 = clip2.audio.set_start(0.03)
        audio3 = clip3.audio.set_start(0.06)
        audio4 = clip4.audio.set_start(0.09)

        final_audio = CompositeAudioClip([audio1, audio2, audio3, audio4])
        final_clip = final_clip.set_audio(final_audio)

        final_clip = final_clip.resize((1920, 1072))
        
        final_clip.write_videofile(
            "output/" + str(int(times) + 1) + ".mp4",
            codec="h264_nvenc",
            fps=clip1.fps,
            preset="p7",
            bitrate="5000k",
            audio_codec="aac",
            audio_fps=48000,          
            ffmpeg_params=["-crf", "0"]
        )
        
        #text
        times = str(int(times) + 1)
        input_file = "output/" + str(times) + ".mp4"  
        text_to_show = "4\\^" + str(times)           
        font_path = r"C\:/Windows/Fonts/arialbd.ttf"

        video_filter = (
                f"drawtext=fontfile='{font_path}':"
                f"text='{text_to_show}':"
                "fontcolor=white:"
                "fontsize=160:"
                "x=(w-text_w)/2:"
                "y=h-text_h-20:"
                "borderw=3:"            
                "bordercolor=black" 
            )
        (
            ffmpeg
            .input(input_file)
            .output('output/layer' + str(times) + '.mp4', vf=video_filter, **{'c:a': 'copy'})
            .overwrite_output()
            .run()
        )
        
    except FileNotFoundError:
        print("error")
        break

file_list = "file_list.txt"
with open(file_list, "w") as f:
    for i in range (value + 1): 
        f.write(f"file 'output/layer{i}.mp4'\n")

output_file = "final_data/o.mp4"
command = [
    "ffmpeg",
    "-f", "concat",
    "-safe", "0",
    "-i", file_list,
    "-c:v", "h264_nvenc",  
    "-c:a", "aac", 
    "-ar", "48000",    
    output_file
]

subprocess.run(command)
print("ended")
