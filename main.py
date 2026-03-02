import os
import subprocess
from styles.elevate_style import ElevateStyle
from styles.word_append_style import WordAppendStyle
from styles.highlight_style import HighlightStyle
from styles.slide_style import SlideStyle
from styles.one_word_style import OneWordStyle
from styles.basic_style import BasicStyle
from styles.two_word_style import TwoWordStyle
from styles.color_word_style import ColorWordStyle
from styles.reveal_style import RevealStyle

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
    print("\n=== Subtitle Animation Toolkit ===")
    
    video_path = "inputs/video.mp4"
    srt_path = "inputs/subtitles.srt"
    
    if not os.path.exists(video_path) or not os.path.exists(srt_path):
        print("Error: Ensure 'video.mp4' and 'subtitles.srt' are in 'inputs/' folder.")
        return

    # 1. Font Selection Menu
    fonts = ["Ramabhadra", "Suranna", "Gidugu", "Noto Sans Telugu"]
    print("\nAvailable Fonts:")
    for i, f in enumerate(fonts, 1):
        print(f"{i}. {f}")
    
    try:
        f_choice = int(input("\nSelect a font (number): "))
        font_name = fonts[f_choice - 1]
    except (ValueError, IndexError):
        print("Invalid choice, defaulting to Noto Sans Telugu.")
        font_name = "Noto Sans Telugu"

    # 2. Font Size Selection
    try:
        size_input = input("\nEnter font size (default 70, press Enter to keep): ")
        font_size = int(size_input) if size_input.strip() else 70
    except ValueError:
        print("Invalid size, defaulting to 70.")
        font_size = 70

    # 3. Style Selection Menu
    styles = {
        "1": ("elevate", ElevateStyle),
        "2": ("append", WordAppendStyle),
        "3": ("highlight", HighlightStyle),
        "4": ("slide", SlideStyle),
        "5": ("oneword", OneWordStyle),
        "6": ("basic", BasicStyle),
        "7": ("twoword", TwoWordStyle),
        "8": ("colorword", ColorWordStyle),
        "9": ("reveal", RevealStyle),
    }
    print("\nAvailable Animation Styles:")
    print("1. Elevate    (Pop effect)")
    print("2. Append     (Sequential reveal)")
    print("3. Highlight  (Background boxes)")
    print("4. Slide      (Slide in from below)")
    print("5. One Word   (One word at a time)")
    print("6. Basic      (Plain subtitles, no animation)")
    print("7. Two Words  (Two words at a time)")
    print("8. Color Word (All words visible, active word in color)")
    print("9. Reveal     (All words shown: dim → active → bright)")
    
    s_choice = input("\nSelect a style (number): ")
    style_info = styles.get(s_choice, ("append", WordAppendStyle))
    style_key, style_class = style_info
    
    # Initialize the selected style with font choices from main
    selected_style = style_class(font_name=font_name, font_size=font_size)
    
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    # Clean up font name for use in filename
    font_slug = font_name.lower().replace(" ", "_")
    
    ass_path = os.path.join(output_dir, f"subtitles_{style_key}_{font_slug}.ass")
    output_video = os.path.join(output_dir, f"video_{style_key}_{font_slug}.mp4")

    print(f"\nApplying '{style_key}' animation with font '{font_name}' (size {font_size})...")
    selected_style.generate_ass(srt_path, ass_path)
    
    try:
        burn_video(video_path, ass_path, output_video)
    except Exception as e:
        print(f"Error during burning: {str(e)}")

if __name__ == "__main__":
    main()
