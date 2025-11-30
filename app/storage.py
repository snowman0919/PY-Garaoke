import json
import os
from datetime import datetime

class StorageManager:
    def __init__(self, base_path="."):
        self.base_path = base_path
        self.data_dir = os.path.join(self.base_path, "data")
        self.songs_dir = os.path.join(self.data_dir, "songs")
        self.stems_dir = os.path.join(self.data_dir, "stems")
        self.takes_dir = os.path.join(self.data_dir, "takes")
        self.scores_file = os.path.join(self.data_dir, "scores.json")
        self.config_file = os.path.join(self.data_dir, "config.json")

        self._ensure_dirs_exist()

    def _ensure_dirs_exist(self):
        os.makedirs(self.songs_dir, exist_ok=True)
        os.makedirs(self.stems_dir, exist_ok=True)
        os.makedirs(self.takes_dir, exist_ok=True)

    def _load_json(self, filepath, default_data=None):
        if not os.path.exists(filepath):
            if default_data is not None:
                self._save_json(filepath, default_data)
                return default_data
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, filepath, data):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_config(self):
        default_config = {"nickname": None, "first_run": True}
        return self._load_json(self.config_file, default_config)

    def save_config(self, config):
        self._save_json(self.config_file, config)

    def load_songs(self):
        data = self._load_json(os.path.join(self.data_dir, "songs_metadata.json"), [])
        if not isinstance(data, list):
            return []
        return data

    def save_songs(self, songs):
        self._save_json(os.path.join(self.data_dir, "songs_metadata.json"), songs)

    def load_scores(self):
        data = self._load_json(self.scores_file, [])
        if not isinstance(data, list):
            return []
        return data

    def save_scores(self, scores):
        self._save_json(self.scores_file, scores)

    def get_song_file_path(self, song_id):
        return os.path.join(self.songs_dir, f"{song_id}.wav")

    def get_stem_file_path(self, song_id, stem_type): # stem_type: 'mr' or 'sr'
        return os.path.join(self.stems_dir, f"{song_id}_{stem_type}.wav")

    def get_pitch_file_path(self, song_id):
        return os.path.join(self.stems_dir, f"{song_id}_pitch.npy")

    def get_take_file_path(self, song_id, nickname):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return os.path.join(self.takes_dir, f"{song_id}_{timestamp}_{nickname}.wav")

