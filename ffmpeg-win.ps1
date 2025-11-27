# 최신 ffmpeg 릴리즈 zip 다운로드 (공식 static build)
$zipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$zipPath = "$env:USERPROFILE\Downloads\ffmpeg.zip"
$extractPath = "$env:USERPROFILE\ffmpeg"

Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $extractPath

# bin 폴더 실제 경로 (폴더명에 버전번호가 있음)
$binPath = Get-ChildItem "$extractPath\ffmpeg-*" -Directory | Select-Object -First 1 | ForEach-Object { "$($_.FullName)\bin" }

# 사용자 환경변수 PATH에 bin 추가
$envPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($envPath -notlike "*$binPath*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$envPath;$binPath", "User")
    Write-Host "PATH에 $binPath 추가 완료. 새 콘솔을 열어야 적용됩니다."
} else {
    Write-Host "이미 PATH에 등록되어 있습니다."
}

# 완료 안내
Write-Host "ffmpeg 설치 및 환경변수 등록이 완료되었습니다."
