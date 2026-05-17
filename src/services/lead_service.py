from __future__ import annotations

import logging

from src.models import JobRecord, RecruiterLead
from src.services.google_search_service import GoogleSearchService
from src.services.hunter_service import HunterService
from src.services.snov_service import SnovService


class LeadService:
    """
    Recruiter sourcing workflow:
    1. Google LinkedIn recruiter search -> Hunter email finder (by name)
    2. Hunter domain search (HR department)
    3. Snov.io fallback
    """

    def __init__(
        self,
        hunter: HunterService,
        snov: SnovService | None,
        google_search: GoogleSearchService | None,
        logger: logging.Logger,
    ) -> None:
        self._hunter = hunter
        self._snov = snov
        self._google_search = google_search
        self._logger = logger

    def find_recruiter_for_job(self, job: JobRecord) -> RecruiterLead:
        company_name = job.company_info.name or job.company

        lead = self._try_google_and_hunter_email_finder(company_name)
        if lead.email:
            return lead

        lead = self._try_hunter_domain_search(company_name)
        if lead.email:
            return lead

        return self._try_snov_fallback(company_name, lead)

    def find_recruiter_for_company(self, company_name: str) -> RecruiterLead:
        """Backward-compatible entry point."""
        return self.find_recruiter_for_job(
            JobRecord(
                job_id="",
                title="",
                company=company_name,
                description="",
                job_url="",
                application_url="",
            )
        )

    def _try_google_and_hunter_email_finder(self, company_name: str) -> RecruiterLead:
        if not self._google_search:
            return RecruiterLead()

        try:
            candidates = self._google_search.find_recruiter_candidates(company_name)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Google recruiter search failed for %s: %s", company_name, exc)
            return RecruiterLead()

        for candidate in candidates:
            try:
                lead = self._hunter.find_email_for_person(
                    company_name,
                    candidate.first_name,
                    candidate.last_name,
                )
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Hunter email finder failed for %s at %s: %s",
                    candidate.name,
                    company_name,
                    exc,
                )
                continue

            if lead.email:
                if not lead.name:
                    lead.name = candidate.name
                if not lead.title:
                    lead.title = candidate.title
                self._logger.info(
                    "Found recruiter via Google+Hunter for %s: %s",
                    company_name,
                    lead.email,
                )
                return self._tag_hunter_lead(lead, "hunter_email_finder")

        return RecruiterLead()

    def _try_hunter_domain_search(self, company_name: str) -> RecruiterLead:
        try:
            lead = self._hunter.find_recruiter_for_company(company_name)
            return self._tag_hunter_lead(lead, "hunter_domain")
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Hunter domain search failed for %s: %s", company_name, exc)
            return RecruiterLead()

    def _try_snov_fallback(self, company_name: str, hunter_lead: RecruiterLead) -> RecruiterLead:
        if not self._snov:
            return hunter_lead
        try:
            snov_lead = self._snov.find_recruiter_for_company(company_name)
            if snov_lead.email:
                snov_lead.lead_source = "snov"
                snov_lead.hunter_email = hunter_lead.hunter_email
                self._logger.info("Snov fallback found recruiter for %s", company_name)
                return snov_lead
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Snov fallback failed for %s: %s", company_name, exc)
        return hunter_lead

    @staticmethod
    def _tag_hunter_lead(lead: RecruiterLead, source: str) -> RecruiterLead:
        if lead.email:
            lead.hunter_email = lead.email
            lead.lead_source = source
        return lead
