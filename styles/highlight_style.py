from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time

class HighlightStyle(BaseStyle):
    """
    Rounded-corner subtitle card using thick blurry outlines.
    ALL words: large dark blurry outline → outlines merge → rounded dark card.
    ACTIVE word: same large blurry outline but orange → rounded orange highlight.
    BorderStyle=1 is used so inline \\bord controls the entire background.
    """
    CHUNK_SIZE = 5

    # Dark card background for inactive words
    # Large bord + heavy be blur → corners become naturally rounded, outlines merge
    DARK_COLOR = "&H000000&"   # black (BGR)
    DARK_ALPHA = "&H55&"       # ~67% opaque (33% transparent)
    CARD_BORD  = 12            # large outline = creates the card thickness
    CARD_BLUR  = 8             # heavy blur = soft rounded corners

    # Active word highlight
    ACTIVE_COLOR = "&H0096FF&" # bright orange (BGR 6-digit → RGB #FF9600)
    ACTIVE_ALPHA = "&H00&"     # fully opaque

    def generate_events(self, entries):
        events = []

        # Precompute reusable tag strings
        inactive_open = (
            f"{{\\1c&H00FFFFFF&\\1a&H00&"
            f"\\3c{self.DARK_COLOR}\\3a{self.DARK_ALPHA}"
            f"\\bord{self.CARD_BORD}\\be{self.CARD_BLUR}\\b0}}"
        )
        active_open = (
            f"{{\\1c&H00FFFFFF&\\1a&H00&"
            f"\\3c{self.ACTIVE_COLOR}\\3a{self.ACTIVE_ALPHA}"
            f"\\bord{self.CARD_BORD}\\be{self.CARD_BLUR}\\b1}}"
        )
        # Reset back to inactive after active word
        reset_to_inactive = (
            f"{{\\1c&H00FFFFFF&\\1a&H00&"
            f"\\3c{self.DARK_COLOR}\\3a{self.DARK_ALPHA}"
            f"\\bord{self.CARD_BORD}\\be{self.CARD_BLUR}\\b0}}"
        )

        for entry in entries:
            words = entry['text'].split()
            if not words:
                continue

            total_duration = entry['end_time'] - entry['start_time']
            chunks = [words[i:i + self.CHUNK_SIZE]
                      for i in range(0, len(words), self.CHUNK_SIZE)]
            chunk_duration = total_duration / len(chunks)

            for c_idx, chunk in enumerate(chunks):
                c_start = entry['start_time'] + c_idx * chunk_duration
                word_dur = chunk_duration / len(chunk)

                for w_idx in range(len(chunk)):
                    w_start = c_start + w_idx * word_dur
                    w_end   = w_start + word_dur

                    line_parts = []
                    for i, word in enumerate(chunk):
                        if i == w_idx:
                            line_parts.append(f"{active_open}{word}{reset_to_inactive}")
                        else:
                            line_parts.append(f"{inactive_open}{word}")

                    text = " ".join(line_parts)
                    events.append(
                        f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                        f"Boxed,,0,0,0,,{text}\n"
                    )

        return events