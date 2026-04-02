import io

from odoo_venv.main import _process_requirement_line, _resolve_mode_overrides
from odoo_venv.modes import KnownIssue, Mode, ModeOverride, available_modes, load_modes


class TestModeLoading:
    """Verify load_modes() returns correct structure from real modes.toml."""

    def test_loads_three_modes(self):
        modes = load_modes()
        assert set(modes.keys()) == {"conservative", "modern", "bleeding-edge"}

    def test_strategies(self):
        modes = load_modes()
        assert modes["conservative"].strategy == "compat"
        assert modes["modern"].strategy == "latest-secure"
        assert modes["bleeding-edge"].strategy == "uncapped"

    def test_bleeding_edge_no_overrides(self):
        modes = load_modes()
        assert modes["bleeding-edge"].overrides == []
        assert modes["bleeding-edge"].known_issues == []
        assert modes["bleeding-edge"].extra_commands == []

    def test_available_modes(self):
        assert available_modes() == {"conservative", "modern", "bleeding-edge"}


class TestModeOverrideFromDict:
    """Verify ModeOverride.from_dict normalizes ignore/install to lists."""

    def test_string_ignore_becomes_list(self):
        override = ModeOverride.from_dict({
            "package": "pkg",
            "ignore": "pkg==1.0",
            "install": "pkg>=2.0",
        })
        assert override.ignore == ["pkg==1.0"]
        assert override.install == ["pkg>=2.0"]

    def test_list_ignore_stays_list(self):
        override = ModeOverride.from_dict({
            "package": "pkg",
            "ignore": ["pkg==1.0", "pkg==1.1"],
            "install": ["pkg>=2.0"],
        })
        assert override.ignore == ["pkg==1.0", "pkg==1.1"]
        assert override.install == ["pkg>=2.0"]

    def test_missing_fields_default(self):
        override = ModeOverride.from_dict({"package": "pkg"})
        assert override.ignore == []
        assert override.install == []
        assert override.when == ""
        assert override.reason == ""

    def test_empty_string_becomes_empty_list(self):
        override = ModeOverride.from_dict({"package": "pkg", "ignore": "", "install": ""})
        assert override.ignore == []
        assert override.install == []


class TestKnownIssueFromDict:
    def test_from_dict(self):
        ki = KnownIssue.from_dict({
            "package": "gevent",
            "error_pattern": "Failed to build",
            "suggestion": "Use --mode modern",
            "link": "https://example.com",
        })
        assert ki.package == "gevent"
        assert ki.error_pattern == "Failed to build"
        assert ki.link == "https://example.com"

    def test_missing_link_defaults_empty(self):
        ki = KnownIssue.from_dict({
            "package": "gevent",
            "error_pattern": "err",
            "suggestion": "fix it",
        })
        assert ki.link == ""


class TestResolveOverrides:
    """Verify _resolve_mode_overrides evaluates markers correctly."""

    def test_compat_applies_matching_overrides(self):
        mode = Mode(
            description="test",
            strategy="compat",
            overrides=[
                ModeOverride(
                    package="urllib3",
                    ignore=["urllib3==1.26.5"],
                    install=["urllib3==1.26.14"],
                    when="python_version > '3.9'",
                ),
            ],
            known_issues=[],
            extra_commands=[],
        )
        ignore, extra = _resolve_mode_overrides(mode, "17.0", "3.10")
        assert "urllib3==1.26.5" in ignore
        assert "urllib3==1.26.14" in extra

    def test_marker_no_match_skips_override(self):
        mode = Mode(
            description="test",
            strategy="compat",
            overrides=[
                ModeOverride(
                    package="psycopg2",
                    ignore=["psycopg2==2.7.3.1"],
                    install=["psycopg2==2.8.3"],
                    when="python_version < '3.8'",
                ),
            ],
            known_issues=[],
            extra_commands=[],
        )
        ignore, extra = _resolve_mode_overrides(mode, "18.0", "3.10")
        assert ignore == []
        assert extra == []

    def test_uncapped_returns_empty(self):
        mode = Mode(
            description="test",
            strategy="uncapped",
            overrides=[],
            known_issues=[],
            extra_commands=[],
        )
        ignore, extra = _resolve_mode_overrides(mode, "17.0", "3.10")
        assert ignore == []
        assert extra == []

    def test_empty_when_always_matches(self):
        mode = Mode(
            description="test",
            strategy="compat",
            overrides=[
                ModeOverride(
                    package="foo",
                    ignore=["foo==1.0"],
                    install=["foo==2.0"],
                    when="",
                ),
            ],
            known_issues=[],
            extra_commands=[],
        )
        ignore, extra = _resolve_mode_overrides(mode, "17.0", "3.10")
        assert "foo==1.0" in ignore
        assert "foo==2.0" in extra


class TestStripSpecifiers:
    """Verify _process_requirement_line strips specifiers in bleeding-edge."""

    def test_strips_version_specifier(self):
        f = io.StringIO()
        result = _process_requirement_line("gevent==21.8.0", {}, f, {}, strip_specifiers=True)
        assert result is True
        assert f.getvalue().strip() == "gevent"

    def test_preserves_name_without_strip(self):
        f = io.StringIO()
        result = _process_requirement_line("gevent==21.8.0", {}, f, {}, strip_specifiers=False)
        assert result is True
        assert f.getvalue().strip() == "gevent==21.8.0"

    def test_strips_complex_specifier(self):
        f = io.StringIO()
        _process_requirement_line("urllib3>=1.26.5,<2.0", {}, f, {}, strip_specifiers=True)
        assert f.getvalue().strip() == "urllib3"

    def test_strips_extras_keeps_package_name(self):
        f = io.StringIO()
        _process_requirement_line("requests[security]==2.28.0", {}, f, {}, strip_specifiers=True)
        # Requirement.name strips extras; package name only
        assert f.getvalue().strip() == "requests"

    def test_comment_lines_skipped(self):
        f = io.StringIO()
        result = _process_requirement_line("# comment", {}, f, {}, strip_specifiers=True)
        assert result is False

    def test_empty_lines_skipped(self):
        f = io.StringIO()
        result = _process_requirement_line("", {}, f, {}, strip_specifiers=True)
        assert result is False
