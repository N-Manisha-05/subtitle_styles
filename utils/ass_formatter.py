def format_ass_time(seconds):
    """Convert seconds (float) to ASS time (H:MM:SS.cc)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100: cs = 0; s += 1
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; h += 1
    return f"{h}:{m:02}:{s:02}.{cs:02}"

def get_ass_header(font_name="Noto Sans Telugu", font_size=80):
    """Return the standard ASS file header"""
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,5,10,10,0,1
Style: Boxed,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,20,20,40,1
"""
