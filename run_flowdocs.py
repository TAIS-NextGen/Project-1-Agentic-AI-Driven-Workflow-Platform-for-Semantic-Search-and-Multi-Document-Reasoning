from __future__ import annotations

import json
import os
import shutil
import socket
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Iterable, Sequence

APP_NAME = "FlowDocs"
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"


def println(message: str = "") -> None:
    print(message, flush=True)


def fail(message: str, code: int = 1) -> int:
    println()
    println(f"[ERROR] {message}")
    return code


def find_project_root(start: Path) -> Path | None:
    candidates = [start, start / "FlowDocs"]
    candidates.extend(path for path in start.iterdir() if path.is_dir())

    for candidate in candidates:
        if (candidate / "backend" / "main.py").is_file() and (
            candidate / "frontend" / "package.json"
        ).is_file():
            return candidate.resolve()

    # Recherche limitee pour prendre en charge une archive extraite avec un niveau en plus.
    for backend_main in start.glob("**/backend/main.py"):
        candidate = backend_main.parent.parent
        if (candidate / "frontend" / "package.json").is_file():
            return candidate.resolve()
    return None


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    println(f"> {' '.join(args)}")
    result = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
    )
    if capture and result.stdout:
        println(result.stdout.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"La commande a echoue avec le code {result.returncode}: {' '.join(args)}"
        )
    return result


def command_output(args: Sequence[str], cwd: Path | None = None) -> str:
    result = run_command(args, cwd=cwd, capture=True)
    if result.returncode != 0:
        raise RuntimeError(f"Commande en echec: {' '.join(args)}")
    return (result.stdout or "").strip()


def resolve_executable(names: Iterable[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def ensure_python_version() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError(
            f"Python 3.11 ou plus recent est requis. Version detectee: {sys.version.split()[0]}"
        )


def ensure_node() -> tuple[str, str, str]:
    node = resolve_executable(["node.exe", "node"])
    npm = resolve_executable(["npm.cmd", "npm"])
    if not node or not npm:
        raise RuntimeError(
            "Node.js ou npm est introuvable. Installez Node.js 20.19 ou plus recent, puis rouvrez Windows."
        )

    version_text = command_output([node, "--version"]).splitlines()[-1].strip().lstrip("v")
    parts = version_text.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError as exc:
        raise RuntimeError(f"Version Node.js illisible: {version_text}") from exc

    if major < 20 or (major == 20 and minor < 19):
        raise RuntimeError(
            f"Node.js 20.19 ou plus recent est requis. Version detectee: v{version_text}"
        )
    return node, npm, version_text


def valid_python(executable: Path) -> bool:
    if not executable.is_file():
        return False
    result = subprocess.run(
        [str(executable), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def create_or_get_runtime_python(runtime_dir: Path) -> tuple[Path, bool]:
    project_venv = Path.cwd() / ".venv" / "Scripts" / "python.exe"
    if valid_python(project_venv):
        return project_venv, True

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        venv_dir = Path(local_app_data) / "FlowDocs" / "venv-py311"
    else:
        venv_dir = runtime_dir / "venv-py311"
    venv_python = venv_dir / "Scripts" / "python.exe"

    if valid_python(venv_python):
        return venv_python, True

    if venv_dir.exists():
        shutil.rmtree(venv_dir, ignore_errors=True)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    println("[1/5] Creation de l'environnement Python...")
    result = run_command([sys.executable, "-m", "venv", str(venv_dir)], capture=True)
    if result.returncode == 0 and valid_python(venv_python):
        return venv_python, True

    println("[AVERTISSEMENT] Impossible de creer le venv; utilisation de Python global.")
    return Path(sys.executable), False


def imports_available(python_exe: Path) -> bool:
    imports = (
        "import fastapi,uvicorn,pydantic_settings,multipart,aiofiles,httpx;"
        "import PIL,pypdf,docx,openpyxl,dateparser,pymupdf,sklearn,numpy"
    )
    result = subprocess.run(
        [str(python_exe), "-c", imports],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def install_backend_dependencies(
    python_exe: Path, requirements: Path, using_venv: bool
) -> None:
    if imports_available(python_exe):
        println("[2/5] Dependances backend deja pretes.")
        return

    println("[2/5] Installation des dependances backend...")
    base = [str(python_exe), "-m", "pip", "install", "--disable-pip-version-check"]
    extra = [] if using_venv else ["--user"]
    run_command(base + ["--upgrade", "pip"] + extra, check=True)
    run_command(base + ["-r", str(requirements)] + extra, check=True)

    if not imports_available(python_exe):
        raise RuntimeError(
            "Les dependances backend ont ete installees, mais leur import echoue encore."
        )


def run_npm_install(npm: str, frontend: Path) -> None:
    # npm est un fichier .cmd sous Windows. shell=True est utilise uniquement ici,
    # avec une commande fixe et un cwd separe, afin d'eviter les problemes de guillemets.
    command = subprocess.list2cmdline([npm, "install", "--include=dev"])
    println(f"> {command}")
    result = subprocess.run(
        command,
        cwd=str(frontend),
        shell=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"npm install a echoue avec le code {result.returncode}.")


def ensure_frontend_dependencies(frontend: Path, npm: str) -> Path:
    vite_js = frontend / "node_modules" / "vite" / "bin" / "vite.js"
    if vite_js.is_file():
        println("[3/5] Dependances frontend deja pretes.")
        return vite_js

    println("[3/5] Installation des dependances frontend...")
    run_npm_install(npm, frontend)
    if not vite_js.is_file():
        raise RuntimeError(
            "Vite reste introuvable apres npm install. Verifiez le fichier frontend/package.json."
        )
    return vite_js


def http_ready(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_url(url: str, seconds: int, process: subprocess.Popen[bytes] | None = None) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_ready(url):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(1)
    return False


def tail_file(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return "(journal absent)"
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except OSError as exc:
        return f"(lecture impossible: {exc})"


def open_log(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8", errors="replace")


def start_process(
    args: Sequence[str],
    *,
    cwd: Path,
    log_path: Path,
) -> tuple[subprocess.Popen[bytes], object]:
    log_handle = open_log(log_path)
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
    process = subprocess.Popen(
        list(args),
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return process, log_handle



def listener_pids_windows(port: int) -> list[int]:
    """Return process IDs listening on a TCP port on Windows."""
    if os.name != "nt":
        return []
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    pids: set[int] = set()
    pattern = re.compile(rf"^\s*TCP\s+\S*:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)
    for line in (result.stdout or "").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        pid = int(match.group(1))
        if pid > 0 and pid != os.getpid():
            pids.add(pid)
    return sorted(pids)


def stop_listener_windows(port: int) -> None:
    """Stop stale FlowDocs development servers occupying a dedicated port."""
    pids = listener_pids_windows(port)
    if not pids:
        return
    println(f"[NETTOYAGE] Arret de l'ancien service sur le port {port}: PID {', '.join(map(str, pids))}")
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    deadline = time.time() + 12
    while time.time() < deadline:
        if not listener_pids_windows(port):
            return
        time.sleep(0.5)
    remaining = listener_pids_windows(port)
    if remaining:
        raise RuntimeError(
            f"Le port {port} reste occupe par le PID {remaining[0]}. Fermez l'ancien terminal FlowDocs puis relancez run.bat."
        )


def stop_stale_flowdocs_services() -> None:
    """Guarantee that this archive, not an older Vite server, is started."""
    if os.name == "nt":
        stop_listener_windows(5173)
        stop_listener_windows(8000)
    else:
        if http_ready(FRONTEND_URL) or http_ready(f"{BACKEND_URL}/health"):
            raise RuntimeError(
                "Un ancien service FlowDocs utilise deja les ports 5173 ou 8000. Arretez-le avant de relancer."
            )


def write_runtime_info(runtime_dir: Path, **data: object) -> None:
    try:
        (runtime_dir / "runtime.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def main() -> int:
    ensure_python_version()
    launcher_dir = Path(__file__).resolve().parent
    root = find_project_root(launcher_dir)
    if root is None:
        return fail(
            "Dossier FlowDocs introuvable. Le lanceur doit etre place dans le dossier qui contient backend et frontend, ou juste au-dessus."
        )

    os.chdir(root)
    frontend = root / "frontend"
    requirements = root / "backend" / "requirements.txt"
    runtime_dir = root / ".flowdocs-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    launcher_log = runtime_dir / "launcher.log"

    println()
    println("=====================================================")
    println("          FlowDocs - Demarrage Windows V14 Frontend")
    println("=====================================================")
    println(f"Projet detecte : {root}")
    println(f"Python : {sys.version.split()[0]} ({sys.executable})")

    try:
        node, npm, node_version = ensure_node()
        println(f"Node.js : v{node_version} ({node})")

        runtime_python, using_venv = create_or_get_runtime_python(runtime_dir)
        println(f"Python runtime : {runtime_python}")
        install_backend_dependencies(runtime_python, requirements, using_venv)

        env_file = frontend / ".env"
        env_file.write_text(
            "VITE_API_BASE_URL=http://127.0.0.1:8000\n", encoding="utf-8"
        )
        vite_js = ensure_frontend_dependencies(frontend, npm)

        # Important: an older Vite server can otherwise keep serving the old UI.
        stop_stale_flowdocs_services()

        backend_log = runtime_dir / "backend.log"
        frontend_log = runtime_dir / "frontend.log"
        backend_process = None
        frontend_process = None
        backend_handle = None
        frontend_handle = None

        println("[4/5] Demarrage du backend de cette version...")
        backend_process, backend_handle = start_process(
            [
                str(runtime_python),
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=root,
            log_path=backend_log,
        )
        if not wait_for_url(f"{BACKEND_URL}/health", 90, process=backend_process):
            if backend_handle:
                backend_handle.flush()
            println("\n--- Dernieres lignes du backend ---")
            println(tail_file(backend_log))
            raise RuntimeError(
                f"Le backend ne demarre pas. Journal complet: {backend_log}"
            )

        println("[5/5] Demarrage du frontend de cette version...")
        frontend_process, frontend_handle = start_process(
            [
                node,
                str(vite_js),
                "--force",
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
            cwd=frontend,
            log_path=frontend_log,
        )
        if not wait_for_url(FRONTEND_URL, 90, process=frontend_process):
            if frontend_handle:
                frontend_handle.flush()
            println("\n--- Dernieres lignes du frontend ---")
            println(tail_file(frontend_log))
            raise RuntimeError(
                f"Le frontend ne demarre pas. Journal complet: {frontend_log}"
            )

        write_runtime_info(
            runtime_dir,
            project_root=str(root),
            python=str(runtime_python),
            backend_pid=backend_process.pid if backend_process else None,
            frontend_pid=frontend_process.pid if frontend_process else None,
            backend_url=BACKEND_URL,
            frontend_url=FRONTEND_URL,
        )

        println()
        println("=====================================================")
        println("FlowDocs est pret.")
        println(f"Frontend : {FRONTEND_URL}")
        println(f"API docs : {BACKEND_URL}/docs")
        println(f"Journaux : {runtime_dir}")
        println("=====================================================")
        webbrowser.open(f"{FRONTEND_URL}/?build=frontend-refresh-v14")
        return 0

    except Exception as exc:  # noqa: BLE001 - launcher must show all errors
        with launcher_log.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {type(exc).__name__}: {exc}\n")
        return fail(f"{exc}\nJournal du lanceur: {launcher_log}")


if __name__ == "__main__":
    raise SystemExit(main())
