from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time


# ASS colors are &HBBGGRR& (reversed RGB)
# ── Customise these three colours freely ─────────────────────────────────────
FUTURE_COLOR = "&H888888&"   # Dim gray  – words not yet spoken
ACTIVE_COLOR = "&H0066FF&"   # Orange    – word being spoken right now
PAST_COLOR   = "&HFFFFFF&"   # White     – words already spoken
# ─────────────────────────────────────────────────────────────────────────────


class RevealStyle(BaseStyle):
    """
    All words are visible from the start.
    - Future words  → FUTURE_COLOR (dim)
    - Active word   → ACTIVE_COLOR (bright, highlighted)
    - Past words    → PAST_COLOR   (spoken, visible)

    Duration is split equally among words (same as OneWordStyle).
    """

    def generate_events(self, entries):
        events = []
        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue

            total_duration = entry['end_time'] - entry['start_time']
            word_duration = total_duration / len(words)

            for i in range(len(words)):
                word_start = entry['start_time'] + i * word_duration
                word_end = (
                    entry['start_time'] + (i + 1) * word_duration
                    if i < len(words) - 1
                    else entry['end_time']
                )

                parts = []
                for j, word in enumerate(words):
                    if j < i:
                        # Already spoken
                        color = PAST_COLOR
                    elif j == i:
                        # Currently active
                        color = ACTIVE_COLOR
                    else:
                        # Not yet spoken
                        color = FUTURE_COLOR

                    parts.append(f"{{\\c{color}}}{word}")

                line = " ".join(parts)
                events.append(
                    f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},"
                    f"Default,,0,0,0,,{line}\n"
                )

        return events
