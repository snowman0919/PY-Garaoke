$ErrorActionPreference = "Stop"

$zipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$zipPath = "$env:TEMP\ffmpeg.zip"
$extractPath = "$env:USERPROFILE\ffmpeg"

Write-Host "ffmpeg 다운로드 중..."
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

Write-Host "압축 해제 중..."
if (Test-Path $extractPath) {
    Remove-Item -Recurse -Force $extractPath
}
Expand-Archive -Path $zipPath -DestinationPath $extractPath

Remove-Item $zipPath -Force

$binPath = Get-ChildItem "$extractPath\ffmpeg-*" -Directory |
           Sort-Object LastWriteTime -Descending |
           Select-Object -First 1 |
           ForEach-Object { Join-Path $_.FullName "bin" }

if (-not (Test-Path "$binPath\ffmpeg.exe")) {
    Write-Host "ffmpeg.exe를 찾지 못했습니다."
    exit 1
}

$envPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if (-not $envPath) { $envPath = "" }

if ($envPath -notlike "*$binPath*") {
    $newPath = "$envPath;$binPath".Trim(";")
    [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "PATH 등록 완료."
} else {
    Write-Host "이미 PATH에 등록되어 있습니다."
}

Write-Host "ffmpeg 설치 및 설정 완료."