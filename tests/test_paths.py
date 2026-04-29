import pytest

from workclock.paths import normalize_path


def test_windows_path_passthrough():
    assert normalize_path(r"C:\foo\bar") == r"C:\foo\bar"


def test_windows_path_forward_slashes_normalized_to_backslashes():
    assert normalize_path("C:/foo/bar") == r"C:\foo\bar"


def test_mnt_c_translates_to_windows_drive():
    assert normalize_path("/mnt/c/foo/bar") == r"C:\foo\bar"


def test_mnt_d_translates_to_windows_drive():
    assert normalize_path("/mnt/d/projects/x") == r"D:\projects\x"


def test_home_translates_to_wsl_unc():
    assert normalize_path("/home/jermsai/Code/X") == r"\\wsl$\Ubuntu\home\jermsai\Code\X"


def test_root_linux_path_translates_to_wsl_unc():
    assert normalize_path("/etc/hosts") == r"\\wsl$\Ubuntu\etc\hosts"


def test_trailing_slash_stripped():
    assert normalize_path("/mnt/c/foo/") == r"C:\foo"


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        normalize_path("relative/path")
