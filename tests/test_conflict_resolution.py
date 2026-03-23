"""Tests for requirement version conflict resolution (Phase 2).

Tests _specifiers_conflict(), _resolve_conflicts(), real-world CI failure scenarios,
and _validate_and_relax() transitive conflict detection.
"""

from unittest.mock import MagicMock, patch

import pytest
from packaging.requirements import Requirement

from odoo_venv.main import (
    _UV_CONFLICT_PATTERN,
    ReqSource,
    TaggedRequirement,
    _collect_all_requirements,
    _get_exact_pin,
    _install_manifest_deps_best_effort,
    _resolve_conflicts,
    _specifiers_conflict,
    _tag_and_add,
    _validate_and_relax,
)


def _tagged(raw_line: str, source: ReqSource, origin: str = "test") -> TaggedRequirement:
    """Helper to create a TaggedRequirement from a raw line."""
    try:
        req = Requirement(raw_line)
    except Exception:
        req = None
    return TaggedRequirement(raw_line=raw_line, requirement=req, source=source, origin=origin)


# ---------------------------------------------------------------------------
# _get_exact_pin
# ---------------------------------------------------------------------------
class TestGetExactPin:
    def test_exact_pin(self):
        assert _get_exact_pin(Requirement("pkg==1.8")) == "1.8"

    def test_range_specifier(self):
        assert _get_exact_pin(Requirement("pkg>=1.0")) is None

    def test_bare_name(self):
        assert _get_exact_pin(Requirement("pkg")) is None

    def test_compound_specifier(self):
        # >=1.0,<2.0 has two specifiers, not a single ==
        assert _get_exact_pin(Requirement("pkg>=1.0,<2.0")) is None


# ---------------------------------------------------------------------------
# _specifiers_conflict
# ---------------------------------------------------------------------------
class TestSpecifiersConflict:
    def test_exact_vs_higher_range(self):
        """==1.8 vs >=1.16 → conflict (1.8 doesn't satisfy >=1.16)."""
        assert _specifiers_conflict(Requirement("pkg==1.8"), Requirement("pkg>=1.16")) is True

    def test_different_exact_pins(self):
        """==2.20.0 vs ==2.21.0 → conflict."""
        assert _specifiers_conflict(Requirement("pkg==2.20.0"), Requirement("pkg==2.21.0")) is True

    def test_compatible_ranges(self):
        """>=1.0 vs >=2.0 → no conflict (any version >=2.0 satisfies both)."""
        assert _specifiers_conflict(Requirement("pkg>=1.0"), Requirement("pkg>=2.0")) is False

    def test_exact_within_range(self):
        """==1.8 vs >=1.0,<2.0 → no conflict (1.8 satisfies the range)."""
        assert _specifiers_conflict(Requirement("pkg==1.8"), Requirement("pkg>=1.0,<2.0")) is False

    def test_bare_vs_anything(self):
        """No specifier → never conflicts."""
        assert _specifiers_conflict(Requirement("pkg"), Requirement("pkg==1.0")) is False

    def test_both_bare(self):
        assert _specifiers_conflict(Requirement("pkg"), Requirement("pkg")) is False

    def test_same_exact_pin(self):
        """==1.8 vs ==1.8 → no conflict."""
        assert _specifiers_conflict(Requirement("pkg==1.8"), Requirement("pkg==1.8")) is False


# ---------------------------------------------------------------------------
# _resolve_conflicts
# ---------------------------------------------------------------------------
class TestResolveConflicts:
    def test_preset_wins_with_version(self):
        """Versioned PRESET entry drops BASE and ADDON entries."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.8", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.16", ReqSource.ADDON, "web/__manifest__.py"),
                _tagged("python-stdnum>=2.0", ReqSource.PRESET, "extra_requirements"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["python-stdnum>=2.0"]

    def test_bare_preset_does_not_override(self):
        """Bare PRESET entry (no version) doesn't drop BASE pin."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.8", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum", ReqSource.PRESET, "extra_requirements"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert "python-stdnum==1.8" in result
        assert "python-stdnum" in result

    def test_addon_vs_base_conflict_drops_base(self):
        """When addon and base conflict, base is dropped."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.8", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.16", ReqSource.ADDON, "web/__manifest__.py"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["python-stdnum>=1.16"]

    def test_no_conflict_keeps_all(self):
        """Compatible entries from different sources are all kept."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.8", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.0,<2.0", ReqSource.ADDON, "web/__manifest__.py"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert "python-stdnum==1.8" in result
        assert "python-stdnum>=1.0,<2.0" in result

    def test_deduplication(self):
        """Identical lines from multiple sources are deduplicated."""
        req_map = {
            "requests": [
                _tagged("requests==2.28.0", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("requests==2.28.0", ReqSource.ADDON, "addon/requirements.txt"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["requests==2.28.0"]

    def test_single_source_passthrough(self):
        """Single-source entries pass through without conflict check."""
        req_map = {
            "lxml": [_tagged("lxml==4.9.3", ReqSource.BASE, "odoo/requirements.txt")],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["lxml==4.9.3"]


# ---------------------------------------------------------------------------
# Real-world CI failure scenarios
# ---------------------------------------------------------------------------
class TestRealWorldScenarios:
    """Reproduce the 5 Category 1 CI failures from the brainstorm report."""

    def test_odoo_12_requests_conflict(self):
        """12.0: requests==2.20.0 (base) vs ==2.21.0 (addon dir) → addon wins."""
        req_map = {
            "requests": [
                _tagged("requests==2.20.0", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("requests==2.21.0", ReqSource.ADDON, "oca/requirements.txt"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["requests==2.21.0"]

    def test_odoo_14_stdnum_conflict(self):
        """14.0: python-stdnum==1.8 (base) vs >=1.16 (manifest) → addon wins."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.8", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.16", ReqSource.ADDON, "l10n_eu_oss/__manifest__.py"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["python-stdnum>=1.16"]

    def test_odoo_15_stdnum_conflict(self):
        """15.0: python-stdnum==1.13 (base) vs >=1.18 (manifest) → addon wins."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.13", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.18", ReqSource.ADDON, "l10n_eu_oss/__manifest__.py"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["python-stdnum>=1.18"]

    def test_odoo_17_stdnum_conflict(self):
        """17.0: python-stdnum==1.17 (base) vs >=1.18 (manifest) → addon wins."""
        req_map = {
            "python-stdnum": [
                _tagged("python-stdnum==1.17", ReqSource.BASE, "odoo/requirements.txt"),
                _tagged("python-stdnum>=1.18", ReqSource.ADDON, "l10n_eu_oss/__manifest__.py"),
            ],
        }
        result = _resolve_conflicts(req_map)
        assert result == ["python-stdnum>=1.18"]

    @pytest.mark.parametrize(
        "base_pin, addon_req",
        [
            ("python-stdnum==1.8", "python-stdnum>=1.16"),
            ("requests==2.20.0", "requests==2.21.0"),
        ],
        ids=["range_vs_pin", "pin_vs_pin"],
    )
    def test_verbose_warns_on_relaxed_pin(self, base_pin, addon_req, capsys):
        """Verbose mode emits warning when a base pin is relaxed."""
        pkg_name = Requirement(base_pin).name.lower()
        req_map = {
            pkg_name: [
                _tagged(base_pin, ReqSource.BASE),
                _tagged(addon_req, ReqSource.ADDON),
            ],
        }
        _resolve_conflicts(req_map, verbose=True)
        captured = capsys.readouterr()
        assert "Relaxed Odoo's" in captured.out
        assert base_pin in captured.out


# ---------------------------------------------------------------------------
# _UV_CONFLICT_PATTERN
# ---------------------------------------------------------------------------
class TestUvConflictPattern:
    def test_matches_standard_error(self):
        m = _UV_CONFLICT_PATTERN.search("you require requests==2.21.0")
        assert m and m.group(1) == "requests" and m.group(2) == "2.21.0"

    def test_no_match_on_unrelated_error(self):
        assert _UV_CONFLICT_PATTERN.search("network timeout") is None

    def test_matches_multiline_wrapped_output(self):
        """uv wraps long lines — 'you\\n      require' must still match."""
        stderr = (
            "  × No solution found when resolving dependencies:\n"
            "  ╰─▶ Because matplotlib==3.4.1 depends on pyparsing>=2.2.1 and you\n"
            "      require pyparsing==2.2.0, we can conclude that your requirements and\n"
            "      matplotlib==3.4.1 are incompatible."
        )
        m = _UV_CONFLICT_PATTERN.search(stderr)
        assert m is not None
        # Must match the FIRST 'you require' (pyparsing), not the second (matplotlib)
        assert m.group(1) == "pyparsing"
        assert m.group(2) == "2.2.0"

    def test_no_trailing_comma_in_version(self):
        """Version capture must not include trailing punctuation."""
        m = _UV_CONFLICT_PATTERN.search("you require matplotlib==3.4.1, we can conclude")
        assert m is not None
        assert m.group(2) == "3.4.1"  # no trailing comma


# ---------------------------------------------------------------------------
# _validate_and_relax
# ---------------------------------------------------------------------------
def _mock_compile_result(rc, stderr=""):
    """Create a mock subprocess.CompletedProcess for uv pip compile."""
    result = MagicMock()
    result.returncode = rc
    result.stderr = stderr
    result.stdout = ""
    return result


class TestValidateAndRelax:
    """Tests for _validate_and_relax() — the uv pip compile validation loop."""

    @patch("odoo_venv.main.subprocess.run")
    def test_compile_succeeds_no_relaxation(self, mock_run, tmp_path):
        """When compile succeeds on first try, no pins are relaxed."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.21.0\nlxml==4.9.3\n")
        mock_run.return_value = _mock_compile_result(0)

        relaxed = _validate_and_relax(str(req_file), python_version="3.10", base_pins={"requests"})

        assert relaxed == set()
        assert "requests==2.21.0" in req_file.read_text()

    @patch("odoo_venv.main.subprocess.run")
    def test_single_base_pin_relaxed(self, mock_run, tmp_path):
        """A conflicting BASE pin is removed and compile retried."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.21.0\nklaviyo-api\nlxml==4.9.3\n")
        mock_run.side_effect = [
            _mock_compile_result(1, "you require requests==2.21.0"),
            _mock_compile_result(0),
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.7", base_pins={"requests"})

        assert relaxed == {"requests"}
        contents = req_file.read_text()
        assert "requests" not in contents
        assert "lxml==4.9.3" in contents

    @patch("odoo_venv.main.subprocess.run")
    def test_multiple_base_pins_relaxed(self, mock_run, tmp_path):
        """Two sequential conflicts — two pins relaxed across two retries."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.21.0\npyparsing==2.2.0\nmatplotlib\n")
        mock_run.side_effect = [
            _mock_compile_result(1, "you require requests==2.21.0"),
            _mock_compile_result(1, "you require pyparsing==2.2.0"),
            _mock_compile_result(0),
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.7", base_pins={"requests", "pyparsing"})

        assert relaxed == {"requests", "pyparsing"}
        contents = req_file.read_text()
        assert "requests" not in contents
        assert "pyparsing" not in contents
        assert "matplotlib" in contents

    @patch("odoo_venv.main.subprocess.run")
    def test_non_base_pin_not_relaxed(self, mock_run, tmp_path):
        """Conflict on a non-BASE pin — no relaxation, returns empty set."""
        req_file = tmp_path / "requirements.txt"
        original = "requests==2.21.0\nlxml==4.9.3\n"
        req_file.write_text(original)
        mock_run.return_value = _mock_compile_result(1, "you require requests==2.21.0")

        relaxed = _validate_and_relax(
            str(req_file),
            python_version="3.10",
            base_pins={"lxml"},  # requests NOT in base_pins
        )

        assert relaxed == set()
        assert req_file.read_text() == original

    @patch("odoo_venv.main.subprocess.run")
    def test_max_retries_exceeded(self, mock_run, tmp_path):
        """When max_retries is exhausted, returns what was relaxed so far."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("a==1\nb==1\nc==1\n")
        # Each retry hits a different package — after max_retries=2, stops
        mock_run.side_effect = [
            _mock_compile_result(1, "you require a==1"),
            _mock_compile_result(1, "you require b==1"),
            # max_retries=2 means only 2 iterations
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.10", base_pins={"a", "b", "c"}, max_retries=2)

        assert relaxed == {"a", "b"}

    @patch("odoo_venv.main.subprocess.run")
    def test_unparseable_error_falls_through(self, mock_run, tmp_path):
        """When stderr doesn't match the conflict pattern, returns immediately."""
        req_file = tmp_path / "requirements.txt"
        original = "requests==2.21.0\n"
        req_file.write_text(original)
        mock_run.return_value = _mock_compile_result(1, "some random error from uv")

        relaxed = _validate_and_relax(str(req_file), python_version="3.10", base_pins={"requests"})

        assert relaxed == set()
        assert req_file.read_text() == original

    @patch("odoo_venv.main.subprocess.run")
    def test_warning_emitted_on_relaxation(self, mock_run, tmp_path, capsys):
        """A user-visible warning is printed when a pin is relaxed."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.21.0\nklaviyo-api\n")
        mock_run.side_effect = [
            _mock_compile_result(1, "you require requests==2.21.0"),
            _mock_compile_result(0),
        ]

        _validate_and_relax(str(req_file), python_version="3.7", base_pins={"requests"})

        captured = capsys.readouterr()
        assert "Relaxed Odoo's" in captured.out
        assert "requests==2.21.0" in captured.out

    @patch("odoo_venv.main.subprocess.run")
    def test_real_world_klaviyo_conflict(self, mock_run, tmp_path):
        """Simulate the actual Odoo 12.0 failure: requests==2.21.0 vs klaviyo-api."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.21.0\nklaviyo-api\nwerkzeug==0.16.1\n")
        mock_run.side_effect = [
            _mock_compile_result(1, "you require requests==2.21.0"),
            _mock_compile_result(0),
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.7", base_pins={"requests", "werkzeug"})

        assert "requests" in relaxed
        assert "werkzeug" not in relaxed

    @patch("odoo_venv.main.subprocess.run")
    def test_real_world_pillow_conflict(self, mock_run, tmp_path):
        """Simulate 13.0 failure: pillow==5.4.1 vs matplotlib==3.4.1."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pillow==5.4.1\nmatplotlib==3.4.1\nlxml==4.9.3\n")
        mock_run.side_effect = [
            _mock_compile_result(1, "you require pillow==5.4.1"),
            _mock_compile_result(0),
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.7", base_pins={"pillow", "lxml"})

        assert "pillow" in relaxed
        contents = req_file.read_text()
        assert "pillow" not in contents
        assert "lxml==4.9.3" in contents

    @patch("odoo_venv.main.subprocess.run")
    def test_real_world_pyparsing_multiline_conflict(self, mock_run, tmp_path):
        """Simulate 13.0 failure where uv wraps 'you\\n      require pyparsing==2.2.0'."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pyparsing==2.2.0\nmatplotlib==3.4.1\nlxml==4.9.3\n")
        # Reproduce uv's actual wrapped output
        stderr = (
            "  × No solution found when resolving dependencies:\n"
            "  ╰─▶ Because matplotlib==3.4.1 depends on pyparsing>=2.2.1 and you\n"
            "      require pyparsing==2.2.0, we can conclude that your requirements and\n"
            "      matplotlib==3.4.1 are incompatible.\n"
            "      And because you require matplotlib==3.4.1, we can conclude that your\n"
            "      requirements are unsatisfiable."
        )
        mock_run.side_effect = [
            _mock_compile_result(1, stderr),
            _mock_compile_result(0),
        ]

        relaxed = _validate_and_relax(str(req_file), python_version="3.7", base_pins={"pyparsing", "lxml"})

        assert "pyparsing" in relaxed
        contents = req_file.read_text()
        assert "pyparsing" not in contents
        assert "matplotlib==3.4.1" in contents


# ---------------------------------------------------------------------------
# _collect_all_requirements — manifest-only dep separation
# ---------------------------------------------------------------------------
class TestManifestDepsSeparation:
    """Tests for the manifest-only deps split in _collect_all_requirements."""

    def _make_manifest(self, tmp_path, deps):
        """Create a minimal __manifest__.py with external_dependencies."""
        mf = tmp_path / "__manifest__.py"
        mf.write_text(str({"external_dependencies": {"python": deps}}))
        return mf

    def _make_req_file(self, tmp_path, name, lines):
        """Create a requirements.txt file."""
        f = tmp_path / name
        f.write_text("\n".join(lines) + "\n")
        return f

    def _target_env(self):
        from packaging.markers import default_environment

        return default_environment()

    def test_manifest_only_dep_separated(self, tmp_path):
        """Dep in manifest but NOT in any req file → goes to manifest_only_deps."""
        base_req = self._make_req_file(tmp_path, "base.txt", ["lxml==4.9.3"])
        mf = self._make_manifest(tmp_path, ["python-ldap"])
        parsed = {mf: {"external_dependencies": {"python": ["python-ldap"]}}}

        req_map, manifest_only = _collect_all_requirements(
            base_req_files=[base_req],
            addons_req_files=[],
            extra_requirements=None,
            extra_requirements_file=None,
            manifest_files=[mf],
            parsed_manifests=parsed,
            ignored_req_map={},
            target_env=self._target_env(),
        )

        assert "python-ldap" in manifest_only
        assert "python-ldap" not in req_map

    def test_manifest_dep_in_req_file_stays_in_main(self, tmp_path):
        """Dep in both manifest AND req file → stays in main req_map, not manifest_only."""
        base_req = self._make_req_file(tmp_path, "base.txt", ["lxml==4.9.3"])
        addon_req = self._make_req_file(tmp_path, "addon.txt", ["python-ldap>=3.0"])
        mf = self._make_manifest(tmp_path, ["python-ldap"])
        parsed = {mf: {"external_dependencies": {"python": ["python-ldap"]}}}

        req_map, manifest_only = _collect_all_requirements(
            base_req_files=[base_req],
            addons_req_files=[addon_req],
            extra_requirements=None,
            extra_requirements_file=None,
            manifest_files=[mf],
            parsed_manifests=parsed,
            ignored_req_map={},
            target_env=self._target_env(),
        )

        assert "python-ldap" not in manifest_only
        assert "python-ldap" in req_map

    def test_ignored_manifest_dep_excluded(self, tmp_path):
        """Dep in ignored_req_map → excluded from both req_map and manifest_only."""
        base_req = self._make_req_file(tmp_path, "base.txt", ["lxml==4.9.3"])
        mf = self._make_manifest(tmp_path, ["python-ldap"])
        parsed = {mf: {"external_dependencies": {"python": ["python-ldap"]}}}
        ignored = {"python-ldap": [Requirement("python-ldap")]}

        req_map, manifest_only = _collect_all_requirements(
            base_req_files=[base_req],
            addons_req_files=[],
            extra_requirements=None,
            extra_requirements_file=None,
            manifest_files=[mf],
            parsed_manifests=parsed,
            ignored_req_map=ignored,
            target_env=self._target_env(),
        )

        assert "python-ldap" not in manifest_only
        assert "python-ldap" not in req_map


# ---------------------------------------------------------------------------
# _install_manifest_deps_best_effort
# ---------------------------------------------------------------------------
class TestInstallManifestDepsBestEffort:
    """Tests for the best-effort manifest dep installer."""

    @patch("odoo_venv.main._run_command")
    def test_all_deps_install_successfully(self, mock_run, tmp_path):
        """All deps succeed → empty skipped list."""
        mock_run.return_value = None  # no error

        skipped = _install_manifest_deps_best_effort(["python-ldap", "pymssql"], venv_dir=tmp_path, verbose=False)

        assert skipped == []
        assert mock_run.call_count == 2

    @patch("odoo_venv.main._run_command")
    def test_one_dep_fails_others_continue(self, mock_run, tmp_path):
        """One failure → that dep in skipped, others installed."""
        import subprocess as sp

        mock_run.side_effect = [
            None,  # python-ldap succeeds
            sp.CalledProcessError(1, "uv"),  # pymssql fails
            None,  # pyyaml succeeds
        ]

        skipped = _install_manifest_deps_best_effort(
            ["python-ldap", "pymssql", "pyyaml"],
            venv_dir=tmp_path,
            verbose=False,
        )

        assert skipped == ["pymssql"]
        assert mock_run.call_count == 3

    @patch("odoo_venv.main._run_command")
    def test_warning_emitted_on_skip(self, mock_run, tmp_path, capsys):
        """Skipped dep emits a warning message."""
        import subprocess as sp

        mock_run.side_effect = sp.CalledProcessError(1, "uv")

        _install_manifest_deps_best_effort(["python-ldap"], venv_dir=tmp_path, verbose=False)

        captured = capsys.readouterr()
        assert "python-ldap" in captured.out
        assert "failed to install" in captured.out


# ---------------------------------------------------------------------------
# _tag_and_add — PRESET entries bypass ignored_req_map
# ---------------------------------------------------------------------------
class TestTagAndAddPresetBypass:
    """PRESET entries must never be filtered by _is_ignored.

    Regression test: auto-ignore adds a bare Requirement("python-ldap") to
    ignored_req_map when the user's extra_requirement overrides Odoo's pin.
    The old code passed ignored_req_map={} for extra_requirements, so PRESET
    entries were never dropped.  The new _tag_and_add must preserve this.
    """

    def test_preset_not_filtered_by_bare_ignore(self):
        """PRESET python-ldap==3.4.2 must pass through even with bare ignore."""
        from collections import defaultdict

        req_map = defaultdict(list)
        # Simulate auto-ignore adding bare Requirement("python-ldap")
        ignored = {"python-ldap": [Requirement("python-ldap")]}

        _tag_and_add(
            req_map,
            "python-ldap==3.4.2",
            Requirement("python-ldap==3.4.2"),
            ReqSource.PRESET,
            "extra_requirements",
            ignored,
        )

        assert "python-ldap" in req_map
        assert req_map["python-ldap"][0].raw_line == "python-ldap==3.4.2"

    def test_base_still_filtered_by_bare_ignore(self):
        """BASE entries should still be filtered by bare ignore."""
        from collections import defaultdict

        req_map = defaultdict(list)
        ignored = {"python-ldap": [Requirement("python-ldap")]}

        _tag_and_add(
            req_map,
            "python-ldap==3.4.0",
            Requirement("python-ldap==3.4.0"),
            ReqSource.BASE,
            "odoo/requirements.txt",
            ignored,
        )

        assert "python-ldap" not in req_map

    def test_addon_still_filtered_by_bare_ignore(self):
        """ADDON entries should still be filtered by bare ignore."""
        from collections import defaultdict

        req_map = defaultdict(list)
        ignored = {"python-ldap": [Requirement("python-ldap")]}

        _tag_and_add(
            req_map,
            "python-ldap==3.4.0",
            Requirement("python-ldap==3.4.0"),
            ReqSource.ADDON,
            "some/__manifest__.py",
            ignored,
        )

        assert "python-ldap" not in req_map
