from src.utils.validators import Validators


def test_has_non_empty_description_success() -> None:
    assert Validators.has_non_empty_description("Backend role with FastAPI")


def test_has_non_empty_description_empty() -> None:
    assert not Validators.has_non_empty_description("   ")


def test_parse_subject_and_body_success() -> None:
    draft = Validators.parse_subject_and_body("Subject: Application for SDE-1\n\nHello recruiter.")
    assert draft.is_valid
    assert draft.subject == "Application for SDE-1"
    assert "Hello recruiter." in draft.body


def test_parse_subject_and_body_missing_subject() -> None:
    draft = Validators.parse_subject_and_body("Hello recruiter.")
    assert not draft.is_valid
    assert draft.validation_error == "Missing Subject line"
