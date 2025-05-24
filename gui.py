import gradio as gr
import os
import subprocess
import time
import glob
import math
import ffmpeg # ffmpeg-python
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, clips_array
import shutil # For copying file

# --- Helper function to ensure directories exist ---
def ensure_dirs():
    os.makedirs("input_temp", exist_ok=True)
    os.makedirs("output_temp", exist_ok=True)
    os.makedirs("final_videos", exist_ok=True)

# --- The core video processing logic ---
def process_video_layers(
    input_video_file,
    num_compositing_loops,
    initial_text,
    cpu_choice_str,
    output_width,
    output_height,
    font_name,
    text_size,
    text_position_str,
    text_font_color,
    text_border_color,
    volume_multiplier,
    use_dynaudnorm,
    output_final_filename,
    progress=gr.Progress(track_tqdm=True)
):
    ensure_dirs()
    
    status_messages = []

    if input_video_file is None:
        return None, "Error: No input video file provided. Please upload a video."

    # --- 1. Setup Paths and Parameters ---
    uploaded_video_path = input_video_file.name # Path to the uploaded file in Gradio's temp space
    base_input_video = os.path.join("input_temp", "source_video" + os.path.splitext(uploaded_video_path)[1])
    shutil.copy(uploaded_video_path, base_input_video)
    status_messages.append(f"Input video copied to: {base_input_video}")

    # --- Codec and Preset based on CPU choice ---
    if cpu_choice_str == "NVIDIA GPU":
        codec = 'h264_nvenc'
        preset = 'p7'
    elif cpu_choice_str == "AMD GPU":
        codec = 'h264_amf'
        preset = 'p7'
    else: # CPU
        codec = 'libx264'
        preset = 'ultrafast'
    status_messages.append(f"Using codec: {codec}, preset: {preset}")

    # --- Text Position ---
    if text_position_str == "Top":
        text_y_position = "y=15"
    elif text_position_str == "Center":
        text_y_position = "y=(h-text_h)/2"
    else: # Bottom
        text_y_position = "y=h-text_h-10"

    output_layer_files_for_concat = []
    
    # --- Sanitize output filename ---
    if not output_final_filename.endswith(".mp4"):
        output_final_filename += ".mp4"
    final_output_path = os.path.join("final_videos", os.path.basename(output_final_filename))


    # --- 2. Create layer0.mp4 (Initial text overlay on original video) ---
    try:
        status_messages.append(f"Creating layer0 with text: '{initial_text}'...")
        progress(0, desc="Creating layer0.mp4")
        layer0_output_path = os.path.join("output_temp", "layer0.mp4")
        video_filter_layer0 = (
            f"scale={output_width}:{output_height},"
            f"drawtext=fontfile='{font_name}':"
            f"text='{initial_text}':"
            f"fontcolor={text_font_color}:"
            f"fontsize={text_size}:"
            f"x=(w-text_w)/2:"
            f"{text_y_position}:"
            f"borderw=4:"
            f"bordercolor={text_border_color}"
        )
        (
            ffmpeg
            .input(base_input_video)
            .output(
                layer0_output_path,
                vf=video_filter_layer0,
                vcodec=codec,
                acodec='aac', # Re-encode audio for the first layer
                ar='44100',
                preset=preset,
                **{'b:v': '20M', 'maxrate': '30M', 'bufsize': '40M'} if cpu_choice_str != "CPU" else {} # Example quality params for GPU
            )
            .overwrite_output()
            .run(quiet=True)
        )
        output_layer_files_for_concat.append(layer0_output_path)
        status_messages.append(f"Successfully created {layer0_output_path}")
    except ffmpeg.Error as e:
        error_msg = f"Error creat: {e.stderr.decode('utf8') if e.stderr else str(e)}"
        status_messages.append(error_msg)
        print(error_msg)
        return None, "\n".join(status_messages)

    # --- 3. Loop for compositing and subsequent text overlays ---
    # `current_compositing_input_path` will be `base_input_video` for the first composited layer (layer1),
    # then the output of the previous compositing stage (`N.mp4`) for subsequent layers.
    
    path_from_previous_compositing = base_input_video # Initial input for the first 2x2 grid

    for i in range(num_compositing_loops):
        current_loop_iter_for_progress = i + 1
        progress(current_loop_iter_for_progress / (num_compositing_loops +1) , desc=f"Processing loop {i+1}/{num_compositing_loops}")

        current_output_stage_num = i + 1  # 1, 2, ...
        current_output_stage_str = str(current_output_stage_num)
        status_messages.append(f"\n--- Starting loop {current_output_stage_num} ---")

        # --- Determine input for compositing ---
        # In the original script, the 2x2 grid was made from file_paths[0] for times=0,
        # and output/times.mp4 for subsequent.
        # Here, path_from_previous_compositing holds the correct source.
        if i == 0:
             video_path_for_moviepy_compositing = base_input_video
        else:
            # This should be the output of the PREVIOUS compositing stage, before text was added.
            # e.g., for loop i=1 (making 2.mp4), use output/1.mp4
             video_path_for_moviepy_compositing = os.path.join("output_temp", str(i) + ".mp4")


        status_messages.append(f"Compositing from: {video_path_for_moviepy_compositing}")
        
        # --- Compositing (2x2 grid) using MoviePy ---
        try:
            clip1 = VideoFileClip(video_path_for_moviepy_compositing)
            clip2 = VideoFileClip(video_path_for_moviepy_compositing)
            clip3 = VideoFileClip(video_path_for_moviepy_compositing)
            clip4 = VideoFileClip(video_path_for_moviepy_compositing)

            clip1 = clip1.set_audio(clip1.audio.volumex(volume_multiplier))
            clip2 = clip2.set_audio(clip2.audio.volumex(volume_multiplier))
            clip3 = clip3.set_audio(clip3.audio.volumex(volume_multiplier))
            clip4 = clip4.set_audio(clip4.audio.volumex(volume_multiplier))

            # Apply start delays for the "echo" effect
            clip2 = clip2.set_start(0.03)
            clip3 = clip3.set_start(0.06)
            clip4 = clip4.set_start(0.09)

            final_clip_visuals = clips_array([[clip1, clip2], [clip3, clip4]])
            
            # Audio composition
            audio1 = clip1.audio
            audio2 = clip2.audio.set_start(0.03) # Audio needs to match video delays
            audio3 = clip3.audio.set_start(0.06)
            audio4 = clip4.audio.set_start(0.09)
            
            final_audio = CompositeAudioClip([audio1, audio2, audio3, audio4])
            final_clip_with_audio = final_clip_visuals.set_audio(final_audio)

            # Output path for this composited stage (e.g., output_temp/1.mp4, output_temp/2.mp4)
            # This file will be the input for the next compositing stage if dynaudnorm is not used,
            # OR it will be the input for the text overlay of the current layer.
            composited_video_path = os.path.join("output_temp", f"{current_output_stage_str}.mp4")
            temp_composited_for_dynaudnorm = os.path.join("output_temp", f"{current_output_stage_str}_tmp_dyn.mp4")

            output_path_for_moviepy = temp_composited_for_dynaudnorm if use_dynaudnorm else composited_video_path
            
            status_messages.append(f"Writing composited video to: {output_path_for_moviepy}")
            final_clip_with_audio.write_videofile(
                output_path_for_moviepy,
                codec=codec,
                fps=clip1.fps, # Use FPS of source
                audio_codec="aac",
                preset=preset,
                ffmpeg_params=["-vf", f"scale={output_width}:{output_height},setsar=1:1"], # Scale after compositing
                threads=os.cpu_count(), # Utilize available CPU threads for encoding
                logger=None # Suppress moviepy's verbose FFMPEG logs if desired, or 'bar'
            )
            path_after_compositing_and_norm = composited_video_path # Assume this for now

            if use_dynaudnorm:
                status_messages.append(f"Applying dynaudnorm to {temp_composited_for_dynaudnorm} -> {composited_video_path}")
                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", temp_composited_for_dynaudnorm,
                    "-af", "dynaudnorm",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    composited_video_path
                ], check=True, capture_output=True)
                os.remove(temp_composited_for_dynaudnorm)
            
            status_messages.append(f"Successfully created composited stage: {path_after_compositing_and_norm}")
            # This path_after_compositing_and_norm (e.g. output_temp/1.mp4) is now ready to have text added
            # AND will be the input for the NEXT loop's MoviePy compositing.

        except Exception as e:
            error_msg = f"Error during MoviePy compositing or dynaudnorm for stage {current_output_stage_str}: {str(e)}"
            if hasattr(e, 'stderr'): error_msg += f"\nFFmpeg stderr: {e.stderr.decode('utf8')}"
            status_messages.append(error_msg)
            print(error_msg)
            # Clean up clips if they are open
            for c in [clip1, clip2, clip3, clip4, final_clip_visuals, final_clip_with_audio]:
                if 'close' in dir(c): c.close()
            return None, "\n".join(status_messages)
        finally:
            # Ensure clips are closed to release file handles
            for c_name in ['clip1', 'clip2', 'clip3', 'clip4', 'final_clip_visuals', 'final_clip_with_audio', 'audio1', 'audio2', 'audio3', 'audio4']:
                if c_name in locals():
                    clip_obj = locals()[c_name]
                    if hasattr(clip_obj, 'close'):
                        clip_obj.close()

        # --- Text for this layer (layerN.mp4) ---
        text_exponent_for_this_layer = current_output_stage_num # 1, 2, ...
        number_for_text = 4**text_exponent_for_this_layer
        
        if text_exponent_for_this_layer <= 20: # Original script threshold
            text_to_show_on_layer = f'{number_for_text:,}'
        else:
            if text_exponent_for_this_layer == 21 and isinstance(text_to_show_on_layer, str): # From previous iteration
                 # This logic for number conversion seems to assume text_to_show_on_layer is the previous number string.
                 # It should be based on number_for_text
                 pass # The original logic here was a bit complex, simplifying for now.

            # Scientific notation for large numbers
            exp = int(math.floor(math.log10(number_for_text)))
            mantissa_int = number_for_text // 10**(exp - 12)  # get ~13 significant digits
            mantissa = mantissa_int / 10**12
            text_to_show_on_layer = f'{mantissa:.12f}e+{exp}'

        current_layer_output_path = os.path.join("output_temp", f"layer{current_output_stage_str}.mp4")
        status_messages.append(f"Adding text '{text_to_show_on_layer}' to {path_after_compositing_and_norm} -> {current_layer_output_path}")
        
        try:
            video_filter_current_layer = (
                # Input (path_after_compositing_and_norm) is already scaled by MoviePy's output
                # So, drawtext doesn't need to scale again if sizes match.
                # However, to be safe and match original script's intent of explicit scaling before text:
                f"scale={output_width}:{output_height}," 
                f"drawtext=fontfile='{font_name}':"
                f"text='{text_to_show_on_layer}':"
                f"fontcolor={text_font_color}:"
                f"fontsize={text_size}:"
                f"x=(w-text_w)/2:"
                f"{text_y_position}:"
                f"borderw=4:"
                f"bordercolor={text_border_color}"
            )
            (
                ffmpeg
                .input(path_after_compositing_and_norm) # Use the output from compositing/dynaudnorm
                .output(current_layer_output_path, vf=video_filter_current_layer, **{'c:a': 'copy'}) # Copy audio
                .overwrite_output()
                .run(quiet=True)
            )
            output_layer_files_for_concat.append(current_layer_output_path)
            status_messages.append(f"Successfully created {current_layer_output_path}")
        except ffmpeg.Error as e:
            error_msg = f"Error adding text for layer{current_output_stage_str}.mp4: {e.stderr.decode('utf8') if e.stderr else str(e)}"
            status_messages.append(error_msg)
            print(error_msg)
            return None, "\n".join(status_messages)
        
        # The output of the compositing stage (e.g., output_temp/1.mp4) is used as input for the *next* compositing loop.
        # So, path_from_previous_compositing = path_after_compositing_and_norm for the next iteration. This is implicitly handled by video_path_for_moviepy_compositing logic.


    # --- 4. Concatenation ---
    if not output_layer_files_for_concat:
        status_messages.append("No layer files to concatenate.")
        return None, "\n".join(status_messages)

    concat_list_file = os.path.join("output_temp", "file_list_for_concat.txt")
    with open(concat_list_file, "w") as f:
        for file_path in output_layer_files_for_concat:
            # FFmpeg concat demuxer needs relative paths from the file list or absolute paths.
            # Using absolute paths is safer here.
            f.write(f"file '{os.path.abspath(file_path)}'\n")
    
    status_messages.append(f"\nConcatenating {len(output_layer_files_for_concat)} layers into {final_output_path}...")
    progress(0.95, desc="Concatenating final video")
    try:
        command = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0", # Needed if paths in file_list.txt are absolute or complex
            "-i", concat_list_file,
            "-c:v", codec, # Use selected codec for final output
            "-c:a", "aac", # Standard audio codec
            "-preset", preset,
            final_output_path
        ]
        if cpu_choice_str != "CPU": # Add quality params for GPU if desired for final concat
             command.extend(['-b:v', '25M', '-maxrate', '40M', '-bufsize', '50M'])

        subprocess.run(command, check=True, capture_output=True)
        status_messages.append(f"Successfully created final video: {final_output_path}")
    except subprocess.CalledProcessError as e:
        error_msg = f"Error during final concatenation: {e.stderr.decode('utf8') if e.stderr else str(e)}"
        status_messages.append(error_msg)
        print(error_msg)
        return None, "\n".join(status_messages)

    # --- 5. Cleanup (optional - for now, keep intermediate for debugging) ---
    # Consider adding a checkbox to Gradio: "Delete intermediate files"
    # If checked, remove "output_temp" and "input_temp" contents.
    # For now, cleaning up concat list file:
    if os.path.exists(concat_list_file):
        os.remove(concat_list_file)
    if os.path.exists(base_input_video): # remove the copied input
        os.remove(base_input_video)


    status_messages.append("\nProcessing complete!")
    return final_output_path, "\n".join(status_messages)


# --- Gradio Interface Definition ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Video Layering & Text Overlay Tool")
    gr.Markdown("Upload a video, configure options, and generate a layered video with text overlays.")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Input & Output")
            input_video = gr.File(label="Upload Input Video", file_types=['.mp4', '.mov', '.avi', '.mkv'])
            output_filename = gr.Textbox(label="Output Filename (e.g., final_video.mp4)", value="layered_output.mp4")
            
            gr.Markdown("### Processing Settings")
            num_loops = gr.Slider(label="Number of Compositing Layers (iterations)", minimum=1, maximum=1000, value=1, step=1)
            # If num_loops = 0, only layer0 (initial text) is created and used as final.
            # If num_loops = 1, layer0 and layer1 are created and concatenated.
            cpu_choice = gr.Radio(label="Processing Unit", choices=["CPU", "NVIDIA GPU", "AMD GPU"], value="CPU")
            
            gr.Markdown("### Video Dimensions")
            output_w = gr.Number(label="Output Width", value=1280) # Defaulting to 720p for faster processing
            output_h = gr.Number(label="Output Height", value=720)

        with gr.Column(scale=1):
            gr.Markdown("### Text Overlay Settings")
            initial_text_input = gr.Textbox(label="Initial Text", value="1")
            font_path_input = gr.Textbox(label="Font Name or Full Font File Path", value="C\:/Windows/Fonts/arialbd.ttf", placeholder="e.g., Arial or C:/Windows/Fonts/arial.ttf")
            text_size_input = gr.Slider(label="Text Size", minimum=10, maximum=300, value=160, step=1)
            text_position_choice = gr.Radio(label="Text Position", choices=["Top", "Center", "Bottom"], value="Bottom")
            font_color_input = gr.ColorPicker(label="Text Font Color", value="#FFFFFF")
            border_color_input = gr.ColorPicker(label="Text Border Color", value="#000000")

            gr.Markdown("### Audio Settings")
            volume_input = gr.Slider(label="Volume Multiplier for Layered Audio", minimum=0.0, maximum=1, value=0.5, step=0.01)
            dynaudnorm_checkbox = gr.Checkbox(label="Enable Dynamic Audio Normalization (dynaudnorm) for composited stages", value=False)

    process_button = gr.Button("Start Processing", variant="primary")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Output Video")
            output_video_display = gr.Video(label="Processed Video")
        with gr.Column(scale=1):
            gr.Markdown("### Processing Log")
            status_output = gr.Textbox(label="Status / Log", lines=15, interactive=False)

    process_button.click(
        fn=process_video_layers,
        inputs=[
            input_video,
            num_loops,
            initial_text_input,
            cpu_choice,
            output_w,
            output_h,
            font_path_input,
            text_size_input,
            text_position_choice,
            font_color_input,
            border_color_input,
            volume_input,
            dynaudnorm_checkbox,
            output_filename
        ],
        outputs=[output_video_display, status_output]
    )
    
    gr.Markdown("---")
    gr.Markdown("#### Notes:")
    gr.Markdown("- Ensure FFmpeg is installed and in your system PATH.")
    gr.Markdown("- Font names must be recognizable by FFmpeg or provide a full path to the font file.")
    gr.Markdown("- Intermediate files are stored in `output_temp` and `input_temp` folders and are currently not auto-deleted.")
    gr.Markdown("- Final videos are saved in the `final_videos` folder.")

if __name__ == "__main__":
    ensure_dirs() # Ensure directories are present when script starts
    demo.launch(debug=True, share=True)
