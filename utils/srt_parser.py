import re

def parse_srt_time(srt_time):
    """Convert SRT time (HH:MM:SS,mmm) to seconds (float)"""
    srt_time = srt_time.strip().replace(',', '.')
    parts = re.split(':', srt_time)
    if len(parts) != 3: return 0.0
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s

def process_srt(srt_path):
    """Parse SRT into a list of subtitle entries"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().replace('\r\n', '\n')
    
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) >= 3:
            # Line 0 is ID, Line 1 is time, Line 2+ is text
            time_range = lines[1]
            text = " ".join(lines[2:])
            if ' --> ' in time_range:
                start_str, end_str = time_range.split(' --> ')
                entries.append({
                    'start_time': parse_srt_time(start_str),
                    'end_time': parse_srt_time(end_str),
                    'text': text
                })
    return entries

def chunk_text(text, chunk_size=3):
    """Divide text into chunks of specified size"""
    words = text.split()
    return [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
