import os
import subprocess
from styles.elevate_style import ElevateStyle
from styles.word_append_style import WordAppendStyle

# Registry for future animations
STYLE_REGISTRY = {
    "elevate": ElevateStyle(),
    "append": WordAppendStyle(),
    # "slide": SlideInStyle(),
    # "reveal": WordRevealStyle(),
}

def burn_video(video_path, ass_path, output_path):
    """Hard-burn subtitles into video using FFmpeg"""
    abs_ass_path = os.path.abspath(ass_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass='{abs_ass_path}'",
        "-c:a", "copy",
        output_path
    ]
    print(f"\nBurning animated subtitles into video...")
    subprocess.run(cmd, check=True)
    print(f"\nSuccess! Final video saved at: {output_path}")

def main():
    print("=== Subtitle Animation Toolkit (Modular) ===")
    
    video_path = "inputs/video.mp4"
    srt_path = "inputs/subtitles.srt"
    
    if not os.path.exists(video_path) or not os.path.exists(srt_path):
        print("Error: Ensure 'video.mp4' and 'subtitles.srt' are in 'inputs/' folder.")
        return


    style_key = "append"
    selected_style = STYLE_REGISTRY[style_key]
    
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    ass_path = os.path.join(output_dir, f"subtitles_{style_key}.ass")
    output_video = os.path.join(output_dir, f"video_{style_key}.mp4")

    print(f"Applying '{style_key}' animation...")
    selected_style.generate_ass(srt_path, ass_path)
    
    try:
        burn_video(video_path, ass_path, output_video)
    except Exception as e:
        print(f"Error during burning: {str(e)}")

if __name__ == "__main__":
    main()
