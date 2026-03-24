"""Shared helpers for thinking agent tests."""

from unittest.mock import MagicMock


def mock_crew_result(raw_json: str):
    """Build a mock Crew whose kickoff() returns a result with the given raw JSON."""
    mock_result = MagicMock()
    mock_result.raw = raw_json
    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = mock_result
    return mock_crew
