import os
import sys
import platform
import time
import subprocess
import socket
import glob

REPO_LINK = "https://github.com/snowman0919/PY-Garaoke/archive/refs/heads/main.zip"
REPO_DIR = "PY-Garaoke"


def clear_terminal():
    if sys.platform.startswith("win"):
        os.system("cls")
    else:
        os.system("clear")


def run_step(title, cmd, cwd=None):
    print()
    base_text = f"{title} 중입니다"
    print(base_text, end="", flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    dot = 0
    while True:
        ret = proc.poll()
        if ret is not None:
            break
        dot = (dot + 1) % 4
        dots = "." * dot
        padding = " " * (3 - dot)
        text = f"\r{base_text}{dots}{padding}"
        print(text, end="", flush=True)
        time.sleep(0.4)

    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        print()
        print(f"[오류] {title} 단계에서 문제가 발생했습니다.")
        if stderr:
            try:
                msg = stderr.decode("utf-8", errors="ignore")
            except Exception:
                msg = str(stderr)
            print("오류 메시지:")
            print(msg.strip())
        sys.exit(1)

    done_text = f"\r{title} 완료!"
    print(done_text + " " * 10)


def get_venv_python():
    if platform.system() == "Windows":
        return os.path.join("venv", "Scripts", "python.exe")
    else:
        return os.path.join("venv", "bin", "python")

def add_ffmpeg_to_path_windows():
    """Windows 환경에서 ffmpeg 경로를 찾아 현재 프로세스의 환경변수에 추가"""
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        return

    ffmpeg_dir = os.path.join(user_profile, "ffmpeg")
    if not os.path.exists(ffmpeg_dir):
        return

    candidates = glob.glob(os.path.join(ffmpeg_dir, "ffmpeg-*"))
    for candidate in candidates:
        bin_path = os.path.join(candidate, "bin")
        if os.path.exists(bin_path) and os.path.exists(os.path.join(bin_path, "ffmpeg.exe")):
            current_path = os.environ.get("PATH", "")
            if bin_path not in current_path:
                os.environ["PATH"] = current_path + os.pathsep + bin_path
            return


def main():
    clear_terminal()
    print("설치를 시작합니다!")
    print("잠시만 기다려주세요...")

    print()
    print("현재 작업 디렉터리:", os.getcwd())

    if os.path.exists("app.py") and os.path.exists("requirements.txt"):
        print("이미 프로젝트 디렉터리 내부에 있습니다. 클론 단계를 건너뜁니다.")
    else:
        if not os.path.exists(REPO_DIR):
            if platform.system() == "Windows":
                run_step(
                    "깃허브에서 데이터 다운로드",
                    ["curl.exe", "-L", REPO_LINK, "-o", "PY-Garaoke.zip"],
                )
                run_step(
                    "데이터 압축 해제",
                    ["tar.exe", "-xf", REPO_DIR+".zip"],
                )
                run_step(
                    "캐시파일 제거",
                    ["del", REPO_DIR+".zip"],
                )
            else:
                run_step(
                    "깃허브에서 데이터 다운로드",
                    ["curl", "-L", REPO_LINK, "-o", "PY-Garaoke.zip"],
                )
                run_step(
                    "데이터 압축 해제",
                    ["tar", "-xf", REPO_DIR+".zip"],
                )
                run_step(
                    "캐시파일 제거",
                    ["rm", "-rf", REPO_DIR+".zip"],
                )
        else:
            print()
            print("레포지토리가 이미 존재합니다. 클론을 건너뜁니다.")
        
        os.chdir(REPO_DIR)

    run_step(
        "가상환경 생성",
        [sys.executable, "-m", "venv", "venv"],
    )

    venv_python = get_venv_python()
    if not os.path.exists(venv_python):
        print()
        print("[오류] 가상환경 파이썬 실행 파일을 찾을 수 없습니다.")
        print("경로:", venv_python)
        sys.exit(1)

    run_step(
        "패키지 관리자 설치 및 업데이트",
        [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
    )

    run_step(
        "프로그램 실행을 위한 필수 패키지 설치",
        [venv_python, "-m", "pip", "install", "-r", "requirements.txt"],
    )

    if platform.system() == "Windows":
        run_step(
            "프로그램 실행을 위한 필수 확장 프로그램 설치",
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", "ffmpeg-win.ps1"],
        )
        add_ffmpeg_to_path_windows()
    else:
        run_step(
            "프로그램 실행을 위한 필수 프로그램 설치",
            ["brew", "install", "ffmpeg"],
        )

    print()
    print("모든 준비가 완료되었습니다.")
    print("곧 프로그램을 자동으로 실행합니다...")

    subprocess.run([venv_python, "app.py"])


def has_internet(host="github.com", port=443, timeout=3):
    try:
        socket.create_connection((host, port), timeout)
        return True
    except OSError:
        return False

def is_admin_windows():
    import ctypes
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def relaunch_as_admin_windows():
    import ctypes, sys, os

    exe = sys.executable
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])

    cmd = f'"{script}" {params}'

    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        cmd,
        None,
        1
    )

    if ret <= 32:
        raise RuntimeError(f"관리자 권한 요청 실패, ShellExecute 반환 코드: {ret}")


if __name__ == "__main__":
    import platform, sys

    if platform.system() == "Windows" and not is_admin_windows():
        print("관리자 권한 요청 중...")
        relaunch_as_admin_windows()
        sys.exit(0)

    if has_internet():
        try:
            main()
        except KeyboardInterrupt:
            print()
            print("설치가 사용자에 의해 중단되었습니다...")
    else:
        print("인터넷 연결에 실패했습니다.\n설치를 위해선 인터넷에 연결해주세요!")
