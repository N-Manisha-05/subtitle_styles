from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time

class WordAppendStyle(BaseStyle):
    """
    Subtitles appear one word at a time and accumulate to form a full sentence.
    """
    def generate_events(self, entries):
        events = []
        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue
            
            total_duration = entry['end_time'] - entry['start_time']
            word_duration = total_duration / len(words)
            
            for i in range(1, len(words) + 1):
                # Calculate start and end for this partial reveal
                start_offset = (i - 1) * word_duration
                # If it's the last word, make it stay until the very end of the entry
                end_offset = i * word_duration if i < len(words) else total_duration
                
                start_time = entry['start_time'] + start_offset
                end_time = entry['start_time'] + end_offset
                
                # Join only the first i words
                accumulated_text = " ".join(words[:i])
                
                events.append(f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},Default,,0,0,0,,{accumulated_text}\n")
        
        return events
