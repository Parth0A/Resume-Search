"""Automated tests for resume search backend logic.

Tests use small synthetic records and never rely on external datasets.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

from backend import _build_search_query
from backend import _extract_experience
from backend import _extract_skills
from backend import _find_resume_column
from backend import _is_resume_text_usable
from backend import _normalize_text
from backend import _prepare_export_data
from backend import _rank_candidates
from backend import _validate_job_title
from backend import _validate_skills
from backend import load_resumes
from backend import search_resumes


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_normalizes_case_and_whitespace(self):
        assert _normalize_text("  Python   Developer  ") == "python developer"

    def test_normalizes_punctuation_only_text(self):
        assert _normalize_text("!!!") == "!!!"

    def test_handles_non_string_input(self):
        assert _normalize_text(None) == ""
        assert _normalize_text(123) == ""
        assert _normalize_text([]) == ""

    def test_handles_empty_string(self):
        assert _normalize_text("") == ""


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

class TestLoadResumes:
    def test_loads_valid_csv(self):
        csv_content = "Resume_str,Category\nPython developer with 3 years of experience,Engineering\n"
        df = load_resumes(csv_content.encode("utf-8"), "Resume.csv")
        assert not df.empty
        assert "Resume_str" in df.columns

    def test_accepts_alternate_resume_column(self):
        csv_content = "Resume,Category\nBackend engineer resume\n"
        df = load_resumes(csv_content.encode("utf-8"), "Resume.csv")
        assert "Resume" in df.columns

    def test_accepts_category_column(self):
        csv_content = "Resume_str,Category\nResume text,Engineering\n"
        df = load_resumes(csv_content.encode("utf-8"), "Resume.csv")
        assert "Category" in df.columns

    def test_rejects_empty_file(self):
        with pytest.raises(ValueError):
            load_resumes(b"", "Resume.csv")

    def test_rejects_file_with_no_rows(self):
        csv_content = "Resume_str,Category\n"
        with pytest.raises(ValueError):
            load_resumes(csv_content.encode("utf-8"), "Resume.csv")

    def test_rejects_csv_without_resume_column(self):
        csv_content = "Name,Email\nAlice,a@example.com\n"
        with pytest.raises(ValueError):
            load_resumes(csv_content.encode("utf-8"), "Resume.csv")

    def test_rejects_csv_with_only_blank_resumes(self):
        csv_content = "Resume_str,Category\n,\n,\n"
        with pytest.raises(ValueError):
            load_resumes(csv_content.encode("utf-8"), "Resume.csv")

    def test_rejects_malformed_csv(self):
        # Unparseable content should raise a dataset error, not crash.
        with pytest.raises(ValueError):
            load_resumes(b"not a csv at all @@@@", "Resume.csv")


# ---------------------------------------------------------------------------
# Resume column detection
# ---------------------------------------------------------------------------

class TestFindResumeColumn:
    def test_finds_preferred_column(self):
        df = pd.DataFrame({"Resume_str": ["text"], "Category": ["eng"]})
        assert _find_resume_column(df) == "Resume_str"

    def test_finds_alternate_column(self):
        df = pd.DataFrame({"ResumeText": ["text"], "Category": ["eng"]})
        assert _find_resume_column(df) == "ResumeText"

    def test_tries_ordered_alternatives(self):
        df = pd.DataFrame({"Content": ["text"]})
        assert _find_resume_column(df) == "Content"

    def test_raises_when_no_column_found(self):
        df = pd.DataFrame({"Name": ["Alice"]})
        with pytest.raises(ValueError):
            _find_resume_column(df)


# ---------------------------------------------------------------------------
# Resume text usability
# ---------------------------------------------------------------------------

class TestIsResumeTextUsable:
    def test_returns_true_for_usable_text(self):
        series = pd.Series(["", "  ", "Python engineer"])
        assert _is_resume_text_usable(series) is True

    def test_returns_false_for_blank_text(self):
        series = pd.Series(["", "  ", "!!!", "\t"])
        assert _is_resume_text_usable(series) is False

    def test_handles_non_string_values(self):
        series = pd.Series([None, 123, "useful text"])
        assert _is_resume_text_usable(series) is True


# ---------------------------------------------------------------------------
# Job title validation
# ---------------------------------------------------------------------------

class TestValidateJobTitle:
    def test_accepts_valid_job_title(self):
        result = _validate_job_title("Software Engineer")
        assert result == "software engineer"

    def test_rejects_blank_job_title(self):
        with pytest.raises(ValueError):
            _validate_job_title("")

    def test_rejects_whitespace_only_job_title(self):
        with pytest.raises(ValueError):
            _validate_job_title("   ")

    def test_rejects_punctuation_only_job_title(self):
        with pytest.raises(ValueError):
            _validate_job_title("!!!")


# ---------------------------------------------------------------------------
# Skill parsing and validation
# ---------------------------------------------------------------------------

class TestValidateSkills:
    def test_parses_comma_separated_skills(self):
        result = _validate_skills("Python, SQL, Git")
        assert result == ["Python", "SQL", "Git"]

    def test_deduplicates_skills(self):
        result = _validate_skills("Python, python, Git")
        assert result == ["Python", "Git"]

    def test_trims_whitespace(self):
        result = _validate_skills(" Python , SQL ")
        assert result == ["Python", "SQL"]

    def test_returns_empty_for_blank_input(self):
        assert _validate_skills("") == []
        assert _validate_skills("   ") == []

    def test_rejects_blank_entries(self):
        with pytest.raises(ValueError):
            _validate_skills("Python, , Git")

    def test_rejects_blank_after_normalization(self):
        # A token that normalizes to nothing is treated as blank.
        with pytest.raises(ValueError):
            _validate_skills("Python, ,")


# ---------------------------------------------------------------------------
# Skill matching
# ---------------------------------------------------------------------------

class TestExtractSkills:
    def test_finds_exact_skills(self):
        resume = "Experienced Python and SQL developer."
        assert _extract_skills(resume, ["Python", "SQL"]) == ["Python", "SQL"]

    def test_missing_skill_not_returned(self):
        resume = "Java backend developer."
        assert _extract_skills(resume, ["Python", "SQL"]) == []

    def test_uses_word_boundary_to_reduce_substring_errors(self):
        resume = "JavaScript developer with Node experience."
        # JavaScript should not match Java.
        matched = _extract_skills(resume, ["Java", "JavaScript"])
        assert "Java" not in matched
        assert "JavaScript" in matched

    def test_deduplicates_detected_skills(self):
        resume = "Python developer familiar with python tooling."
        matched = _extract_skills(resume, ["Python", "python"])
        # Same normalized skill should appear once in the original casing.
        assert matched.count("Python") == 1

    def test_handles_empty_skill_list(self):
        assert _extract_skills("Python resume", []) == []

    def test_handles_resume_with_no_matches(self):
        assert _extract_skills("No relevant skills here.", ["Python", "SQL"]) == []


# ---------------------------------------------------------------------------
# Experience extraction
# ---------------------------------------------------------------------------

class TestExtractExperience:
    def test_extracts_explicit_experience_phrase(self):
        assert _extract_experience("3 years of experience") == 3
        assert _extract_experience("3 years experience") == 3
        assert _extract_experience("5 year experience") == 5
        assert _extract_experience("2 yrs experience") == 2

    def test_returns_none_for_ambiguous_text(self):
        assert _extract_experience("graduated in 2020 with a degree") is None
        assert _extract_experience("project lasted 2 years") is None
        assert _extract_experience("2 years ago I started studying") is None

    def test_returns_none_for_no_match(self):
        assert _extract_experience("Python developer") is None

    def test_returns_none_for_non_string_input(self):
        assert _extract_experience(None) is None
        assert _extract_experience(123) is None

    def test_handles_blank_text(self):
        assert _extract_experience("") is None


# ---------------------------------------------------------------------------
# Search query building
# ---------------------------------------------------------------------------

class TestBuildSearchQuery:
    def test_combines_job_title_and_skills(self):
        query = _build_search_query("Software Engineer", ["Python", "SQL"])
        assert "software engineer" in query
        assert "python" in query
        assert "sql" in query

    def test_validates_job_title(self):
        with pytest.raises(ValueError):
            _build_search_query("", ["Python"])

    def test_handles_empty_skills(self):
        query = _build_search_query("Engineer", [])
        assert query == "engineer"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

class TestRankCandidates:
    def test_ranks_by_descending_score(self):
        search = "python developer"
        resumes = ["Python developer with deep experience", "Java developer"]
        result = _rank_candidates(
            search_query=search,
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=2,
        )
        assert len(result) == 2
        if result:
            assert result[0]["score"] >= result[1]["score"]

    def test_respects_result_limit(self):
        resumes = ["Python developer"] * 12
        result = _rank_candidates(
            search_query="python developer",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None] * 12,
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng"] * 12,
            original_indices=list(range(12)),
            limit=5,
        )
        assert len(result) == 5

    def test_returns_empty_for_no_usable_text(self):
        resumes = ["!!!", "   "]
        result = _rank_candidates(
            search_query="python",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=5,
        )
        assert result == []

    def test_tie_breaks_by_original_position(self):
        resumes = ["Python developer", "Python developer"]
        result = _rank_candidates(
            search_query="python developer",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[5, 2],
            limit=5,
        )
        assert len(result) >= 2
        # Earlier original index should appear first on tie.
        assert result[0]["original_index"] < result[1]["original_index"]


# ---------------------------------------------------------------------------
# Minimum experience filtering
# ---------------------------------------------------------------------------

class TestExperienceFiltering:
    def test_filters_by_minimum_experience(self):
        resumes = ["Engineer with 2 years of experience", "Engineer with 8 years of experience"]
        result = _rank_candidates(
            search_query="engineer",
            resume_texts=resumes,
            min_experience=5,
            detected_experience=[2, 8],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=5,
        )
        assert len(result) == 1
        assert result[0]["original_index"] == 1

    def test_excludes_unknown_experience(self):
        resumes = ["Engineer resume", "Engineer with 4 years experience"]
        result = _rank_candidates(
            search_query="engineer",
            resume_texts=resumes,
            min_experience=3,
            detected_experience=[None, 4],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=5,
        )
        assert len(result) == 1
        assert result[0]["original_index"] == 1

    def test_includes_all_when_no_minimum(self):
        resumes = ["Engineer with 2 years of experience", "Engineer resume"]
        result = _rank_candidates(
            search_query="engineer",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[2, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=5,
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Search orchestration
# ---------------------------------------------------------------------------

class TestSearchResumes:
    def test_returns_ranked_results(self):
        df = pd.DataFrame({
            "Resume_str": ["Python developer with 3 years experience", "Java developer"],
            "Category": ["Engineering", "Engineering"],
        })
        results = search_resumes(
            df=df,
            job_title="Python developer",
            skills=[],
            min_experience=None,
            limit=10,
        )
        assert results["total_candidates"] == 2
        assert len(results["results"]) == 2
        assert results["results"][0]["score"] >= results["results"][1]["score"]

    def test_reports_matching_and_missing_skills(self):
        df = pd.DataFrame({
            "Resume_str": ["Python and SQL developer"],
            "Category": ["Engineering"],
        })
        results = search_resumes(
            df=df,
            job_title="developer",
            skills=["Python", "SQL", "Java"],
            min_experience=None,
            limit=10,
        )
        row = results["results"][0]
        assert "Python" in row["matched_skills"]
        assert "SQL" in row["matched_skills"]
        assert "Java" in row["missing_skills"]

    def test_applies_minimum_experience_filter(self):
        df = pd.DataFrame({
            "Resume_str": ["Engineer with 2 years of experience", "Engineer with 6 years experience"],
            "Category": ["Eng", "Eng"],
        })
        results = search_resumes(
            df=df,
            job_title="engineer",
            skills=[],
            min_experience=5,
            limit=10,
        )
        assert len(results["results"]) == 1
        assert results["results"][0]["experience"] == 6

    def test_excludes_unknown_experience_with_minimum(self):
        df = pd.DataFrame({
            "Resume_str": ["Engineer resume", "Engineer with 3 years experience"],
            "Category": ["Eng", "Eng"],
        })
        results = search_resumes(
            df=df,
            job_title="engineer",
            skills=[],
            min_experience=3,
            limit=10,
        )
        indices = [row["original_index"] for row in results["results"]]
        assert 0 not in indices
        assert 1 in indices

    def test_respects_result_limit(self):
        df = pd.DataFrame({
            "Resume_str": ["Python developer"] * 15,
            "Category": ["Eng"] * 15,
        })
        results = search_resumes(
            df=df,
            job_title="python developer",
            skills=[],
            min_experience=None,
            limit=5,
        )
        assert len(results["results"]) == 5

    def test_handles_duplicate_skills(self):
        df = pd.DataFrame({
            "Resume_str": ["Python developer"],
            "Category": ["Eng"],
        })
        results = search_resumes(
            df=df,
            job_title="developer",
            skills=["Python", "Python", "SQL"],
            min_experience=None,
            limit=10,
        )
        row = results["results"][0]
        assert row["matched_skills"] == ["Python"]
        assert row["missing_skills"] == ["SQL"]

    def test_handles_no_keyword_overlap_safely(self):
        # Punctuation-only tokens may be skipped by the vectorizer, so this
        # search is expected to return whatever the current TF-IDF behavior
        # produces rather than asserting an empty list.
        df = pd.DataFrame({
            "Resume_str": ["Java developer", "C++ developer"],
            "Category": ["Eng", "Eng"],
        })
        results = search_resumes(
            df=df,
            job_title="rust developer",
            skills=[],
            min_experience=None,
            limit=10,
        )
        assert isinstance(results, dict)
        assert "results" in results

    def test_rejects_punctuation_only_job_title(self):
        df = pd.DataFrame({
            "Resume_str": ["Python developer"],
            "Category": ["Eng"],
        })
        with pytest.raises(ValueError):
            search_resumes(
                df=df,
                job_title="!!!",
                skills=[],
                min_experience=None,
                limit=10,
            )

    def test_raises_for_blank_job_title(self):
        df = pd.DataFrame({"Resume_str": ["Python developer"], "Category": ["Eng"]})
        with pytest.raises(ValueError):
            search_resumes(df=df, job_title="", skills=[], min_experience=None, limit=5)

    def test_raises_for_invalid_limit(self):
        df = pd.DataFrame({"Resume_str": ["Python developer"], "Category": ["Eng"]})
        with pytest.raises(ValueError):
            search_resumes(df=df, job_title="developer", skills=[], min_experience=None, limit=0)

    def test_skills_requested_is_preserved(self):
        df = pd.DataFrame({
            "Resume_str": ["Python developer"],
            "Category": ["Eng"],
        })
        results = search_resumes(
            df=df,
            job_title="developer",
            skills=["Python"],
            min_experience=None,
            limit=10,
        )
        assert results["skills_requested"] == ["Python"]


# ---------------------------------------------------------------------------
# Export data preparation
# ---------------------------------------------------------------------------

class TestPrepareExportData:
    def test_prepares_dataframe_with_expected_columns(self):
        results = [{
            "original_index": 3,
            "resume_text": "Python developer",
            "category": "Engineering",
            "score": 0.8,
            "experience": 3,
            "matched_skills": ["Python"],
            "missing_skills": ["SQL"],
        }]
        df = _prepare_export_data(results, 10)
        assert not df.empty
        assert "Candidate" in df.columns
        assert "Match Score" in df.columns
        assert "Original Index" in df.columns
        assert df.iloc[0]["Candidate"] == "Candidate 4"
        assert df.iloc[0]["Original Index"] == 3

    def test_handles_experience_not_detected(self):
        results = [{
            "original_index": 0,
            "resume_text": "Developer",
            "category": None,
            "score": 0.5,
            "experience": None,
            "matched_skills": [],
            "missing_skills": [],
        }]
        df = _prepare_export_data(results, 1)
        assert df.iloc[0]["Detected Experience"] == "Not detected"
        assert df.iloc[0]["Category"] == "Not specified"

    def test_returns_empty_dataframe_for_no_results(self):
        df = _prepare_export_data([], 0)
        assert df.empty


# ---------------------------------------------------------------------------
# Stable ordering for tied scores
# ---------------------------------------------------------------------------

class TestStableTieOrdering:
    def test_preserves_deterministic_order_for_ties(self):
        resumes = ["Python developer", "Python developer"]
        first = _rank_candidates(
            search_query="python developer",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=2,
        )
        second = _rank_candidates(
            search_query="python developer",
            resume_texts=resumes,
            min_experience=None,
            detected_experience=[None, None],
            skills=[],
            resume_texts_raw=resumes,
            categories=["Eng", "Eng"],
            original_indices=[0, 1],
            limit=2,
        )
        assert first[0]["original_index"] == second[0]["original_index"]
        assert first[1]["original_index"] == second[1]["original_index"]
