import builtins
import sys
from types import SimpleNamespace

import pytest

from cbsc_zdc.data.root_adapter import BranchMap, inspect_root


def test_branch_map_is_frozen_and_complete():
    branches = BranchMap("e", "px", "py", "pz", "eid", "ee", "hid", "hl", "he")
    assert branches.hcal_energy == "he"
    with pytest.raises(Exception):
        branches.e = "changed"


def test_inspect_root_reports_missing_optional_dependency(monkeypatch, tmp_path):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "uproot":
            raise ImportError("simulated missing uproot")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.delitem(sys.modules, "uproot", raising=False)
    with pytest.raises(RuntimeError, match="Install uproot/awkward"):
        inspect_root(tmp_path / "missing.root")


def test_inspect_root_uses_uproot_and_returns_classnames(monkeypatch, tmp_path):
    class FakeRootFile:
        def items(self):
            return [("myTree;1", SimpleNamespace(classname="TTree"))]

    opened = []

    def fake_open(path):
        opened.append(path)
        return FakeRootFile()

    monkeypatch.setitem(sys.modules, "uproot", SimpleNamespace(open=fake_open))
    path = tmp_path / "sample.root"
    assert inspect_root(path) == {"myTree;1": "TTree"}
    assert opened == [path]
