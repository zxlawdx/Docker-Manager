import argparse
import subprocess as sb
import threading
import time
import sys
from pathlib import Path

from docker_manager_client import url as url_client
from grpc_server import url as url_server

PYTHON = sys.executable

BASE_DIR = Path(__file__).parent.resolve()


def stream_logs(prefix, pipe):
    for line in iter(pipe.readline, ''):
        print(f"[{prefix}] {line}", end='')


def start_process(prefix, folder, file_key, url_module):
    """
    Inicia qualquer processo baseado no URL.py
    """

    file_name = url_module.URL[file_key]

    process = sb.Popen(
        [PYTHON, file_name],
        cwd=BASE_DIR / folder,
        stdout=sb.PIPE,
        stderr=sb.STDOUT,
        text=True,
        bufsize=1
    )

    threading.Thread(
        target=stream_logs,
        args=(prefix, process.stdout),
        daemon=True
    ).start()

    return process


def run_server():
    server = start_process(
        prefix="SERVER",
        folder="grpc_server",
        file_key="server",
        url_module=url_server
    )

    server.wait()


def run_client():
    client = start_process(
        prefix="CLIENT",
        folder="docker_manager_client",
        file_key="app",
        url_module=url_client
    )

    client.wait()


def run_all():

    server = start_process(
        prefix="SERVER",
        folder="grpc_server",
        file_key="server",
        url_module=url_server
    )

    time.sleep(2)

    client = start_process(
        prefix="CLIENT",
        folder="docker_manager_client",
        file_key="app",
        url_module=url_client
    )

    client.wait()

    server.terminate()
    server.wait()


def main():

    parser = argparse.ArgumentParser(
        description="Docker Manager CLI"
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("runserver")
    subparsers.add_parser("runclient")
    subparsers.add_parser("runall")

    args = parser.parse_args()

    commands = {
        "runserver": run_server,
        "runclient": run_client,
        "runall": run_all
    }

    command = commands.get(args.command)

    if command:
        command()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()