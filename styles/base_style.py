from abc import ABC, abstractmethod
from utils.ass_formatter import get_ass_header
from utils.srt_parser import process_srt

class BaseStyle(ABC):
    def __init__(self, font_name="Noto Sans Telugu", font_size=26):
        self.font_name = font_name
        self.font_size = font_size

    @abstractmethod
    def generate_events(self, entries):
        """Implement animation logic here to return list of ASS events"""
        pass

    def generate_ass(self, srt_path, ass_path):
        """Orchestrate ASS file generation"""
        entries = process_srt(srt_path)
        header = get_ass_header(self.font_name, self.font_size)
        events_header = "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        
        events = self.generate_events(entries)
        
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(events_header)
            f.writelines(events)
        return ass_path
