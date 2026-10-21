"""OBSERVE pins the optional CNS extra in one place. These hold whether or not CNS is installed and never skip."""

import os
from importlib import metadata
from pathlib import Path

import cns_connector

ROOT = Path(__file__).resolve().parent
PIN = "cns @ git+https://github.com/wking53214/CNS.git@v1.9.0"


def test_requirements_cns_pins_exactly_the_release():
    lines = (ROOT / "requirements-cns.txt").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.strip() and not line.startswith("#")] == [PIN]
    assert len([line for line in lines if line.startswith("#")]) == 1


def test_install_hint_names_the_pinned_file_and_release():
    assert "pip install -r requirements-cns.txt" in cns_connector.INSTALL_HINT
    assert PIN in cns_connector.INSTALL_HINT


def test_installed_cns_is_the_pinned_release_when_required():
    # Only meaningful where CI installed requirements-cns.txt; elsewhere there is nothing to compare.
    if os.environ.get("OBSERVE_REQUIRE_CNS") == "1":
        assert metadata.version("cns") == PIN.rsplit("@v", 1)[1]
