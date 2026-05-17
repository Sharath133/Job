from src.services.playwright_service import PlaywrightApplyService
from src.services.session_store import SessionStore


def test_classify_portal() -> None:
    service = PlaywrightApplyService(
        user_agent="Mozilla/5.0",
        resume_path="./resume.pdf",
        manual_review_dir="./manual_review",
        session_store=SessionStore("./session.json"),
    )
    assert service.classify_portal("https://jobs.lever.co/acme/123") == "lever"
    assert service.classify_portal("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"
    assert service.classify_portal("https://acme.workdayjobs.com/en-US/job/123") == "workday"
