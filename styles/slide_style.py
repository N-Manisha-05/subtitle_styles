from styles.base_style import BaseStyle
from utils.ass_formatter import format_ass_time

class SlideStyle(BaseStyle):
    """
    Each chunk of words slides in from the LEFT and exits to the RIGHT.

    Two events are emitted per chunk (seamless, no overlap):
      1. ENTER event  — \move(off-left → center, 0..SLIDE_MS)
         Text arrives at center and stays for the rest of this event.
      2. EXIT event   — \move(center → off-right, 0..SLIDE_MS)
         Starts exactly when the enter event ends.

    Coordinates use \an2 (bottom-center anchor):
      x = horizontal center of text, y = bottom of text line.
    """
    CHUNK_SIZE   = 5    # words per slide group
    SLIDE_MS     = 350  # enter / exit animation duration in ms

    # Screen coordinates (PlayRes 1920×1080)
    X_CENTER     = 960
    X_LEFT_OFF   = -300   # off-screen left  (text slides in from here)
    X_RIGHT_OFF  = 2300   # off-screen right (text slides out to here)
    Y_POS        = 1020   # resting y-position (bottom-center, respects margin)

    def _move(self, x1, y1, x2, y2, t1_ms=None, t2_ms=None):
        """Build an ASS \\move tag string."""
        if t1_ms is None:
            return f"\\move({x1},{y1},{x2},{y2})"
        return f"\\move({x1},{y1},{x2},{y2},{t1_ms},{t2_ms})"

    def generate_events(self, entries):
        events = []
        slide_s = self.SLIDE_MS / 1000.0   # convert ms → seconds

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
                c_end   = c_start + chunk_duration
                text    = " ".join(chunk)

                # Clamp slide duration to half the chunk so enter+exit always fit
                actual_slide_s = min(slide_s, chunk_duration / 2)
                actual_slide_ms = int(actual_slide_s * 1000)

                # ── ENTER event: off-left → center ──────────────────────────
                enter_start = c_start
                enter_end   = c_end - actual_slide_s      # leave room for exit
                enter_move  = self._move(
                    self.X_LEFT_OFF, self.Y_POS,
                    self.X_CENTER,   self.Y_POS,
                    0, actual_slide_ms
                )
                events.append(
                    f"Dialogue: 0,"
                    f"{format_ass_time(enter_start)},{format_ass_time(enter_end)},"
                    f"Slide,,0,0,0,,{{\\an2{enter_move}}}{text}\n"
                )

                # ── EXIT event: center → off-right ──────────────────────────
                exit_start = enter_end
                exit_end   = c_end
                exit_move  = self._move(
                    self.X_CENTER,   self.Y_POS,
                    self.X_RIGHT_OFF, self.Y_POS,
                    0, actual_slide_ms
                )
                events.append(
                    f"Dialogue: 0,"
                    f"{format_ass_time(exit_start)},{format_ass_time(exit_end)},"
                    f"Slide,,0,0,0,,{{\\an2{exit_move}}}{text}\n"
                )

        return events

