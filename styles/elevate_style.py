from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time
from utils.srt_parser import chunk_text

class ElevateStyle(BaseStyle):
    def generate_events(self, entries):
        events = []
        yellow = "&H00FFFF" # Yellow (Red+Green)
        white = "&HFFFFFF" # White

        for entry in entries:
            chunks = chunk_text(entry['text'], chunk_size=3)
            
            total_duration = entry['end_time'] - entry['start_time']
            chunk_duration = total_duration / len(chunks)
            
            for c_idx, chunk in enumerate(chunks):
                c_start = entry['start_time'] + (c_idx * chunk_duration)
                c_end = c_start + chunk_duration
                
                word_dur = chunk_duration / len(chunk)
                for w_idx, target_word in enumerate(chunk):
                    w_start = c_start + (w_idx * word_dur)
                    w_end = w_start + word_dur
                    
                    line_parts = []
                    for i, word in enumerate(chunk):
                        if i == w_idx:
                            # Pop effect: start 100%, grow to 120%, back to 100%
                            pop_time = min(200, int(word_dur * 500))
                            tag = f"{{\\1c{yellow}\\fscx100\\fscy100\\t(0,{pop_time},\\fscx120\\fscy120)\\t({pop_time},{pop_time*2},\\fscx100\\fscy100)}}"
                            line_parts.append(f"{tag}{word}{{\\1c{white}\\fscx100\\fscy100}}")
                        else:
                            line_parts.append(word)
                    
                    text = " ".join(line_parts)
                    events.append(f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},Default,,0,0,0,,{text}\n")
        return events
