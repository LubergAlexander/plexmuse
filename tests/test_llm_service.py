"""Tests for the LLM service."""

# pylint: disable=redefined-outer-name

from unittest.mock import Mock

import pytest  # pylint: disable=import-error

from app.models import Artist
from app.services.llm_service import LLMService, clean_llm_response


def test_clean_llm_response_with_json_block():
    """Test cleaning LLM response with JSON block."""
    input_text = '```json\n{"key": "value"}\n```'
    assert clean_llm_response(input_text) == '{"key": "value"}'


def test_clean_llm_response_without_json_block():
    """Test cleaning LLM response without JSON block."""
    input_text = '  {"key": "value"}  '
    assert clean_llm_response(input_text) == '{"key": "value"}'


@pytest.fixture
def mock_completion(monkeypatch):
    """Fixture to mock litellm completion."""
    mock = Mock()
    monkeypatch.setattr("app.services.llm_service.completion", mock)
    return mock


@pytest.fixture
def sample_artists():
    """Fixture to provide sample artists."""
    return [
        Artist(id="1", name="Artist1", genres=["Rock", "Alternative"]),
        Artist(id="2", name="Artist2", genres=["Pop", "Electronic"]),
        Artist(id="3", name="Artist3", genres=["Hip Hop", "Rap"]),
    ]


def test_get_artist_recommendations(mock_completion, sample_artists):
    """Test getting artist recommendations."""
    # Mock the LLM response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"artists": ["Artist1", "Artist2"]}'))]
    mock_completion.return_value = mock_response

    service = LLMService()
    result = service.get_artist_recommendations("Test prompt", sample_artists)

    assert result == ["Artist1", "Artist2"]
    mock_completion.assert_called_once()


def test_get_track_recommendations(mock_completion):
    """Test getting track recommendations."""
    # Sample artist tracks data
    artist_tracks = {
        "Artist1": [{"name": "Album1", "year": 2020}],
        "Artist2": [{"name": "Album2", "year": 2021}],
    }

    # Mock the LLM response
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content="""{"tracks": [
                    {"artist": "Artist1", "title": "Track1"},
                    {"artist": "Artist2", "title": "Track2"}
                ]}"""
            )
        )
    ]
    mock_completion.return_value = mock_response

    service = LLMService()
    result = service.get_track_recommendations("Test prompt", artist_tracks)

    assert len(result) == 2
    assert result[0]["artist"] == "Artist1"
    assert result[0]["title"] == "Track1"
    mock_completion.assert_called_once()


def test_generate_playlist_name(mock_completion):
    """Test generating playlist name."""
    # Mock the LLM response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Awesome Mix Vol. 1"))]
    mock_completion.return_value = mock_response

    service = LLMService()
    result = service.generate_playlist_name("Test prompt")

    assert result == "Awesome Mix Vol. 1"
    mock_completion.assert_called_once()


def test_get_artist_recommendations_error_handling(mock_completion, sample_artists):
    """Test error handling in artist recommendations."""
    # Mock an error response
    mock_completion.side_effect = Exception("API Error")

    service = LLMService()
    with pytest.raises(Exception) as exc_info:
        service.get_artist_recommendations("Test prompt", sample_artists)

    assert str(exc_info.value) == "API Error"


def test_get_artist_recommendations_invalid_json(mock_completion, sample_artists):
    """Test handling invalid JSON in response."""
    # Mock invalid JSON response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Invalid JSON"))]
    mock_completion.return_value = mock_response

    service = LLMService()
    with pytest.raises(Exception):
        service.get_artist_recommendations("Test prompt", sample_artists)


def test_get_track_recommendations_empty_response(mock_completion):
    """Test handling empty track recommendations."""
    # Mock empty response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"tracks": []}'))]
    mock_completion.return_value = mock_response

    service = LLMService()
    with pytest.raises(ValueError, match="No tracks found in response"):
        service.get_track_recommendations("Test prompt", {})
