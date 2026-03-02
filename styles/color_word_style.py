from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time


# ASS colors are &HBBGGRR& (Blue-Green-Red, NOT RGB)
# Change ACTIVE_COLOR to any color you like:
#   Orange : &H0066FF&
#   Yellow : &H00FFFF&
#   Cyan   : &HFF9900&
#   Green  : &H00FF00&
ACTIVE_COLOR = "&H0066FF&"   # Orange


class ColorWordStyle(BaseStyle):
    """
    Shows all words of a subtitle simultaneously.
    The currently 'active' word is rendered in ACTIVE_COLOR;
    all other words stay in the default white.
    Duration is divided equally among words.
    """

    def generate_events(self, entries):
        events = []
        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue

            total_duration = entry['end_time'] - entry['start_time']
            word_duration = total_duration / len(words)

            for i, active_word in enumerate(words):
                word_start = entry['start_time'] + i * word_duration
                word_end = (
                    entry['start_time'] + (i + 1) * word_duration
                    if i < len(words) - 1
                    else entry['end_time']
                )

                # Build the line: color the active word, keep others white
                parts = []
                for j, word in enumerate(words):
                    if j == i:
                        parts.append(f"{{\\c{ACTIVE_COLOR}}}{word}{{\\c&HFFFFFF&}}")
                    else:
                        parts.append(word)

                line = " ".join(parts)
                events.append(
                    f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},"
                    f"Default,,0,0,0,,{line}\n"
                )

        return events
