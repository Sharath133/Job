class FakeDomainResolver:
    """Returns a fixed domain for unit tests."""

    def __init__(self, domain: str = "acme.com") -> None:
        self._domain = domain

    def resolve_domain(self, company_name: str) -> str:
        return self._domain
