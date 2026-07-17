import json

from sorena.tools import jobscout_tool

PROFILE = {
    "target_roles": ["AI Engineer"],
    "skills": {"strong": ["Python", "FastAPI"], "learning": ["LangGraph"]},
    "location": {"base": "Italy", "remote": "preferred", "hybrid": "acceptable"},
    "languages": ["English"],
    "dealbreakers": ["onsite in the US"],
    "salary_floor": None,
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _job(company="Acme", title="AI Engineer", location="Worldwide", description=""):
    return {
        "company_name": company,
        "title": title,
        "candidate_required_location": location,
        "description": description,
        "url": "https://example.com/job",
        "job_type": "full_time",
    }


def test_score_job_rewards_role_and_skill_matches():
    job = _job(title="AI Engineer", description="You'll use Python and FastAPI daily.")
    score = jobscout_tool.score_job(job, PROFILE)
    assert score > 0


def test_score_job_penalizes_dealbreaker_location():
    matching_job = _job(location="Worldwide", description="Python FastAPI AI Engineer")
    dealbreaker_job = _job(location="onsite in the US", description="Python FastAPI AI Engineer")
    assert jobscout_tool.score_job(dealbreaker_job, PROFILE) < jobscout_tool.score_job(
        matching_job, PROFILE
    )


def test_score_job_is_clamped_to_0_100():
    empty_job = _job(title="", description="")
    assert 0 <= jobscout_tool.score_job(empty_job, PROFILE) <= 100


def test_dedupe_hash_is_case_and_whitespace_insensitive():
    a = jobscout_tool._dedupe_hash("Acme Inc", "AI Engineer", "Worldwide")
    b = jobscout_tool._dedupe_hash(" acme inc ", "ai engineer", "worldwide")
    assert a == b


def test_load_profile_reads_yaml(tmp_path, monkeypatch):
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))  # valid YAML is valid JSON
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)

    loaded = jobscout_tool.load_profile()

    assert loaded["target_roles"] == ["AI Engineer"]


def test_load_profile_missing_file_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", tmp_path / "does_not_exist.yaml")

    try:
        jobscout_tool.load_profile()
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError as e:
        assert "profile.yaml" in str(e) or "does_not_exist" in str(e)


def test_search_and_score_jobs_saves_new_and_dedupes_on_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)

    jobs_payload = {"jobs": [_job(company="Acme", title="AI Engineer")]}
    monkeypatch.setattr(
        jobscout_tool.requests, "get", lambda url, params, timeout: FakeResponse(jobs_payload)
    )

    first = jobscout_tool.search_and_score_jobs("AI Engineer")
    assert "Acme" in first

    second = jobscout_tool.search_and_score_jobs("AI Engineer")
    assert "No new postings" in second


def test_grade_for_boundaries():
    assert jobscout_tool._grade_for(90) == "A"
    assert jobscout_tool._grade_for(89) == "B"
    assert jobscout_tool._grade_for(80) == "B"
    assert jobscout_tool._grade_for(79) == "C"
    assert jobscout_tool._grade_for(70) == "C"
    assert jobscout_tool._grade_for(69) == "D"
    assert jobscout_tool._grade_for(60) == "D"
    assert jobscout_tool._grade_for(59) == "F"
    assert jobscout_tool._grade_for(0) == "F"


def test_save_job_match_score_computes_overall_and_grade_from_components(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")

    result = jobscout_tool.save_job_match_score(
        company="Acme",
        title="AI Engineer",
        skills_match=28,
        experience_fit=18,
        salary_alignment=14,
        industry_relevance=14,
        location_fit=9,
        growth_potential=9,
        interview_chance="High",
    )

    # 28+18+14+14+9+9 = 92 -> grade A
    assert "92/100" in result
    assert "grade A" in result


def test_get_job_match_history_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")

    jobscout_tool.save_job_match_score(
        company="First",
        title="Role1",
        skills_match=10,
        experience_fit=10,
        salary_alignment=5,
        industry_relevance=5,
        location_fit=5,
        growth_potential=5,
        interview_chance="Low",
    )
    jobscout_tool.save_job_match_score(
        company="Second",
        title="Role2",
        skills_match=30,
        experience_fit=20,
        salary_alignment=15,
        industry_relevance=15,
        location_fit=10,
        growth_potential=10,
        interview_chance="High",
    )

    history = jobscout_tool.get_job_match_history()
    lines = history.splitlines()
    assert "Second" in lines[0]
    assert "First" in lines[1]


def test_get_job_match_history_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")

    assert jobscout_tool.get_job_match_history() == "No match scores saved yet."


def test_get_recent_job_match_scores_within_window(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    jobscout_tool.save_job_match_score(
        company="Acme",
        title="AI Engineer",
        skills_match=30,
        experience_fit=20,
        salary_alignment=15,
        industry_relevance=15,
        location_fit=10,
        growth_potential=10,
        interview_chance="High",
    )

    scores = jobscout_tool.get_recent_job_match_scores(days=7)

    assert scores == [(scores[0][0], "A")]


def test_get_recent_job_match_scores_excludes_older_than_window(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    jobscout_tool.save_job_match_score(
        company="Acme",
        title="AI Engineer",
        skills_match=10,
        experience_fit=5,
        salary_alignment=5,
        industry_relevance=5,
        location_fit=5,
        growth_potential=5,
        interview_chance="Low",
    )

    conn = jobscout_tool._connect()
    conn.execute("UPDATE job_match_scores SET scored_at = datetime('now', '-30 days')")
    conn.commit()
    conn.close()

    assert jobscout_tool.get_recent_job_match_scores(days=7) == []


def test_get_recent_job_match_scores_empty_when_none_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")

    assert jobscout_tool.get_recent_job_match_scores() == []


def test_get_cv_reads_configured_path(tmp_path, monkeypatch):
    cv_file = tmp_path / "cv.md"
    cv_file.write_text("# Ash Dorkian\nSenior Engineer")
    monkeypatch.setattr(jobscout_tool, "CV_PATH", cv_file)
    monkeypatch.setattr(jobscout_tool, "CV_PATH_FALLBACK", tmp_path / "does_not_exist.md")

    assert "Senior Engineer" in jobscout_tool.get_cv()


def test_get_cv_falls_back_when_primary_missing(tmp_path, monkeypatch):
    fallback = tmp_path / "fallback.md"
    fallback.write_text("fallback CV text")
    monkeypatch.setattr(jobscout_tool, "CV_PATH", tmp_path / "does_not_exist.md")
    monkeypatch.setattr(jobscout_tool, "CV_PATH_FALLBACK", fallback)

    assert "fallback CV text" in jobscout_tool.get_cv()


def test_get_cv_missing_both_reports_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "CV_PATH", tmp_path / "a.md")
    monkeypatch.setattr(jobscout_tool, "CV_PATH_FALLBACK", tmp_path / "b.md")

    assert "No CV file found" in jobscout_tool.get_cv()


def test_get_job_posting_finds_by_company_substring(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)
    monkeypatch.setattr(
        jobscout_tool.requests,
        "get",
        lambda url, params, timeout: FakeResponse(
            {"jobs": [_job(company="Aruba", title="AI Engineer", description="Work on AI stuff")]}
        ),
    )
    jobscout_tool.search_and_score_jobs("engineer")

    result = jobscout_tool.get_job_posting("aruba")

    assert "Aruba" in result
    assert "Work on AI stuff" in result


def test_get_job_posting_no_match(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")

    assert "No stored posting matches" in jobscout_tool.get_job_posting("nonexistent")


def test_find_skill_gap_picks_most_mentioned_learning_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))  # learning: ["LangGraph"]
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)
    monkeypatch.setattr(
        jobscout_tool.requests,
        "get",
        lambda url, params, timeout: FakeResponse(
            {
                "jobs": [
                    _job(company="A", title="X", description="needs LangGraph experience"),
                    _job(company="B", title="Y", description="needs LangGraph too"),
                    _job(company="C", title="Z", description="no relevant skills mentioned"),
                ]
            }
        ),
    )
    jobscout_tool.search_and_score_jobs("engineer")

    gap = jobscout_tool.find_skill_gap()

    assert gap == ("LangGraph", 2, 3)


def test_find_skill_gap_none_when_no_postings(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)

    assert jobscout_tool.find_skill_gap() is None


def test_find_skill_gap_none_when_zero_mentions(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)
    monkeypatch.setattr(
        jobscout_tool.requests,
        "get",
        lambda url, params, timeout: FakeResponse(
            {"jobs": [_job(company="A", title="X", description="totally unrelated content")]}
        ),
    )
    jobscout_tool.search_and_score_jobs("engineer")

    assert jobscout_tool.find_skill_gap() is None


def test_get_skill_gap_formats_the_finding(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "find_skill_gap", lambda: ("LangGraph", 7, 12))
    result = jobscout_tool.get_skill_gap()
    assert "LangGraph" in result
    assert "7 of 12" in result


def test_get_skill_gap_no_data_message(monkeypatch):
    monkeypatch.setattr(jobscout_tool, "find_skill_gap", lambda: None)
    assert "Not enough posting data" in jobscout_tool.get_skill_gap()


def test_search_and_score_jobs_reports_top_scored_not_first_raw(tmp_path, monkeypatch):
    # Regression: Remotive's API ignores the `limit` query param and always
    # returns every match. If `limit` were applied to the raw response
    # before scoring, a low-scoring job that happened to come first in
    # Remotive's own ordering would push out a better match ranked later.
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)

    jobs_payload = {
        "jobs": [
            _job(company="First", title="Barista", description="serve coffee"),
            _job(company="Second", title="Barista", description="serve coffee"),
            _job(
                company="BestMatch",
                title="AI Engineer",
                description="Python FastAPI AI Engineer LangGraph",
            ),
        ]
    }
    monkeypatch.setattr(
        jobscout_tool.requests, "get", lambda url, params, timeout: FakeResponse(jobs_payload)
    )

    result = jobscout_tool.search_and_score_jobs("engineer", limit=1)

    lines = result.splitlines()
    assert len(lines) == 1
    assert "BestMatch" in lines[0]


def test_search_and_score_jobs_sorts_by_score_descending(tmp_path, monkeypatch):
    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(jobscout_tool, "PROFILE_PATH", profile_file)

    jobs_payload = {
        "jobs": [
            _job(company="WeakMatch", title="Barista", description="serve coffee"),
            _job(
                company="StrongMatch",
                title="AI Engineer",
                description="Python FastAPI AI Engineer LangGraph",
            ),
        ]
    }
    monkeypatch.setattr(
        jobscout_tool.requests, "get", lambda url, params, timeout: FakeResponse(jobs_payload)
    )

    result = jobscout_tool.search_and_score_jobs("engineer")

    lines = result.splitlines()
    assert "StrongMatch" in lines[0]
    assert "WeakMatch" in lines[1]
