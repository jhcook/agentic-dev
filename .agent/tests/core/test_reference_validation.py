# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for INFRA-060 reference extraction and validation."""



from agent.core.governance import (
    _extract_references,
    _parse_findings,
    _validate_references,
)


# --- _extract_references tests ---

class TestExtractReferences:
    def test_extracts_adr_ids(self):
        text = "This follows ADR-001 and ADR-023 guidelines."
        assert _extract_references(text) == ["ADR-001", "ADR-023"]

    def test_extracts_jrn_ids(self):
        text = "See JRN-045 for the journey definition."
        assert _extract_references(text) == ["JRN-045"]

    def test_extracts_exc_ids(self):
        text = "Exception granted per EXC-003."
        assert _extract_references(text) == ["EXC-003"]

    def test_extracts_mixed_ids(self):
        text = "ADR-001 applies, JRN-045 maps the journey, EXC-003 grants exception."
        result = _extract_references(text)
        assert result == ["ADR-001", "EXC-003", "JRN-045"]

    def test_deduplicates(self):
        text = "ADR-001 is referenced. See ADR-001 again. Also ADR-001."
        assert _extract_references(text) == ["ADR-001"]

    def test_empty_text(self):
        assert _extract_references("") == []
        assert _extract_references(None) == []

    def test_no_references(self):
        text = "This text has no governance references at all."
        assert _extract_references(text) == []

    def test_partial_match_ignored(self):
        """XADR-001 or ADR- without number should not match."""
        text = "Not a ref: XADR-001, ADR-, JRN-"
        assert _extract_references(text) == []

    def test_multiline_extraction(self):
        text = "REFERENCES:\n- ADR-001\n- JRN-045\n- EXC-003\nEND"
        result = _extract_references(text)
        assert result == ["ADR-001", "EXC-003", "JRN-045"]


# --- _validate_references tests ---

class TestValidateReferences:
    def test_valid_adr(self, tmp_path):
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        (adrs_dir / "ADR-001-some-decision.md").write_text("# ADR-001")
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir()

        valid, invalid = _validate_references(["ADR-001"], adrs_dir, journeys_dir)
        assert valid == ["ADR-001"]
        assert invalid == []

    def test_invalid_adr(self, tmp_path):
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir()

        valid, invalid = _validate_references(["ADR-999"], adrs_dir, journeys_dir)
        assert valid == []
        assert invalid == ["ADR-999"]

    def test_valid_jrn(self, tmp_path):
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        journeys_dir = tmp_path / "journeys"
        scope = journeys_dir / "INFRA"
        scope.mkdir(parents=True)
        (scope / "JRN-045-governance-hardening.yaml").write_text("id: JRN-045")

        valid, invalid = _validate_references(["JRN-045"], adrs_dir, journeys_dir)
        assert valid == ["JRN-045"]
        assert invalid == []

    def test_valid_exc(self, tmp_path):
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        (adrs_dir / "EXC-003-some-exception.md").write_text("# EXC-003")
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir()

        valid, invalid = _validate_references(["EXC-003"], adrs_dir, journeys_dir)
        assert valid == ["EXC-003"]
        assert invalid == []

    def test_mixed_valid_invalid(self, tmp_path):
        adrs_dir = tmp_path / "adrs"
        adrs_dir.mkdir()
        (adrs_dir / "ADR-001-real.md").write_text("# ADR-001")
        journeys_dir = tmp_path / "journeys"
        journeys_dir.mkdir()

        valid, invalid = _validate_references(
            ["ADR-001", "ADR-999", "JRN-999"], adrs_dir, journeys_dir
        )
        assert valid == ["ADR-001"]
        assert invalid == ["ADR-999", "JRN-999"]

    def test_missing_dirs(self, tmp_path):
        """Gracefully handle non-existent directories."""
        nonexistent = tmp_path / "nope"
        valid, invalid = _validate_references(["ADR-001"], nonexistent, nonexistent)
        assert valid == []
        assert invalid == ["ADR-001"]

    def test_empty_refs_list(self, tmp_path):
        valid, invalid = _validate_references([], tmp_path, tmp_path)
        assert valid == []
        assert invalid == []


# --- _parse_findings reference extraction ---

class TestParseFindingsReferences:
    def test_references_extracted_from_findings(self):
        review = (
            "VERDICT: PASS\n"
            "SUMMARY: All compliant per ADR-001.\n"
            "FINDINGS:\n- Follows ADR-001 architecture.\n"
            "REFERENCES:\n- ADR-001\n- JRN-045\n"
            "REQUIRED_CHANGES:\n"
        )
        result = _parse_findings(review)
        assert "references" in result
        assert "ADR-001" in result["references"]
        assert "JRN-045" in result["references"]

    def test_references_empty_when_none_cited(self):
        review = "VERDICT: PASS\nSUMMARY: No issues.\nFINDINGS:\n- None"
        result = _parse_findings(review)
        assert result["references"] == []

    def test_backward_compatible_result_keys(self):
        """Ensure the references key exists even in legacy-style output."""
        review = "VERDICT: PASS\nSUMMARY: OK"
        result = _parse_findings(review)
        assert "references" in result
        assert isinstance(result["references"], list)
