import os
import uuid
import time
import re
import yt_dlp
import torch
import torchaudio
from pydub import AudioSegment
from demucs_infer.pretrained import get_model
from demucs_infer.apply import apply_model
from demucs_infer.audio import save_audio

class SongProcessor:

    def __init__(self, storage_manager, karaoke_scorer):
        self.storage = storage_manager
        self.scorer = karaoke_scorer

    def process_song(self, url_or_query, progress_callback=None, error_callback=None):
        try:
            song_id = str(uuid.uuid4())
            output_path = self.storage.get_song_file_path(song_id)
            output_dir = os.path.dirname(output_path)
            if progress_callback: progress_callback("Starting download...")
            info_dict, downloaded_file = self._download_youtube(url_or_query, song_id, output_dir, progress_callback)
            title = info_dict.get('title', 'Unknown Title')
            artist = info_dict.get('artist', info_dict.get('uploader', 'Unknown Artist'))
            duration_sec = info_dict.get('duration', 0)
            youtube_url = info_dict.get('webpage_url', url_or_query)
            if progress_callback: progress_callback(f"Downloaded: {title}")
            if progress_callback: progress_callback(f"Separating stems for {title}...")
            mr_path = self.storage.get_stem_file_path(song_id, "mr")
            sr_path = self.storage.get_stem_file_path(song_id, "sr")
            self._separate_stems(downloaded_file, mr_path, sr_path, title, progress_callback)
            lrc_path = mr_path.replace("_mr.wav", ".lrc")
            self._process_subtitles(output_dir, song_id, lrc_path)
            if progress_callback: progress_callback(f"Analyzing pitch for {title}...")
            pitch_path = self.storage.get_pitch_file_path(song_id)
            self.scorer.get_pitch_contour(sr_path, save_path=pitch_path)
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
            return song_metadata
        except Exception as e:
            if error_callback: error_callback(str(e))
            raise e

    def _download_youtube(self, url_or_query, song_id, output_dir, progress_callback):
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'default_search': 'ytsearch',
        }
        
        if not url_or_query.startswith(("http://", "https://")):
            url_or_query = f"ytsearch1:{url_or_query}"

        info_dict = None
        webpage_url = None
        
        try:
            if progress_callback: progress_callback("영상 정보 검색 중...")
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info_dict = ydl.extract_info(url_or_query, download=False)
                
            if 'entries' in info_dict:
                if not info_dict['entries']: raise Exception("No search results found.")
                info_dict = info_dict['entries'][0]
            
            webpage_url = info_dict.get('webpage_url')
        except Exception as e:
            raise Exception(f"Video search failed: {e}")

        if not webpage_url:
            webpage_url = url_or_query

        ydl_opts_subs = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': False,
            'subtitleslangs': ['ko', 'en', 'jp'],
            'subtitlesformat': 'vtt',
            'outtmpl': os.path.join(output_dir, f"{song_id}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        try:
            if progress_callback: progress_callback("수동 자막 다운로드 시도 중...")
            with yt_dlp.YoutubeDL(ydl_opts_subs) as ydl:
                ydl.download([webpage_url])
        except Exception as e:
            print(f"Subtitle download step error: {e}")

        ydl_opts_audio = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'postprocessor_args': ['-ac', '2'],
            'outtmpl': os.path.join(output_dir, f"{song_id}.%(ext)s"),
            'quiet': False,
            'no_warnings': True,
            'noplaylist': True,
            'writesub': False,
        }
        
        try:
            if progress_callback: progress_callback("오디오 다운로드 중...")
            with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                ydl.download([webpage_url])
        except yt_dlp.utils.DownloadError as e:
            print(f"Audio download failed: {e}")
            raise e
        
        downloaded_file = os.path.join(output_dir, f"{song_id}.wav")
        if not os.path.exists(downloaded_file):
            files = os.listdir(output_dir)
            candidates = [f for f in files if f.startswith(song_id) and f.endswith('.wav')]
            if candidates:
                os.rename(os.path.join(output_dir, candidates[0]), downloaded_file)
            else:
                candidates = [f for f in files if f.startswith(song_id) and os.path.splitext(f)[1] in ['.webm', '.m4a', '.mp3']]
                if candidates:
                    src = os.path.join(output_dir, candidates[0])
                    AudioSegment.from_file(src).set_channels(2).export(downloaded_file, format="wav")
                else:
                    raise FileNotFoundError(f"Downloaded audio not found for {song_id}")
        
        for f in os.listdir(output_dir):
            if f.startswith(song_id):
                if f.endswith((".mhtml", ".webm", ".mp4", ".json")): 
                    try:
                        os.remove(os.path.join(output_dir, f))
                    except:
                        pass
        return info_dict, downloaded_file

    def _separate_stems(self, input_path, mr_path, sr_path, title, progress_callback):
        if progress_callback: progress_callback("Loading Demucs model...")
        model = get_model("htdemucs_ft")
        model.eval()
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        if progress_callback: progress_callback(f"Separating stems on {device}...")
        wav, sr = torchaudio.load(input_path)
        if wav.shape[0] == 1:
            wav = torch.cat([wav, wav], dim=0)
        elif wav.shape[0] > 2:
            wav = wav.mean(dim=0, keepdim=True).repeat(2, 1)
        wav = wav.unsqueeze(0)
        with torch.no_grad():
            sources = apply_model(model, wav, device=device)
        vocals_stem = None
        accompaniment_stems = []
        for i, source_name in enumerate(model.sources):
            source_tensor = sources[0, i]
            if source_name == "vocals":
                vocals_stem = source_tensor
            else:
                accompaniment_stems.append(source_tensor)
        if vocals_stem is not None:
            save_audio(vocals_stem, sr_path, sr)
        else:
            AudioSegment.silent(duration=10000).export(sr_path, format="wav")
        if accompaniment_stems:
            mixed_mr = torch.sum(torch.stack(accompaniment_stems), dim=0)
            save_audio(mixed_mr, mr_path, sr)
        else:
            AudioSegment.silent(duration=10000).export(mr_path, format="wav")

    def _process_subtitles(self, output_dir, song_id, lrc_path):
        candidates = []
        for f in os.listdir(output_dir):
            if f.startswith(song_id) and f.endswith(('.vtt', '.srt')):
                # Check if 'ko' is in the language part
                if '.ko' in f or 'Korean' in f:
                    candidates.append(f)
        
        if not candidates:
            return

        # If multiple (rare with specific yt-dlp opts), just pick the first one
        sub_file_to_use = candidates[0]
        self._convert_subs_to_lrc(os.path.join(output_dir, sub_file_to_use), lrc_path)


    def _convert_subs_to_lrc(self, sub_path, lrc_path):
        time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})')
        lrc_lines = []
        try:
            with open(sub_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            current_time = None
            current_text = []
            for line in lines:
                line = line.strip()
                if not line:
                    if current_time and current_text:
                        text = " ".join(current_text).strip()
                        text = re.sub(r'<[^>]+>', '', text)
                        if text: lrc_lines.append(f"[{current_time}]{text}")
                    current_time = None
                    current_text = []
                    continue
                if line == "WEBVTT" or line.isdigit(): continue
                if "-->" in line:
                    match = time_pattern.search(line)
                    if match:
                        h, m, s, ms = match.groups()
                        mins = int(h) * 60 + int(m)
                        secs = int(s)
                        cs = int(ms[:2])
                        current_time = f"{mins:02}:{secs:02}.{cs:02}"
                    continue
                if current_time:
                    current_text.append(line)
            if current_time and current_text:
                text = " ".join(current_text).strip()
                text = re.sub(r'<[^>]+>', '', text)
                if text: lrc_lines.append(f"[{current_time}]{text}")
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lrc_lines))
        except Exception as e:
            print(f"Subtitle conversion failed: {e}")
