import os
import sys
import platform
import time
import subprocess
import socket
import glob
import shutil
import zipfile
import urllib.request

REPO_LINK = "https://github.com/snowman0919/PY-Garaoke/archive/refs/heads/main.zip"
PROJECT_PREFIX = "PY-Garaoke"
ZIP_NAME = "PY-Garaoke.zip"


def clear_terminal():
    if sys.platform.startswith("win"):
        os.system("cls")
    else:
        os.system("clear")


def run_step(title, cmd, cwd=None, stream_output=False):
    print()
    base_text = f"{title} 중입니다"

    if not stream_output:
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

    else:
        print(base_text, flush=True)

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=None,
            stderr=subprocess.PIPE,
            shell=False,
        )

        while True:
            ret = proc.poll()
            if ret is not None:
                break
            time.sleep(0.3)

        stderr = proc.stderr.read() if proc.stderr else b""

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

        print(f"{title} 완료!")


def get_venv_python():
    if platform.system() == "Windows":
        return os.path.join("venv", "Scripts", "python.exe")
    else:
        return os.path.join("venv", "bin", "python")


def add_ffmpeg_to_path_windows():
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
    import ctypes

    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            exe,
            params,
            None,
            1
        )
    else:
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


def download_repo_zip():
    print()
    print("레포지토리 ZIP 파일을 다운로드합니다...")
    try:
        urllib.request.urlretrieve(REPO_LINK, ZIP_NAME)
    except Exception as e:
        print("[오류] 레포지토리 다운로드에 실패했습니다.")
        print("사유:", e)
        sys.exit(1)
    print("레포지토리 ZIP 다운로드 완료.")


def extract_repo_zip():
    print()
    print("레포지토리 압축을 해제합니다...")
    try:
        with zipfile.ZipFile(ZIP_NAME, "r") as zf:
            zf.extractall(".")
    except Exception as e:
        print("[오류] 레포지토리 압축 해제에 실패했습니다.")
        print("사유:", e)
        sys.exit(1)
    print("레포지토리 압축 해제 완료.")

    if os.path.exists(ZIP_NAME):
        try:
            os.remove(ZIP_NAME)
        except OSError:
            pass


def enter_project_directory():
    if os.path.exists("app.py") and os.path.exists("requirements.txt"):
        print("이미 프로젝트 디렉터리 내부에 있습니다. 클론 단계를 건너뜁니다.")
        return

    candidates = [
        d for d in os.listdir(".")
        if os.path.isdir(d) and d.startswith(PROJECT_PREFIX)
    ]

    if not candidates:
        download_repo_zip()
        extract_repo_zip()
        candidates = [
            d for d in os.listdir(".")
            if os.path.isdir(d) and d.startswith(PROJECT_PREFIX)
        ]
        if not candidates:
            print("[오류] 레포지토리 디렉터리를 찾지 못했습니다.")
            sys.exit(1)

    target = sorted(candidates)[0]
    print()
    print(f"프로젝트 디렉터리로 이동합니다: {target}")
    os.chdir(target)


def install_ffmpeg_windows():
    if shutil.which("ffmpeg"):
        print()
        print("ffmpeg가 이미 PATH에 존재합니다. 설치를 건너뜁니다.")
        return

    if not os.path.exists("ffmpeg-win.ps1"):
        print()
        print("[오류] ffmpeg-win.ps1 스크립트를 찾을 수 없습니다.")
        print("ffmpeg를 수동으로 설치한 뒤 다시 실행해주세요.")
        sys.exit(1)

    run_step(
        "프로그램 실행을 위한 필수 확장 프로그램 설치",
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", "ffmpeg-win.ps1"],
    )
    add_ffmpeg_to_path_windows()


def install_ffmpeg_macos():
    if shutil.which("ffmpeg"):
        print()
        print("ffmpeg가 이미 설치되어 있습니다. 설치를 건너뜁니다.")
        return

    if not shutil.which("brew"):
        print()
        print("[오류] ffmpeg가 설치되어 있지 않고 Homebrew도 찾을 수 없습니다.")
        print("ffmpeg를 수동으로 설치한 뒤 다시 실행해주세요.")
        sys.exit(1)

    run_step(
        "프로그램 실행을 위한 필수 프로그램 설치",
        ["brew", "install", "ffmpeg"],
    )


def main():
    clear_terminal()
    print("설치를 시작합니다!")
    print("잠시만 기다려주세요...")

    print()
    print("현재 작업 디렉터리:", os.getcwd())

    enter_project_directory()

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
        stream_output=True,
    )

    system = platform.system()
    if system == "Windows":
        install_ffmpeg_windows()
    elif system == "Darwin":
        install_ffmpeg_macos()
    else:
        print()
        print(f"[오류] 현재 운영체제({system})는 자동 설치 스크립트에서 지원하지 않습니다.")
        print("ffmpeg 및 의존성을 수동으로 설치한 뒤, 가상환경에서 app.py를 직접 실행해주세요.")
        sys.exit(1)

    print()
    print("모든 준비가 완료되었습니다.")
    print("곧 프로그램을 자동으로 실행합니다...")

    subprocess.run([venv_python, "app.py"])


if __name__ == "__main__":
    clear_terminal()

    system = platform.system()

    if system == "Windows":
        if not is_admin_windows():
            print("관리자 권한 요청 중...")
            try:
                relaunch_as_admin_windows()
            except RuntimeError as e:
                print()
                print(e)
                sys.exit(1)
            sys.exit(0)

    if not has_internet():
        print("인터넷 연결에 실패했습니다.\n설치를 위해선 인터넷에 연결해주세요!")
        sys.exit(1)

    try:
        main()
    except KeyboardInterrupt:
        print()
        print("설치가 사용자에 의해 중단되었습니다...")