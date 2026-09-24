#!/usr/bin/env python3
"""Entrada do DockerFlow convertido para Vela. O cliente gRPC legado fica preservado."""
import sys
from vela.cli.commands import CommandRunner

if __name__ == "__main__":
    CommandRunner().execute(sys.argv[1:])
