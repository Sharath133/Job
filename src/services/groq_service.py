from __future__ import annotations

import json

import requests

from src.models import EmailDraft, JobRecord
from src.utils.validators import Validators


class GroqService:
    """Runs scoring and email drafting prompts against Groq."""

    _url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def score_job(self, job: JobRecord, resume_summary: str) -> int:
        prompt = (
            "You are a strict technical job-match evaluator.\n"
            "Return ONLY JSON with one key: score (integer 1-10).\n"
            f"Candidate Summary:\n{resume_summary}\n\n"
            f"Job Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Description:\n{job.description}"
        )
        raw_content = self._call_chat_completion(prompt)
        try:
            parsed = json.loads(raw_content)
            score = int(parsed.get("score", 0))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid scoring JSON from Groq: {raw_content}") from exc
        return score

    def generate_email_draft(self, job: JobRecord, resume_summary: str, recruiter_name: str) -> EmailDraft:
        prompt = f"""You are writing a job application email on behalf of Sharath, a backend engineer.

    STRICT RULES:
    1. Output ONLY the email. No explanations, no meta-commentary, no markdown code blocks.
    2. Start with: Subject: Genuinely Interested in the {job.title} at {job.company}
    3. Then the email body exactly following the template below.
    4. The "What excites me" paragraph MUST be 280 characters or fewer (including spaces). Count carefully.
    5. The bullet points section SHOULD be tailored to the job description — emphasize technologies or responsibilities that match the job. Keep 4–5 bullets max.
    6. Replace [Name] with: {recruiter_name}
    7. Replace [Role Name] with: {job.title}
    8. Replace [Company Name] with: {job.company}
    9. In the intro paragraph, replace Python (FastAPI/Django) with the primary backend tech stack mentioned in the job description if different. Otherwise keep it.
    10. The "What excites me" line must sound 100% human-written, natural, and specific to this company/role. Never generic. Never AI-sounding. Max 280 characters.
    11. Do NOT change anything else in the fixed sections — opening line, Sharath's background line, closing lines, and signature must remain exactly as given.

    BOLDING RULES (use **text** markdown for bold):
    12. Always bold these core skills wherever they appear naturally in the email:
        **Python**, **FastAPI**, **Django**, **PostgreSQL**, **MongoDB**, **Redis**, **Elasticsearch**, **AWS**, **GCP**, **LLM**, **Google Gemini**
    13. Additionally, scan the job description and bold any skill/technology from the JD that Sharath mentions — this makes the email feel tailored and keyword-matched.
    14. Bold Sharath's identity markers exactly as shown in the template:
        **Sharath**, **2024 Graduate from IIT Ropar**, **SDE-1 at InfinityLearn**, **2 years of experience**
    15. Bold the Role Name and Company Name wherever they appear.
    16. In bullet points, bold the specific tech stack or skill being highlighted in each bullet (not the whole bullet).
    17. Do NOT over-bold. Only bold nouns (names, tools, skills, companies). Never bold verbs, filler words, or full sentences.

    ---

    FIXED TEMPLATE (follow exactly, only fill in placeholders, tailor bullets + excite line, and apply bolding):

    Subject: Genuinely Interested in the [Role Name] at [Company Name]

    Hi [Name],

    I came across the **[Role Name]** opportunity at **[Company Name]**, and it immediately stood out because the role aligns very closely with my experience and the kind of work I'm genuinely interested in.

    I'm **Sharath**, a **2024 Graduate from IIT Ropar**, currently working as an **SDE-1 at InfinityLearn** with **2 years of experience**. In my current role, I've been working on production-grade backend systems using **Python (FastAPI/Django)**, building APIs, integrations, backend workflows, and scalable systems that support real product use cases.

    A few relevant highlights from my experience:

    [TAILOR THESE 4-5 BULLETS BASED ON JOB DESCRIPTION — pick and bold the skills most relevant to the JD:]
    - Built and maintained backend systems using **Python**, **FastAPI/Django**, **PostgreSQL**, **MongoDB**, **Redis**, and REST APIs
    - Worked on scalable backend workflows, integrations, and **AWS/GCP**-based cloud systems
    - Delivered end-to-end backend features with strong ownership across live products
    - Worked on **AI-driven workflows** and **LLM-integrated** systems using **Google Gemini**
    - Strong focus on writing clean, maintainable code and solving backend reliability/performance challenges

    [IF JD MENTIONS Elasticsearch — add this bullet:]
    - Hands-on experience with **Elasticsearch** for search and log analytics at scale

    What excites me most about **[Company Name]** is [WRITE A SPECIFIC, HUMAN-SOUNDING REASON BASED ON THE JOB/COMPANY — max 280 characters, no filler phrases].

    I've attached my resume for your reference. Thank you for your time and consideration.
    Hoping to hear from you soon.

    Thankyou,
    **Sharath**,
    9347485455

    ---

    JOB CONTEXT:
    Job Title: {job.title}
    Company: {job.company}
    Job Description:
    {job.description}

    Candidate Summary:
    {resume_summary}
    """
        raw_content = self._call_chat_completion(prompt)
        return Validators.parse_subject_and_body(raw_content)
        
    def _call_chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a deterministic assistant that follows output format exactly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(
            self._url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"]["content"].strip()
