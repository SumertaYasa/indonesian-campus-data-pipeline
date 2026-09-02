import json
import dataclasses
from pathlib import Path
from src.models.mapped_data import KampusMapped

class JsonStorage:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.campuses = []

    def add(self, data: KampusMapped):
        """
        Adds the mapped data to the internal list.
        """
        self.campuses.append(dataclasses.asdict(data))
        
    def finalize(self) -> str:
        """
        Saves all accumulated mapped data to a single consolidated JSON file.
        Returns the path to the saved file.
        """
        file_path = self.output_dir / "campuses.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"campuses": self.campuses}, f, ensure_ascii=False, indent=2)
        return str(file_path)
