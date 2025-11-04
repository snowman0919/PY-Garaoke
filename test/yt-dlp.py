from yt_dlp import *

# 다운로드 경로와 파일명 설정
ydl_opts = {
    "outtmpl": "./%(title)s.%(ext)s",  # 저장할 경로와 파일명 형식,
    "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}], # 기본 webm 으로 다운로드 되는데 후에 다운로드 후 mp4로 변경하기 
}

ydl_opts = {
            "format": "best",
            "max-filesize":"300M", 
            "overwrites": True,            
            "outtmpl":  "./%(title)s.%(ext)s",
            "N" : 8,
            "downloader" :  "aria2c",
            # "progress_hooks": [my_my_hook],
            'socket_timeout': 60,
            'ignoreerrors': True,
            "verbose" : True,
            "compat_opts" : "abort-on-error"

        }

with YoutubeDL(ydl_opts) as ydl:
    ydl.cache.remove()
    ydl.download(["https://www.youtube.com/watch?v=4THFRpw68oQ"])