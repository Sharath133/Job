from __future__ import annotations

from src.services.groq_service import GroqService


def test_groq_service_throttles_between_requests(monkeypatch) -> None:
    timeline = [100.0, 105.0, 130.0]
    sleeps: list[float] = []

    def fake_monotonic() -> float:
        return timeline.pop(0)

    monkeypatch.setattr("src.services.groq_service.time.monotonic", fake_monotonic)
    monkeypatch.setattr("src.services.groq_service.time.sleep", sleeps.append)

    service = GroqService("key", "model", request_delay_seconds=30.0)

    service._wait_for_request_slot()
    service._wait_for_request_slot()

    assert sleeps == [25.0]
