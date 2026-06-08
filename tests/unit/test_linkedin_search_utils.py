from src.utils.linkedin_search_utils import (
    build_recruiter_search_query,
    parse_recruiter_candidate,
)


def test_build_recruiter_search_query() -> None:
    query = build_recruiter_search_query("Tata Consultancy Services")
    assert "site:linkedin.com/in" in query
    assert '"Tata Consultancy Services"' in query
    assert '"Talent Acquisition"' in query
    assert '"Engineering Manager"' in query
    assert "India" in query


def test_parse_recruiter_candidate_from_google_result() -> None:
    candidate = parse_recruiter_candidate(
        title="Jane Doe - Technical Recruiter - Tata Consultancy Services | LinkedIn",
        snippet="Talent acquisition specialist at TCS",
        link="https://www.linkedin.com/in/jane-doe-123",
    )
    assert candidate is not None
    assert candidate.name == "Jane Doe"
    assert candidate.first_name == "Jane"
    assert candidate.last_name == "Doe"
