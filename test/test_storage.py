import unittest
import os
import json
from unittest.mock import patch, mock_open
from app.storage import StorageManager

class TestStorageManager(unittest.TestCase):

    def setUp(self):
        self.base_path = "./test_data"
        self.storage_manager = StorageManager(base_path=self.base_path)
        if os.path.exists(self.base_path):
            import shutil

            shutil.rmtree(self.base_path)
        self.storage_manager = StorageManager(base_path=self.base_path)

    def tearDown(self):
        if os.path.exists(self.base_path):
            import shutil

            shutil.rmtree(self.base_path)

    def test_ensure_dirs_exist(self):
        self.assertTrue(os.path.exists(self.storage_manager.songs_dir))
        self.assertTrue(os.path.exists(self.storage_manager.stems_dir))
        self.assertTrue(os.path.exists(self.storage_manager.takes_dir))

    def test_load_save_config(self):
        initial_config = {"nickname": "TestUser", "first_run": False}
        self.storage_manager.save_config(initial_config)
        loaded_config = self.storage_manager.load_config()
        self.assertEqual(loaded_config["nickname"], "TestUser")
        self.assertFalse(loaded_config["first_run"])

    def test_get_or_create_config_new(self):
        if os.path.exists(self.storage_manager.config_file):
            os.remove(self.storage_manager.config_file)
        config = self.storage_manager.load_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["nickname"], None)
        self.assertTrue(config["first_run"])
        self.assertTrue(os.path.exists(self.storage_manager.config_file))

    def test_load_save_songs(self):
        initial_songs = [{"id": "s1", "title": "Song 1"}]
        self.storage_manager.save_songs(initial_songs)
        loaded_songs = self.storage_manager.load_songs()
        self.assertEqual(len(loaded_songs), 1)
        self.assertEqual(loaded_songs[0]["title"], "Song 1")

    def test_load_save_scores(self):
        initial_scores = [{"song_id": "s1", "score": 95.5}]
        self.storage_manager.save_scores(initial_scores)
        loaded_scores = self.storage_manager.load_scores()
        self.assertEqual(len(loaded_scores), 1)
        self.assertEqual(loaded_scores[0]["score"], 95.5)

    def test_get_file_paths(self):
        song_id = "test_song_id"
        nickname = "TestNick"
        self.assertEqual(self.storage_manager.get_song_file_path(song_id), os.path.join(self.base_path, "data/songs", "test_song_id.wav"))
        self.assertEqual(self.storage_manager.get_stem_file_path(song_id, "mr"), os.path.join(self.base_path, "data/stems", "test_song_id_mr.wav"))
        take_path = self.storage_manager.get_take_file_path(song_id, nickname)
        self.assertTrue(f"{song_id}_" in take_path)
        self.assertTrue(f"_{nickname}.wav" in take_path)
        self.assertTrue(os.path.exists(os.path.dirname(take_path)))

    def test_load_scores_with_corrupt_dict_file(self):
        scores_file = self.storage_manager.scores_file
        with open(scores_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        scores = self.storage_manager.load_scores()
        self.assertIsInstance(scores, list)
        self.assertEqual(scores, [])

    def test_load_songs_with_corrupt_dict_file(self):
        songs_file = os.path.join(self.storage_manager.data_dir, "songs_metadata.json")
        with open(songs_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        songs = self.storage_manager.load_songs()
        self.assertIsInstance(songs, list)
        self.assertEqual(songs, [])
if __name__ == "__main__":
    unittest.main()
