import gradio as gr
import os
import subprocess
import time # Not directly used in this version for sleeps, but common utility
import glob # For finding files matching a pattern, not directly used here
import math # For mathematical operations like log10, pow
import ffmpeg # ffmpeg-python library (wrapper for FFmpeg executable)
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, clips_array # For video editing tasks
import shutil # For file operations like copying

# --- ヘルパー関数: 必要なディレクトリが存在することを確認・作成 ---
def ensure_dirs():
    """処理に必要な一時フォルダや出力先フォルダを作成します。"""
    os.makedirs("input_temp", exist_ok=True)    # Temporary storage for uploaded video
    os.makedirs("output_temp", exist_ok=True)   # Storage for intermediate video files
    os.makedirs("final_videos", exist_ok=True)  # Storage for final output videos

# --- メインのビデオ処理関数 ---
def process_video_layers(
    input_video_file,      # (gr.File) Uploaded video file object from Gradio
    num_compositing_loops, # (int) Number of times to repeat the compositing process
    initial_text,          # (str) Text to display on the first layer (layer 0)
    cpu_choice_str,        # (str) Processing unit to use ("CPU", "NVIDIA GPU", "AMD GPU")
    output_width,          # (int) Width of the output video
    output_height,         # (int) Height of the output video
    font_name,             # (str) Font name or full path to the font file
    text_size,             # (int) Size of the text
    text_position_str,     # (str) Position of the text ("Top", "Center", "Bottom")
    text_font_color,       # (str) Color of the text (e.g., "#FFFFFF")
    text_border_color,     # (str) Color of the text border (e.g., "#000000")
    volume_multiplier,     # (float) Volume multiplier for each video in the composite (0.0 - 1.0)
    use_dynaudnorm,        # (bool) Whether to use dynamic audio normalization (dynaudnorm)
    output_final_filename, # (str) Filename for the final output video
    progress=gr.Progress(track_tqdm=True) # Gradio progress bar object
):
    """
    ビデオを指定された回数レイヤー化し、各レイヤーにテキストをオーバーレイし、
    最終的に1つのビデオに結合するコア処理を行います。
    """
    ensure_dirs() # 必要なディレクトリを準備
    
    status_messages = [] # 処理ログを格納するリスト

    # --- 0. 入力チェック ---
    if input_video_file is None:
        return None, "Error: No input video file provided. Please upload a video."

    # --- 1. パスとパラメータの準備 ---
    uploaded_video_path = input_video_file.name # Path to the uploaded file in Gradio's temp space
    # 元のファイル拡張子を維持して、入力ビデオを input_temp にコピー
    base_input_video_filename = "source_video" + os.path.splitext(uploaded_video_path)[1]
    base_input_video = os.path.join("input_temp", base_input_video_filename)
    shutil.copy(uploaded_video_path, base_input_video)
    status_messages.append(f"Input video copied to: {base_input_video}")

    # --- コーデックとプリセットの選択 (CPU/GPUに応じて) ---
    if cpu_choice_str == "NVIDIA GPU":
        codec = 'h264_nvenc' # NVIDIA GPU H.264 encoder
        preset = 'p7'        # For NVIDIA, p1 (fastest) to p7 (highest quality). Using highest quality here.
    elif cpu_choice_str == "AMD GPU":
        codec = 'h264_amf'   # AMD GPU H.264 encoder
        preset = 'p7'        # Assuming similar preset naming for AMD (needs verification for AMF)
    else: # CPU
        codec = 'libx264'    # CPU H.264 encoder (high quality, common)
        preset = 'ultrafast' # FFmpeg preset (veryslow, slow, medium, fast, faster, veryfast, superfast, ultrafast)
    status_messages.append(f"Using codec: {codec}, preset: {preset}")

    # --- テキスト表示位置の決定 ---
    # FFmpeg の drawtext フィルタで使用する y座標の式を設定
    if text_position_str == "Top":
        text_y_position = "y=15" # 15 pixels from the top
    elif text_position_str == "Center":
        text_y_position = "y=(h-text_h)/2" # Vertically centered (h:video_height, text_h:text_height)
    else: # Bottom (default)
        text_y_position = "y=h-text_h-10" # 10 pixels from the bottom
    
    output_layer_files_for_concat = [] # 結合する各レイヤービデオのファイルパスを格納するリスト
    
    # --- 出力ファイル名の整形 ---
    if not output_final_filename.endswith(".mp4"):
        output_final_filename += ".mp4"
    final_output_path = os.path.join("final_videos", os.path.basename(output_final_filename))


    # --- 2. レイヤー0の作成 (元のビデオに初期テキストをオーバーレイ) ---
    # このレイヤーは常に作成される
    try:
        status_messages.append(f"Creating Layer 0 with text: '{initial_text}'...")
        progress(0, desc="Creating Layer 0 (layer0.mp4)") # Gradioプログレスバー更新
        layer0_output_path = os.path.join("output_temp", "layer0.mp4")

        # FFmpegのビデオフィルター設定 (解像度変更 + テキスト描画)
        video_filter_layer0 = (
            f"scale={output_width}:{output_height},"  # 出力解像度にリサイズ
            f"drawtext=fontfile='{font_name}':"       # フォント指定
            f"text='{initial_text}':"                 # 表示テキスト
            f"fontcolor={text_font_color}:"           # テキスト色
            f"fontsize={text_size}:"                  # テキストサイズ
            f"x=(w-text_w)/2:"                        # x座標 (横方向中央)
            f"{text_y_position}:"                     # y座標 (上で設定したもの)
            f"borderw=4:"                             # 縁取りの太さ
            f"bordercolor={text_border_color}"        # 縁取りの色
        )
        
        # FFmpegコマンドの実行 (ffmpeg-pythonを使用)
        (
            ffmpeg
            .input(base_input_video) # 入力ファイル
            .output(
                layer0_output_path,      # 出力ファイルパス
                vf=video_filter_layer0,  # 上で定義したビデオフィルター
                vcodec=codec,            # ビデオコーデック
                acodec='aac',            # オーディオコーデック (最初のレイヤーは再エンコード)
                ar='44100',              # オーディオサンプリングレート
                preset=preset,           # エンコードプリセット
                # GPU利用時のみ、品質関連のパラメータを追加 (例)
                **{'b:v': '20M', 'maxrate': '30M', 'bufsize': '40M'} if cpu_choice_str != "CPU" else {} 
            )
            .overwrite_output() # 出力ファイルが既に存在する場合上書き
            .run(quiet=True)    # FFmpegのログを抑制して実行
        )
        output_layer_files_for_concat.append(layer0_output_path) # 結合用リストに追加
        status_messages.append(f"Successfully created: {layer0_output_path}")
    except ffmpeg.Error as e:
        error_message = f"Error creating Layer 0: {e.stderr.decode('utf8') if e.stderr else str(e)}"
        status_messages.append(error_message)
        print(error_message)
        return None, "\n".join(status_messages) # エラー時は処理中断

    # --- 3. 合成ループ (指定回数繰り返し、レイヤーを重ねていく) ---
    # `path_from_previous_compositing` は、MoviePyでの2x2グリッド合成の入力となるビデオのパス。
    # 初回 (i=0) は元のビデオ (`base_input_video`) を使う。
    # 2回目以降は、1つ前のループでMoviePyによって合成され、(必要なら)音声正規化されたビデオ (例: output_temp/1.mp4) を使う。
    
    for i in range(num_compositing_loops):
        current_loop_iteration = i + 1 # プログレスバー表示用のループ回数 (1から開始)
        progress(current_loop_iteration / (num_compositing_loops + 1), desc=f"Processing loop {current_loop_iteration}/{num_compositing_loops}")

        current_stage_number = i + 1  # 現在処理中のステージ番号 (1, 2, ...)
        current_stage_str = str(current_stage_number) # ファイル名用 (例: "1", "2")
        status_messages.append(f"\n--- Starting loop {current_stage_number} ---")

        # --- MoviePyでの2x2グリッド合成の入力ビデオを決定 ---
        if i == 0:
            # 最初のループ (layer1.mp4 を作るための合成) では、元のビデオを入力とする
            video_path_for_moviepy_compositing = base_input_video
        else:
            # 2回目以降のループでは、前のループで MoviePy が出力したビデオ (音声正規化後) を入力とする
            # 例: ループ i=1 (2.mp4の元を作る) の場合、output_temp/1.mp4 を使用
            video_path_for_moviepy_compositing = os.path.join("output_temp", str(i) + ".mp4")
        
        status_messages.append(f"Compositing from: {video_path_for_moviepy_compositing}")
        
        # --- MoviePy を使った2x2グリッド合成処理 ---
        # 同じビデオを4つ使い、音量調整と時間差をつけて配置する
        # Define clips here to ensure they are in scope for finally block
        clip1, clip2, clip3, clip4 = None, None, None, None
        final_clip_visuals, final_clip_with_audio = None, None
        audio1, audio2, audio3, audio4 = None, None, None, None
        try:
            # MoviePyのクリップとしてビデオを読み込む
            clip1 = VideoFileClip(video_path_for_moviepy_compositing)
            clip2 = VideoFileClip(video_path_for_moviepy_compositing)
            clip3 = VideoFileClip(video_path_for_moviepy_compositing)
            clip4 = VideoFileClip(video_path_for_moviepy_compositing)

            # 各クリップの音量を調整
            clip1 = clip1.set_audio(clip1.audio.volumex(volume_multiplier))
            clip2 = clip2.set_audio(clip2.audio.volumex(volume_multiplier))
            clip3 = clip3.set_audio(clip3.audio.volumex(volume_multiplier))
            clip4 = clip4.set_audio(clip4.audio.volumex(volume_multiplier))

            # エコー効果のために開始時間をずらす (ビデオとオーディオ両方)
            VIDEO_AUDIO_DELAY_2 = 0.03 # seconds
            VIDEO_AUDIO_DELAY_3 = 0.06 # seconds
            VIDEO_AUDIO_DELAY_4 = 0.09 # seconds
            clip2 = clip2.set_start(VIDEO_AUDIO_DELAY_2)
            clip3 = clip3.set_start(VIDEO_AUDIO_DELAY_3)
            clip4 = clip4.set_start(VIDEO_AUDIO_DELAY_4)

            # 2x2のグリッド状にビデオクリップを配置
            final_clip_visuals = clips_array([[clip1, clip2], [clip3, clip4]])
            
            # オーディオも開始時間をずらして合成
            audio1 = clip1.audio
            audio2 = clip2.audio.set_start(VIDEO_AUDIO_DELAY_2) # ビデオの遅延と合わせる
            audio3 = clip3.audio.set_start(VIDEO_AUDIO_DELAY_3)
            audio4 = clip4.audio.set_start(VIDEO_AUDIO_DELAY_4)
            
            final_audio = CompositeAudioClip([audio1, audio2, audio3, audio4])
            final_clip_with_audio = final_clip_visuals.set_audio(final_audio)

            # この合成ステージの出力パス (例: output_temp/1.mp4, output_temp/2.mp4)
            # このファイルは、この後FFmpegでテキストが追加されるか、
            # (dynaudnormを使わない場合は) 次のループのMoviePy合成の入力になる。
            composited_video_path = os.path.join("output_temp", f"{current_stage_str}.mp4")
            # dynaudnorm を使う場合の一時ファイルパス
            temp_composited_for_dynaudnorm = os.path.join("output_temp", f"{current_stage_str}_tmp_dyn.mp4")

            # MoviePyの出力先パス (dynaudnormを使うかどうかで変わる)
            output_path_for_moviepy = temp_composited_for_dynaudnorm if use_dynaudnorm else composited_video_path
            
            status_messages.append(f"Writing composited video to: {output_path_for_moviepy}")
            final_clip_with_audio.write_videofile(
                output_path_for_moviepy,
                codec=codec,               # ビデオコーデック
                fps=clip1.fps,             # 元のビデオのFPSを使用
                audio_codec="aac",         # オーディオコーデック
                preset=preset,             # エンコードプリセット
                # MoviePyで合成後にFFmpegで解像度調整とSAR(Sample Aspect Ratio)を1:1に設定
                ffmpeg_params=["-vf", f"scale={output_width}:{output_height},setsar=1:1"],
                threads=os.cpu_count(),    # 利用可能なCPUスレッド数を使用
                logger=None                # MoviePyのFFmpegログを抑制 (必要なら 'bar' などで表示)
            )
            
            # 合成後、(必要なら)音声正規化されたビデオのパス
            path_after_compositing_and_norm = composited_video_path 

            # --- 動的音声正規化 (dynaudnorm) の適用 (オプション) ---
            if use_dynaudnorm:
                status_messages.append(f"Applying dynaudnorm to {temp_composited_for_dynaudnorm} -> {composited_video_path}")
                # FFmpegコマンドを直接実行して dynaudnorm を適用
                subprocess.run([
                    "ffmpeg", "-y", # 上書き許可
                    "-i", temp_composited_for_dynaudnorm, # 入力 (MoviePyが出力した一時ファイル)
                    "-af", "dynaudnorm",                  # オーディオフィルター: dynaudnorm
                    "-c:v", "copy",                       # ビデオは再エンコードせずコピー
                    "-c:a", "aac",                        # オーディオはAACでエンコード
                    composited_video_path                 # 出力 (正規化後のファイル)
                ], check=True, capture_output=True) # エラーがあれば例外発生、出力をキャプチャ
                os.remove(temp_composited_for_dynaudnorm) # 一時ファイルを削除
            
            status_messages.append(f"Successfully created composited stage: {path_after_compositing_and_norm} (Stage {current_stage_str})")
            # `path_after_compositing_and_norm` (例: output_temp/1.mp4) は、
            # この後テキストが追加され `layer1.mp4` となる。
            # また、このパスが次のループの MoviePy 合成の入力 `video_path_for_moviepy_compositing` になる。

        except Exception as e:
            error_message = f"Error during MoviePy compositing or dynaudnorm for stage {current_stage_str}: {str(e)}"
            if hasattr(e, 'stderr') and e.stderr: # subprocess.CalledProcessError の場合
                 error_message += f"\nFFmpeg stderr: {e.stderr.decode('utf8')}"
            status_messages.append(error_message)
            print(error_message)
            # MoviePyクリップオブジェクトがメモリに残っている可能性があるので、解放を試みる
            # (already defined before try block)
            # for c in [clip1, clip2, clip3, clip4, final_clip_visuals, final_clip_with_audio]:
            #     if c and 'close' in dir(c): c.close() # Check if c is not None
            return None, "\n".join(status_messages)
        finally:
            # `try`ブロック内で定義された可能性のあるMoviePyクリップオブジェクトを確実に閉じる
            # これにより、ファイルハンドルが解放され、後続の処理やファイル削除が失敗するのを防ぐ
            clips_to_close = [
                clip1, clip2, clip3, clip4,
                final_clip_visuals, final_clip_with_audio,
                audio1, audio2, audio3, audio4
            ]
            for clip_obj in clips_to_close:
                if clip_obj and hasattr(clip_obj, 'close'): # 変数が定義され、closeメソッドを持っているか確認
                    try:
                        clip_obj.close()
                    except Exception as close_ex:
                        print(f"Error closing a clip object: {close_ex}")


        # --- FFmpeg を使って、このレイヤー用のテキストを追加 ---
        # 表示するテキストは、4 の (ループ回数) 乗
        TEXT_THRESHOLD_FOR_SCIENTIFIC_NOTATION = 20 # この回数を超えると指数表記

        text_exponent_for_this_layer = current_stage_number # 1, 2, ...
        number_for_text = 4**text_exponent_for_this_layer
        
        if text_exponent_for_this_layer <= TEXT_THRESHOLD_FOR_SCIENTIFIC_NOTATION:
            text_to_show_on_layer = f'{number_for_text:,}' # 例: 16,777,216 (カンマ区切り)
        else:
            # 指数表記 (例: 1.234567890123e+20)
            # 非常に大きな数を扱うため、math.log10で桁数を取得し、仮数部と指数部に分ける
            exponent_val = int(math.floor(math.log10(number_for_text)))
            # 13桁程度の有効数字を持つように仮数部を計算
            mantissa_int_val = number_for_text // 10**(exponent_val - 12) 
            mantissa_val = mantissa_int_val / 10**12
            text_to_show_on_layer = f'{mantissa_val:.12f}e+{exponent_val}' # 小数点以下12桁で表示

        # このレイヤーの出力パス (テキスト追加後。例: output_temp/layer1.mp4)
        current_layer_output_path = os.path.join("output_temp", f"layer{current_stage_str}.mp4")
        status_messages.append(f"Adding text '{text_to_show_on_layer}' to {path_after_compositing_and_norm} -> {current_layer_output_path}")
        
        try:
            # FFmpegのビデオフィルター設定 (テキスト描画)
            # MoviePyからの出力は既に指定解像度になっているはずだが、念のためscaleも入れる (元スクリプトの意図を尊重)
            video_filter_current_layer = (
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
                .input(path_after_compositing_and_norm) # MoviePyで合成＆音声正規化されたビデオを入力
                .output(current_layer_output_path, vf=video_filter_current_layer, **{'c:a': 'copy'}) # オーディオはコピー (再エンコードしない)
                .overwrite_output()
                .run(quiet=True)
            )
            output_layer_files_for_concat.append(current_layer_output_path) # 結合用リストに追加
            status_messages.append(f"Successfully created: {current_layer_output_path}")
        except ffmpeg.Error as e:
            error_message = f"Error adding text for layer{current_stage_str}.mp4: {e.stderr.decode('utf8') if e.stderr else str(e)}"
            status_messages.append(error_message)
            print(error_message)
            return None, "\n".join(status_messages)
        
        # 次のループの MoviePy 合成では、現在のループで MoviePy が出力したファイル (テキスト追加前、音声正規化後) を使う。
        # これはループの冒頭 `video_path_for_moviepy_compositing` の設定で処理される。

    # --- 4. 全レイヤービデオの連結 ---
    if not output_layer_files_for_concat:
        status_messages.append("No layer files to concatenate.")
        return None, "\n".join(status_messages)

    # FFmpegのconcatデマクサ用のファイルリストを作成
    concat_list_filepath = os.path.join("output_temp", "file_list_for_concat.txt")
    with open(concat_list_filepath, "w", encoding='utf-8') as f_concat_list: # encodingを指定
        for file_path_item in output_layer_files_for_concat:
            # FFmpegのconcatデマクサは、ファイルリスト内のパスが絶対パスまたは
            # リストファイルからの相対パスである必要がある。安全のため絶対パスを使用。
            f_concat_list.write(f"file '{os.path.abspath(file_path_item)}'\n") # シングルクォートで囲むと特殊文字を含むパスにも対応しやすい
    
    status_messages.append(f"\nConcatenating {len(output_layer_files_for_concat)} layers into {final_output_path}...")
    progress(0.95, desc="Concatenating final video") # Gradioプログレスバー更新

    try:
        # FFmpegコマンドを直接実行してビデオを連結
        ffmpeg_command = [
            "ffmpeg", "-y",        # 上書き許可
            "-f", "concat",      # 入力フォーマット: concatデマクサ
            "-safe", "0",        # 絶対パスを許可するために必要
            "-i", concat_list_filepath, # 入力ファイルリスト
            "-c:v", codec,       # ビデオコーデック (選択されたものを使用)
            "-c:a", "aac",       # オーディオコーデック (標準的なAAC)
            "-preset", preset,   # エンコードプリセット
            final_output_path    # 最終出力ファイルパス
        ]
        if cpu_choice_str != "CPU": # GPU利用時は品質パラメータを追加 (例)
            ffmpeg_command.extend(['-b:v', '25M', '-maxrate', '40M', '-bufsize', '50M'])

        subprocess.run(ffmpeg_command, check=True, capture_output=True) # エラーがあれば例外発生
        status_messages.append(f"Successfully created final video: {final_output_path}")
    except subprocess.CalledProcessError as e:
        error_message = f"Error during final concatenation: {e.stderr.decode('utf8') if e.stderr else str(e)}"
        status_messages.append(error_message)
        print(error_message)
        return None, "\n".join(status_messages)

    # --- 5. 後片付け (オプション) ---
    # 現在は中間ファイル (`output_temp` 内のファイル) は自動削除されない。
    # Gradioに「中間ファイルを削除する」チェックボックスを追加することも検討可能。
    
    # 連結用ファイルリストを削除
    if os.path.exists(concat_list_filepath):
        os.remove(concat_list_filepath)
    # input_temp にコピーした元のビデオファイルを削除
    if os.path.exists(base_input_video):
        os.remove(base_input_video)

    status_messages.append("\nProcessing complete!")
    return final_output_path, "\n".join(status_messages) # 最終ビデオのパスとログを返す


# --- Gradio UI (ユーザーインターフェース) の定義 ---
with gr.Blocks(theme=gr.themes.Default()) as demo:
    gr.Markdown("# LSVM v1.0")
    gr.Markdown("Upload a video, configure options, and generate a layered video with text overlays.")

    with gr.Row(): # 横並びのセクション
        with gr.Column(scale=1): # 左側のカラム
            gr.Markdown("### Input & Output")
            input_video = gr.File(label="Upload Input Video", file_types=['.mp4', '.mov', '.avi', '.mkv'])
            output_filename_textbox = gr.Textbox(label="Output Filename (e.g., final_video.mp4)", value="layered_output.mp4")
            
            gr.Markdown("### Processing Settings")
            num_loops_slider = gr.Slider(label="Number of Compositing Layers (iterations)", minimum=0, maximum=100, value=1, step=1) # minを0に (レイヤー0のみも可能に)
            # num_loops_slider = 0 の場合: レイヤー0 (初期テキスト付きビデオ) のみが作成され、それが最終出力となる。
            # num_loops_slider = 1 の場合: レイヤー0 と レイヤー1 が作成され、連結される。
            cpu_choice_radio = gr.Radio(label="Processing Unit", choices=["CPU", "NVIDIA GPU", "AMD GPU"], value="CPU")
            
            gr.Markdown("### Video Dimensions")
            output_width_number = gr.Number(label="Output Width (pixels)", value=1280, precision=0)
            output_height_number = gr.Number(label="Output Height (pixels)", value=720, precision=0)

        with gr.Column(scale=1): # 右側のカラム
            gr.Markdown("### Text Overlay Settings")
            initial_text_input_textbox = gr.Textbox(label="Initial Text (for Layer 0)", value="1")
            font_path_input_textbox = gr.Textbox(
                label="Font Name or Full Font File Path", 
                value="C:/Windows/Fonts/arialbd.ttf", # Windowsの例。環境に合わせて変更が必要
                placeholder="e.g., Arial or /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            )
            text_size_input_slider = gr.Slider(label="Text Size", minimum=10, maximum=500, value=160, step=1) # maxを少し大きく
            text_position_choice_radio = gr.Radio(label="Text Position", choices=["Top", "Center", "Bottom"], value="Bottom")
            font_color_input_picker = gr.ColorPicker(label="Text Color", value="#FFFFFF") # 白色
            border_color_input_picker = gr.ColorPicker(label="Text Border Color", value="#000000") # 黒色

            gr.Markdown("### Audio Settings")
            volume_input_slider = gr.Slider(
                label="Volume Multiplier for Layered Audio (in 2x2 composite)", 
                minimum=0.0, maximum=1.0, value=0.25, step=0.01 # デフォルトを少し小さめに (4重になるため)
            )
            dynaudnorm_checkbox_input = gr.Checkbox(
                label="Enable Dynamic Audio Normalization (dynaudnorm) for 2x2 composited stages", 
                value=True # デフォルトで有効にしても良いかも
            )

    process_button = gr.Button("Start Processing", variant="primary")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Output Video")
            output_video_display_player = gr.Video(label="Processed Video")
        with gr.Column(scale=1):
            gr.Markdown("### Processing Log")
            status_output_textbox = gr.Textbox(label="Status / Log", lines=15, interactive=False, autoscroll=True) # autoscroll追加

    # "処理開始" ボタンがクリックされたときの動作を定義
    process_button.click(
        fn=process_video_layers, # 実行する関数
        inputs=[ # 関数に渡す入力コンポーネントのリスト
            input_video,
            num_loops_slider,
            initial_text_input_textbox,
            cpu_choice_radio,
            output_width_number,
            output_height_number,
            font_path_input_textbox,
            text_size_input_slider,
            text_position_choice_radio,
            font_color_input_picker,
            border_color_input_picker,
            volume_input_slider,
            dynaudnorm_checkbox_input,
            output_filename_textbox
        ],
        outputs=[output_video_display_player, status_output_textbox] # 関数の戻り値を受け取る出力コンポーネントのリスト
    )
    
    gr.Markdown("---")
    gr.Markdown("#### Notes:")
    gr.Markdown("- Ensure FFmpeg is installed and in your system PATH.")
    gr.Markdown("- Font names must be recognizable by FFmpeg or provide a full path to the font file (e.g., `C:/Windows/Fonts/arial.ttf` or `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`).")
    gr.Markdown("- Intermediate files are stored in `output_temp` and `input_temp` folders and are currently not auto-deleted.")
    gr.Markdown("- Final videos are saved in the `final_videos` folder.")

# スクリプトが直接実行された場合にGradioアプリを起動
if __name__ == "__main__":
    ensure_dirs() # アプリ起動前に必要なディレクトリを作成
    # `share=True` は、ローカルネットワーク外にも一時的なパブリックリンクを生成する場合に設定します。
    # デバッグ時は `debug=True` が便利です。
    demo.launch(debug=True)
