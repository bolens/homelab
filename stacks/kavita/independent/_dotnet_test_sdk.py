"""Compiler prerequisite shared by the optional net10.0 fixture probes."""
import subprocess
import unittest


def require_dotnet10():
    installed = subprocess.run(["dotnet", "--list-sdks"], capture_output=True, text=True, check=True).stdout
    if not installed.strip():
        raise unittest.SkipTest("requires .NET 10 SDK")
    version = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, check=True).stdout
    if not version.startswith("10."):
        raise unittest.SkipTest("requires .NET 10 SDK")
