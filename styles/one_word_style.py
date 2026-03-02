from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time


class OneWordStyle(BaseStyle):
    """
    Shows exactly one word at a time.
    The subtitle duration is divided equally among all words,
    so each word gets an identical time slot before being replaced
    by the next word.
    """

    def generate_events(self, entries):
        events = []
        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue

            total_duration = entry['end_time'] - entry['start_time']
            word_duration = total_duration / len(words)

            for i, word in enumerate(words):
                word_start = entry['start_time'] + i * word_duration
                # Last word holds until the very end of the subtitle block
                word_end = entry['start_time'] + (i + 1) * word_duration if i < len(words) - 1 else entry['end_time']

                events.append(
                    f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},"
                    f"Default,,0,0,0,,{word}\n"
                )

        return events
