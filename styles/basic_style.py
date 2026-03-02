from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time


class BasicStyle(BaseStyle):
    """
    Plain subtitle display — shows the full subtitle text for its entire duration.
    No animation, no word-by-word splitting.
    """

    def generate_events(self, entries):
        events = []
        for entry in entries:
            text = entry['text'].strip()
            if not text:
                continue
            events.append(
                f"Dialogue: 0,{format_ass_time(entry['start_time'])},{format_ass_time(entry['end_time'])},"
                f"Default,,0,0,0,,{text}\n"
            )
        return events
