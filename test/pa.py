import os
import sys
import platform
import time
import subprocess
import socket

REPO_LINK = "https://github.com/snowman0919/PY-Garaoke.git"
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


def main():
    clear_terminal()
    print("설치를 시작합니다!")
    print("잠시만 기다려주세요...")

    print()
    print("현재 작업 디렉터리:", os.getcwd())

    if not os.path.exists(REPO_DIR):
        run_step(
            "레포지토리 클론",
            ["git", "clone", REPO_LINK],
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
    if platform.system() != "Windows":
        return False
    import ctypes
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin_windows():
    import ctypes
    if platform.system() != "Windows":
        return
    exe = sys.executable
    params = " ".join(f'"{arg}"' for arg in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        params,
        None,
        1
    )


if __name__ == "__main__":
    # if platform.system() == "Windows" and not is_admin_windows():
    #     relaunch_as_admin_windows()
    #     sys.exit(0)

    if has_internet():
        try:
            main()
        except KeyboardInterrupt:
            print()
            print("설치가 사용자에 의해 중단되었습니다...")
    else:
        print("인터넷 연결에 실패했습니다.\n설치를 위해선 인터넷에 연결해주세요!")