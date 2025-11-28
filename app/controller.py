import os
import uuid
import json
import requests
import asyncio
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import yt_dlp
from pydub import AudioSegment

from PySide6.QtCore import QObject, Signal, QTimer, QThread
from PySide6.QtWidgets import QApplication, QMessageBox

from app.storage import StorageManager
from app.audio import AudioPlayer, AudioRecorder, RealtimePitchDetector
from app.scoring import KaraokeScorer
from app.ui import NicknameDialog, AddSongDialog, MainWindow

# Use a global thread pool for long-running tasks like download/stem separation
# to keep the GUI responsive
thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

class Controller(QObject):
    # Signals for UI updates
    update_song_list_signal = Signal(list)
    show_message_signal = Signal(str)
    show_error_signal = Signal(str)
    show_nickname_dialog_signal = Signal(str)
    song_download_progress_signal = Signal(str)
    stem_separation_progress_signal = Signal(str)
    start_singing_ui_signal = Signal(str)
    song_metadata_updated_signal = Signal(str) # For updating start/end times
    
    # Signals for singing screen
    update_playback_position_signal = Signal(float)
    update_realtime_pitch_signal = Signal(float)
    update_lyrics_signal = Signal(str)
    update_reference_pitch_signal = Signal(list, float) # New signal for thread-safe UI update

    # Signals for results screen
    show_results_signal = Signal(dict, list, list, list)

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self.storage = StorageManager()
        self.audio_player = AudioPlayer()
        self.audio_recorder = AudioRecorder()
        self.realtime_pitch_detector = RealtimePitchDetector()
        self.karaoke_scorer = KaraokeScorer()

        self.current_user_nickname = None
        self.current_song_data = None # Currently selected song for singing
        self.current_song_lyrics = []
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self._update_playback_time)
        self.start_singing_time = 0.0

        self._connect_signals()
        self._load_initial_data()
        self._check_first_run()

    def _connect_signals(self):
        # UI Signals
        self.main_window.song_list_widget.add_song_requested.connect(self.show_add_song_dialog)
        self.main_window.song_list_widget.start_singing_requested.connect(self.prepare_singing)
        self.main_window.add_song_dialog.song_add_requested.connect(self.add_song_from_youtube)
        self.main_window.singing_widget.stop_singing_requested.connect(self.stop_singing)
        self.main_window.results_widget.back_to_home_requested.connect(self.main_window.show_song_list)

        # Audio Signals
        self.audio_player.position_changed.connect(self.update_playback_position_signal)
        self.audio_player.finished.connect(self.handle_singing_finished)
        self.audio_recorder.finished.connect(self.process_recorded_take)
        self.realtime_pitch_detector.pitch_detected.connect(self.update_realtime_pitch_signal)
        self.realtime_pitch_detector.volume_detected.connect(lambda vol: None) # Can use for UI feedback later

        # Controller's internal signals to UI
        self.update_song_list_signal.connect(self.main_window.song_list_widget.update_song_list)
        self.show_message_signal.connect(lambda msg: self.main_window.statusBar().showMessage(msg, 3000))
        self.show_error_signal.connect(lambda msg: QMessageBox.critical(self.main_window, "Error", msg))
        self.show_nickname_dialog_signal.connect(self._prompt_for_nickname)
        self.song_download_progress_signal.connect(lambda msg: self.main_window.statusBar().showMessage(f"Download: {msg}", 0))
        self.stem_separation_progress_signal.connect(lambda msg: self.main_window.statusBar().showMessage(f"Stem Separation: {msg}", 0))
        self.start_singing_ui_signal.connect(self.main_window.show_singing_screen)
        self.song_metadata_updated_signal.connect(self.update_song_list) # Refresh list after metadata edit
        self.show_results_signal.connect(self.main_window.results_widget.display_results)
        
        # Connect new thread-safe signal
        self.update_reference_pitch_signal.connect(self.main_window.singing_widget.set_reference_pitch_contour)

        # Connect singing screen updates
        self.update_playback_position_signal.connect(self.main_window.singing_widget.update_playback_position)
        self.update_realtime_pitch_signal.connect(self.main_window.singing_widget.update_realtime_pitch)
        self.update_lyrics_signal.connect(self.main_window.singing_widget.update_lyrics)
        self.main_window.set_pitch_scorer_ref(self.karaoke_scorer) # Pass scorer reference for hop_length/sr

    def _load_initial_data(self):
        self.all_songs = self.storage.load_songs()
        self.update_song_list_signal.emit(self.all_songs)

        config = self.storage.load_config()
        self.current_user_nickname = config.get("nickname")

    def _check_first_run(self):
        config = self.storage.load_config()
        if config.get("first_run", True) or not self.current_user_nickname:
            self.show_nickname_dialog_signal.emit(self.current_user_nickname)

    def _prompt_for_nickname(self, current_nickname):
        dialog = NicknameDialog(current_nickname, self.main_window)
        dialog.nickname_set.connect(self._set_nickname)
        dialog.exec()

    def _set_nickname(self, nickname):
        self.current_user_nickname = nickname
        config = self.storage.load_config()
        config["nickname"] = nickname
        config["first_run"] = False
        self.storage.save_config(config)
        self.show_message_signal.emit(f"Nickname set to: {nickname}")
        self.main_window.show_song_list() # Ensure we are on song list after nickname setup

    def update_song_list(self, song_id=None):
        self.all_songs = self.storage.load_songs()
        self.update_song_list_signal.emit(self.all_songs)

    def show_add_song_dialog(self):
        self.main_window.add_song_dialog.open()

    def add_song_from_youtube(self, url_or_query, song_title_hint):
        self.show_message_signal.emit(f"Adding song: {url_or_query}...")
        thread_pool.submit(self._download_and_separate_song, url_or_query)

    def _download_and_separate_song(self, url_or_query):
        try:
            # 1. Download audio
            song_id = str(uuid.uuid4())
            output_path = self.storage.get_song_file_path(song_id)
            output_dir = os.path.dirname(output_path)
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                # Force stereo output so downstream stem separation always sees 2 channels
                'postprocessor_args': ['-ac', '2'],
                'outtmpl': os.path.join(output_dir, f"{song_id}.%(ext)s"),
                'quiet': False, # Enable logging for debug
                'no_warnings': False,
                'noplaylist': True,
                'default_search': 'ytsearch',
                # Let yt-dlp pick a working client (android sdkless / web_safari) instead of forcing one
                # 'extractor_args': {'youtube': {'player_client': ['default']}},
                # 'username': 'oauth2', 
                # 'password': '',
            }

            # If input is not a URL, assume it's a search query
            if not url_or_query.startswith(("http://", "https://")):
                url_or_query = f"ytsearch1:{url_or_query}"

            self.song_download_progress_signal.emit("Starting download...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url_or_query, download=True)
                # If a search query was used, info_dict will contain results for the first video
                if 'entries' in info_dict:
                    if not info_dict['entries']:
                         raise Exception("No search results found.")
                    info_dict = info_dict['entries'][0]

                title = info_dict.get('title', 'Unknown Title')
                artist = info_dict.get('artist', info_dict.get('uploader', 'Unknown Artist'))
                duration_sec = info_dict.get('duration', 0)
                youtube_url = info_dict.get('webpage_url', url_or_query)

            # Ensure the downloaded file is named correctly as WAV
            downloaded_file = os.path.join(output_dir, f"{song_id}.wav")
            
            # Cleanup: Remove any .mhtml files that might have been downloaded due to client errors
            for f in os.listdir(output_dir):
                if f.startswith(song_id) and f.endswith(".mhtml"):
                    try:
                        os.remove(os.path.join(output_dir, f))
                    except OSError:
                        pass

            if not os.path.exists(downloaded_file):
                # Search for any file starting with song_id
                files_in_output = os.listdir(output_dir)
                possible_files = [f for f in files_in_output if f.startswith(song_id)]
                
                # Filter out non-audio files (like .mhtml which yt-dlp might produce on some errors/captchas)
                valid_audio_exts = {'.wav', '.mp3', '.flac', '.m4a', '.webm', '.ogg', '.opus', '.aac', '.wma', '.mp4'}
                audio_candidates = [f for f in possible_files if os.path.splitext(f)[1].lower() in valid_audio_exts]
                
                found = False
                last_conv_error = None
                if audio_candidates:
                    # Prioritize .wav files
                    wav_files = [f for f in audio_candidates if f.endswith('.wav')]
                    if wav_files:
                        os.rename(os.path.join(output_dir, wav_files[0]), downloaded_file)
                        found = True
                    else:
                        # Try to convert whatever we found (e.g. .webm, .m4a, or no extension)
                        source_file = os.path.join(output_dir, audio_candidates[0])
                        try:
                            # AudioSegment.from_file handles various formats
                            audio = AudioSegment.from_file(source_file)
                            audio = audio.set_channels(2) # Ensure stereo
                            audio.export(downloaded_file, format="wav")
                            found = True
                        except Exception as conv_err:
                            print(f"Failed to convert {source_file} to wav: {conv_err}")
                            last_conv_error = conv_err
                
                if not found:
                    error_msg = f"Downloaded WAV file not found for {song_id}. Output dir contains: {files_in_output}"
                    if last_conv_error:
                        error_msg += f". Last conversion error: {last_conv_error}"
                    raise FileNotFoundError(error_msg)

            self.song_download_progress_signal.emit(f"Downloaded: {title} by {artist}")

            # 2. Stem Separation
            self.stem_separation_progress_signal.emit(f"Separating stems for {title}...")
            mr_path = self.storage.get_stem_file_path(song_id, "mr")
            sr_path = self.storage.get_stem_file_path(song_id, "sr")

            # Demucs command example (replace with actual Python API call)
            # This requires demucs to be installed and runnable via its Python API or CLI
            # from demucs.api import separate_into_parts
            # separate_into_parts(downloaded_file, [mr_path, sr_path])
            
            # Placeholder for Demucs integration. Requires correct API usage.
            # If demucs is tricky via API, subprocess call is an alternative:
            # result = subprocess.run(['demucs', '-o', self.storage.stems_dir, '--filename={stem}.wav', downloaded_file], capture_output=True, text=True)
            # print(result.stdout, result.stderr)

            from demucs_infer.pretrained import get_model
            from demucs_infer.apply import apply_model
            from demucs_infer.audio import save_audio
            import torch
            import torchaudio

            self.stem_separation_progress_signal.emit(f"Loading Demucs model for {title}...")
            model = get_model("htdemucs_ft")
            model.eval()
            device = "cuda" if torch.cuda.is_available() else "cpu"

            self.stem_separation_progress_signal.emit(f"Separating stems using {device} for {title}...")
            wav, model_sr = torchaudio.load(downloaded_file)
            # Demucs expects stereo input; downmix/duplicate as needed
            if wav.shape[0] == 1:
                wav = torch.cat([wav, wav], dim=0)
            elif wav.shape[0] > 2:
                wav = wav.mean(dim=0, keepdim=True).repeat(2, 1)
            wav = wav.unsqueeze(0)

            with torch.no_grad():
                sources = apply_model(model, wav, device=device)
            
            # Save stems
            vocals_stem = None
            accompaniment_stems = []
            
            for i, source_name in enumerate(model.sources):
                source_tensor = sources[0, i] # Remove batch dimension
                if source_name == "vocals":
                    vocals_stem = source_tensor
                else:
                    accompaniment_stems.append(source_tensor)

            if vocals_stem is not None:
                save_audio(vocals_stem, sr_path, model_sr)
            else:
                # If no vocals stem found by name, create a silent one or handle error
                AudioSegment.silent(duration=duration_sec * 1000, frame_rate=self.audio_player.sr).export(sr_path, format="wav")
                self.show_error_signal.emit(f"Vocals stem not found for {title}, created silent vocal track.")

            if accompaniment_stems:
                # Mix all accompaniment stems into one
                mixed_accompaniment = torch.sum(torch.stack(accompaniment_stems), dim=0)
                save_audio(mixed_accompaniment, mr_path, model_sr)
            else:
                # If no accompaniment stems, create a silent one or handle error
                AudioSegment.silent(duration=duration_sec * 1000, frame_rate=self.audio_player.sr).export(mr_path, format="wav")
                self.show_error_signal.emit(f"Accompaniment stems not found for {title}, created silent instrumental track.")


            self.stem_separation_progress_signal.emit(f"Stems separated for {title}")

            # 3. Store metadata
            song_metadata = {
                "id": song_id,
                "title": title,
                "artist": artist,
                "duration": duration_sec,
                "youtube_url": youtube_url,
                "file_path": downloaded_file,
                "mr_path": mr_path,
                "sr_path": sr_path,
                "start_time": 0,
                "end_time": duration_sec
            }
            self.all_songs.append(song_metadata)
            self.storage.save_songs(self.all_songs)
            self.update_song_list_signal.emit(self.all_songs)
            self.show_message_signal.emit(f"Song '{title}' added and processed!")

        except yt_dlp.utils.DownloadError as e:
            self.show_error_signal.emit(f"YouTube Download Error: {e}")
        except FileNotFoundError as e:
            self.show_error_signal.emit(f"File system error during song processing: {e}")
        except Exception as e:
            self.show_error_signal.emit(f"An unexpected error occurred during song download/separation: {e}")
        finally:
            self.song_download_progress_signal.emit("") # Clear status bar
            self.stem_separation_progress_signal.emit("") # Clear status bar

    def prepare_singing(self, song_id):
        selected_song = next((s for s in self.all_songs if s["id"] == song_id), None)
        if not selected_song:
            self.show_error_signal.emit("Selected song not found.")
            return

        if not self.current_user_nickname:
            self._prompt_for_nickname(None) # Prompt for nickname if not set
            return
        
        self.current_song_data = selected_song
        self.show_message_signal.emit(f"Preparing to sing '{selected_song['title']}'...")
        self.start_singing_ui_signal.emit(song_id) # Switch to singing screen

        # Load instrumental track
        mr_path = selected_song["mr_path"]
        if not self.audio_player.load(mr_path):
            self.show_error_signal.emit(f"Could not load instrumental track for {selected_song['title']}.")
            return
        
        # Load lyrics if available
        lyrics_path = mr_path.replace("_mr.wav", ".lrc") # Example convention
        self.current_song_lyrics = []
        if os.path.exists(lyrics_path):
            try:
                with open(lyrics_path, "r", encoding="utf-8") as f:
                    raw_lines = f.readlines()
                    self.current_song_lyrics = self._parse_lyrics(raw_lines)
            except Exception as e:
                print(f"Error loading lyrics: {e}")
                self.current_song_lyrics = []

        # Prepare UI elements
        self.main_window.singing_widget.set_reference_pitch_contour([], selected_song["duration"]) # Empty for now, will generate later
        # Actual reference pitch contour extraction for UI visualization should happen here
        # This will be done in a background thread to avoid UI freeze
        thread_pool.submit(self._extract_and_set_reference_pitch, selected_song)

        # Start countdown
        self.show_message_signal.emit("Countdown: 3...")
        QTimer.singleShot(1000, lambda: self.show_message_signal.emit("Countdown: 2..."))
        QTimer.singleShot(2000, lambda: self.show_message_signal.emit("Countdown: 1..."))
        QTimer.singleShot(3000, self._start_singing_after_countdown)

    def _parse_lyrics(self, raw_lines):
        parsed_lyrics = []
        for line in raw_lines:
            line = line.strip()
            if line.startswith("[") and "]" in line:
                try:
                    time_tag_end = line.find("]")
                    time_tag = line[1:time_tag_end]
                    lyric_text = line[time_tag_end+1:].strip()
                    
                    # Parse time tag mm:ss.xx
                    if ":" in time_tag:
                        parts = time_tag.split(":")
                        minutes = float(parts[0])
                        seconds = float(parts[1])
                        timestamp = minutes * 60 + seconds
                        parsed_lyrics.append((timestamp, lyric_text))
                except ValueError:
                    pass # Skip lines with invalid time format
        
        # Sort by timestamp just in case
        parsed_lyrics.sort(key=lambda x: x[0])
        return parsed_lyrics

    def _extract_and_set_reference_pitch(self, song_data):
        try:
            sr_path = song_data["sr_path"]
            f0_ref, _, _ = self.karaoke_scorer._extract_pitch(sr_path)
            
            # Replace NaNs with 0.0 to preserve time alignment (index = time)
            # If we just drop NaNs, we lose the timing information.
            f0_ref = np.nan_to_num(f0_ref, nan=0.0)
            
            # Pass the full, time-aligned contour to the UI via Signal
            self.update_reference_pitch_signal.emit(f0_ref.tolist(), song_data["duration"])
        except Exception as e:
            self.show_error_signal.emit(f"Error extracting reference pitch for UI: {e}")

    def _start_singing_after_countdown(self):
        if not self.current_song_data or not self.current_user_nickname:
            self.show_error_signal.emit("Cannot start singing: song data or nickname missing.")
            return

        take_filepath = self.storage.get_take_file_path(
            self.current_song_data["id"],
            self.current_user_nickname
        )

        self.audio_recorder.start_recording(take_filepath)
        self.realtime_pitch_detector.start() # Start real-time pitch detection thread

        self.audio_player.play(
            start_sec=self.current_song_data["start_time"],
            end_sec=self.current_song_data["end_time"]
        )
        self.playback_timer.start(100) # Update every 100ms
        self.start_singing_time = time.time()
        self.show_message_signal.emit("Singing started!")

    def _update_playback_time(self):
        current_time_sec = self.audio_player.stream.time / self.audio_player.sr if self.audio_player.stream else 0
        
        # Adjust for start_time offset if playback started from non-zero
        effective_time = self.current_song_data["start_time"] + current_time_sec

        self.update_playback_position_signal.emit(effective_time)

        # Update lyrics
        current_lyric = ""
        if self.current_song_lyrics:
            # Find the last lyric that has a timestamp <= effective_time
            for timestamp, text in self.current_song_lyrics:
                if effective_time >= timestamp:
                    current_lyric = text
                else:
                    break # Since lyrics are sorted, we can stop early
        
        self.update_lyrics_signal.emit(current_lyric)

    def stop_singing(self):
        self.playback_timer.stop()
        self.audio_player.stop()
        self.audio_recorder.stop_recording()
        self.realtime_pitch_detector.stop()
        self.show_message_signal.emit("Singing stopped. Processing results...")

    def handle_singing_finished(self):
        # This signal is emitted by audio_player when song ends naturally
        self.stop_singing() # Ensures recorder and pitch detector also stop
        self.show_message_signal.emit("Song finished. Processing results...")

    def process_recorded_take(self, recorded_take_filepath):
        if not recorded_take_filepath:
            self.show_error_signal.emit("No audio recorded.")
            self.main_window.show_song_list()
            return
        
        if not self.current_song_data:
            self.show_error_signal.emit("No current song data to process take.")
            self.main_window.show_song_list()
            return

        self.show_message_signal.emit("Analyzing performance...")
        thread_pool.submit(self._analyze_and_display_results, recorded_take_filepath)

    def _analyze_and_display_results(self, recorded_take_filepath):
        try:
            song_id = self.current_song_data["id"]
            sr_path = self.current_song_data["sr_path"]

            score_data = self.karaoke_scorer.score_performance(recorded_take_filepath, sr_path)
            feedback = self.karaoke_scorer.generate_feedback(score_data)

            local_score_entry = {
                "song_id": song_id,
                "nickname": self.current_user_nickname,
                "score": score_data["final_score"],
                "pitch": score_data["pitch_accuracy"],
                "rhythm": score_data["rhythm_accuracy"],
                "vibrato": score_data["vibrato_quality"],
                "timestamp": datetime.now().isoformat()
            }
            
            # Save local score
            all_scores = self.storage.load_scores()
            all_scores.append(local_score_entry)
            self.storage.save_scores(all_scores)

            # Get local rankings for this song
            local_rankings = [s for s in all_scores if s["song_id"] == song_id]
            local_rankings.sort(key=lambda x: x["score"], reverse=True)

            # Submit to server and fetch global rankings
            global_rankings = self._submit_score_to_server(local_score_entry)

            self.show_results_signal.emit(score_data, feedback, local_rankings, global_rankings)
            self.main_window.show_results_screen()

        except Exception as e:
            self.show_error_signal.emit(f"Error during performance analysis: {e}")
            self.main_window.show_song_list()

    def _submit_score_to_server(self, score_data):
        server_url = "http://127.0.0.1:8000" # Assume server runs locally
        submit_endpoint = f"{server_url}/api/submit_score"
        top_scores_endpoint = f"{server_url}/api/top_scores"

        global_rankings = []
        try:
            # Submit score
            response = requests.post(submit_endpoint, json=score_data, timeout=5)
            response.raise_for_status()
            self.show_message_signal.emit("Score submitted to global ranking!")

            # Fetch top scores
            top_scores_response = requests.get(top_scores_endpoint, params={"song_id": score_data["song_id"]}, timeout=5)
            top_scores_response.raise_for_status()
            global_rankings = top_scores_response.json()

        except requests.exceptions.ConnectionError:
            self.show_error_signal.emit("Could not connect to ranking server.")
        except requests.exceptions.Timeout:
            self.show_error_signal.emit("Ranking server timed out.")
        except requests.exceptions.RequestException as e:
            self.show_error_signal.emit(f"Error interacting with ranking server: {e}")
        return global_rankings
