from src.utils.domain_utils import guess_domain_from_company


def test_guess_domain_strips_suffixes() -> None:
    assert guess_domain_from_company("Acme Technologies Inc") == "acme.com"


def test_guess_domain_preserves_existing_domain() -> None:
    assert guess_domain_from_company("jobs.acme.com") == "jobs.acme.com"
