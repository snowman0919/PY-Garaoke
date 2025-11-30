from yt_dlp import *

ydl_opts = {
    "outtmpl": "./%(title)s.%(ext)s",
    "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
}
ydl_opts = {
            "format": "best",
            "max-filesize":"300M",
            "overwrites": True,
            "outtmpl":  "./%(title)s.%(ext)s",
            "N" : 8,
            "downloader" :  "aria2c",
            'socket_timeout': 60,
            'ignoreerrors': True,
            "verbose" : True,
            "compat_opts" : "abort-on-error"
        }
with YoutubeDL(ydl_opts) as ydl:
    ydl.cache.remove()
    ydl.download(["https://www.youtube.com/watch?v=4THFRpw68oQ"])
