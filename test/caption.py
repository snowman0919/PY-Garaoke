import yt_dlp

ydl_opts = {
    'writesubtitles': True,
    'writeautomaticsub': False,
    'subtitleslangs': ['ko', 'en','jp'],
    'skip_download': True,
    'subtitlesformat': 'vtt'
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download(['https://youtu.be/9hytMjATH_Y'])