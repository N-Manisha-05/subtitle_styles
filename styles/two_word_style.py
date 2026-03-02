from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time


class TwoWordStyle(BaseStyle):
    """
    Shows two words at a time, each pair getting equal time.
    If the total word count is odd, the last chunk will have one word.
    """

    def generate_events(self, entries):
        events = []
        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue

            # Build pairs: [(w1, w2), (w3, w4), ...]
            pairs = [words[i:i + 2] for i in range(0, len(words), 2)]
            num_pairs = len(pairs)

            total_duration = entry['end_time'] - entry['start_time']
            pair_duration = total_duration / num_pairs

            for idx, pair in enumerate(pairs):
                pair_start = entry['start_time'] + idx * pair_duration
                # Last pair holds until the very end of the subtitle block
                pair_end = entry['start_time'] + (idx + 1) * pair_duration if idx < num_pairs - 1 else entry['end_time']

                text = " ".join(pair)
                events.append(
                    f"Dialogue: 0,{format_ass_time(pair_start)},{format_ass_time(pair_end)},"
                    f"Default,,0,0,0,,{text}\n"
                )

        return events
