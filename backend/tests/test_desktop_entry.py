import pytest

from economy_lab.desktop_entry import build_parser


def test_desktop_parser_requires_port():
    parser = build_parser()
    args = parser.parse_args(["--port", "8765"])
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def test_desktop_parser_rejects_missing_port():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
