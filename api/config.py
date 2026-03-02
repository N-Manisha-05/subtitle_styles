# Shared constants for the API

# Available Telugu fonts (must be installed on the system)
VALID_FONTS = [
    "Ramabhadra",
    "Suranna",
    "Gidugu",
    "Noto Sans Telugu",
]

DEFAULT_FONT = "Noto Sans Telugu"

FONT_DESCRIPTION = (
    "Font family for subtitles. "
    "Available options: " + ", ".join(VALID_FONTS)
)
