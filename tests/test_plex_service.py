"""Tests for the Plex service."""

# pylint: disable=protected-access,redefined-outer-name

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest  # pylint: disable=import-error

from app.models import Artist
from app.services.plex_service import (
    PlexService,
    find_best_track_match,
    normalize_title,
)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_normalize_title():
    """Test title normalization function."""
    assert normalize_title("Track (Live Version)") == "track"
    assert normalize_title("Track.with.dots") == "track with dots"
    assert normalize_title("Track,with,commas") == "track with commas"
    assert normalize_title("  Extra  Spaces  ") == "extra spaces"


def test_find_best_track_match():
    """Test track matching function."""
    # Create mock tracks
    track1 = Mock(title="Perfect Match")
    track2 = Mock(title="Close Match (Live)")
    track3 = Mock(title="Different Track")
    tracks = [track1, track2, track3]

    # Test exact match
    match, score = find_best_track_match(tracks, "Perfect Match")
    assert match == track1
    assert score == 1.0

    # Test close match
    match, score = find_best_track_match(tracks, "Close Match")
    assert match == track2
    assert score >= 0.85

    # Test no match
    match, score = find_best_track_match(tracks, "Non Existent Track")
    assert match is None
    assert score == 0


@pytest.fixture
def mock_plex_server():
    """Fixture to create a mock Plex server."""
    with patch("app.services.plex_service.PlexServer") as mock_server:
        # Mock the machine identifier
        mock_server.return_value.machineIdentifier = "mock_machine_id"

        # Create a mock music library section (type "artist"), discovered via sections()
        mock_library = Mock(type="artist", title="Music")
        mock_server.return_value.library.sections.return_value = [mock_library]

        yield mock_server, mock_library


@pytest.fixture
def plex_service(mock_plex_server):  # pylint: disable=unused-argument
    """Fixture to create a PlexService instance with mocked server."""
    service = PlexService("http://localhost:32400", "fake_token")
    return service


def test_plex_service_initialization(plex_service, mock_plex_server):  # pylint: disable=unused-argument
    """Test PlexService initialization."""
    _, mock_library = mock_plex_server

    # Mock artists for initialization
    artist1 = Mock(ratingKey="1", title="Artist1")
    artist1.genres = []  # Initialize as empty list
    mock_genre1 = Mock(tag="Rock")
    mock_genre2 = Mock(tag="Alternative")
    artist1.genres.extend([mock_genre1, mock_genre2])

    artist2 = Mock(ratingKey="2", title="Artist2")
    artist2.genres = []  # Initialize as empty list
    mock_genre3 = Mock(tag="Pop")
    artist2.genres.append(mock_genre3)

    mock_library.search.return_value = [artist1, artist2]

    # Initialize service
    plex_service.initialize()

    # Verify cache was populated
    assert plex_service.get_cache_size() == 2
    assert "1" in plex_service._artists_cache
    assert "2" in plex_service._artists_cache


def test_initialization_across_multiple_libraries(plex_service, mock_plex_server):
    """Artists from every music library are cached, de-duplicated by rating key."""
    mock_server, _ = mock_plex_server

    lib1 = Mock(type="artist", title="Music")
    lib2 = Mock(type="artist", title="Vinyl Rips")
    non_music = Mock(type="movie", title="Movies")

    artist1 = Mock(ratingKey="1", title="Artist1", genres=[])
    artist2 = Mock(ratingKey="2", title="Artist2", genres=[])
    # Same rating key as artist1 -> should be de-duplicated.
    artist1_dup = Mock(ratingKey="1", title="Artist1", genres=[])

    lib1.search.return_value = [artist1]
    lib2.search.return_value = [artist2, artist1_dup]
    mock_server.return_value.library.sections.return_value = [lib1, non_music, lib2]

    plex_service.initialize()

    assert plex_service.get_cache_size() == 2
    assert len(plex_service._music_libraries) == 2  # only "artist" sections


def test_initialization_no_music_libraries(plex_service, mock_plex_server):
    """A server with no music libraries initializes to an empty cache without error."""
    mock_server, _ = mock_plex_server
    mock_server.return_value.library.sections.return_value = [Mock(type="movie", title="Movies")]

    plex_service.initialize()

    assert plex_service.get_cache_size() == 0
    assert plex_service._music_libraries == []


def test_get_all_artists(plex_service):
    """Test retrieving all artists from cache."""
    # Populate cache with test data
    plex_service._artists_cache = {
        "1": Artist(id="1", name="Artist1", genres=["Rock"]),
        "2": Artist(id="2", name="Artist2", genres=["Pop"]),
    }

    artists = plex_service.get_all_artists()
    assert len(artists) == 2
    assert any(a.name == "Artist1" for a in artists)
    assert any(a.name == "Artist2" for a in artists)


def test_get_artists_albums_bulk(plex_service, mock_plex_server):
    """Test bulk album retrieval."""
    mock_server, mock_library = mock_plex_server

    # Setup mock artists in cache
    artist1 = Mock(title="Artist1", genres=[])  # Initialize with empty list
    album1 = Mock(title="Album1", year=2020)
    album1.tracks = Mock(return_value=["track1", "track2"])

    # Set up albums as a method that returns a list
    artist1.albums.return_value = [album1]

    # Setup mock search results
    mock_library.search.return_value = [artist1]

    # Initialize plex service
    plex_service.initialize()
    plex_service._music_libraries = [mock_library]
    plex_service._server = mock_server.return_value

    # Add artist to cache
    plex_service._artists_cache = {"1": Artist(id="1", name="Artist1", genres=["Rock"])}

    # Test album retrieval
    albums = plex_service.get_artists_albums_bulk(["Artist1"])

    assert "Artist1" in albums
    assert len(albums["Artist1"]) == 1
    assert albums["Artist1"][0]["name"] == "Album1"
    assert albums["Artist1"][0]["year"] == 2020
    assert albums["Artist1"][0]["track_count"] == 2


def test_create_curated_playlist(plex_service, mock_plex_server):
    """Test playlist creation with track matching."""
    mock_server, mock_library = mock_plex_server

    # Setup mock track
    track1 = MagicMock()
    track1.title = "Track1"
    track1.artist.return_value = MagicMock(title="Artist1")

    # Setup mock album
    album = MagicMock()
    album.tracks.return_value = [track1]

    # Create artist with mock albums
    search_result_artist = MagicMock()
    search_result_artist.title = "Artist1"
    search_result_artist.genres = []
    search_result_artist.albums.return_value = [album]

    # Setup mock searches - we need to handle different search scenarios
    def mock_search(*args, **kwargs):  # pylint: disable=unused-argument
        if kwargs.get("libtype") == "artist":
            return [search_result_artist]
        if kwargs.get("libtype") == "track":
            return [track1]
        return []

    # Use side_effect as a function instead of a list
    mock_library.search.side_effect = mock_search

    # Setup mock playlist creation
    mock_server.return_value.createPlaylist.return_value = MagicMock(title="New Playlist")

    # Initialize plex service
    plex_service.initialize()
    plex_service._music_libraries = [mock_library]
    plex_service._server = mock_server.return_value

    # Test playlist creation
    track_recommendations = [{"artist": "Artist1", "title": "Track1"}]

    playlist = plex_service.create_curated_playlist("New Playlist", track_recommendations)

    assert playlist.title == "New Playlist"
    mock_server.return_value.createPlaylist.assert_called_once()
    # Without prompt/model, a bare provenance summary is written.
    playlist.edit.assert_called_once_with(summary="Generated by Plexmuse")


def test_create_curated_playlist_writes_metadata_summary(plex_service, mock_plex_server):
    """Prompt and model are embedded in the playlist summary when provided."""
    mock_server, mock_library = mock_plex_server

    track1 = MagicMock()
    track1.title = "Track1"
    track1.artist.return_value = MagicMock(title="Artist1")
    album = MagicMock()
    album.tracks.return_value = [track1]
    search_result_artist = MagicMock()
    search_result_artist.title = "Artist1"
    search_result_artist.genres = []
    search_result_artist.albums.return_value = [album]

    def mock_search(*args, **kwargs):  # pylint: disable=unused-argument
        if kwargs.get("libtype") == "artist":
            return [search_result_artist]
        if kwargs.get("libtype") == "track":
            return [track1]
        return []

    mock_library.search.side_effect = mock_search
    mock_playlist = MagicMock(title="New Playlist")
    mock_server.return_value.createPlaylist.return_value = mock_playlist

    plex_service.initialize()
    plex_service._music_libraries = [mock_library]
    plex_service._server = mock_server.return_value

    plex_service.create_curated_playlist(
        "New Playlist",
        [{"artist": "Artist1", "title": "Track1"}],
        prompt="rock playlist",
        model="gpt-4",
    )

    mock_playlist.edit.assert_called_once_with(summary="Generated by Plexmuse\nPrompt: rock playlist\nModel: gpt-4")


def test_create_curated_playlist_no_matches(plex_service, mock_plex_server):
    """Test playlist creation with no matching tracks."""
    mock_server, mock_library = mock_plex_server

    # Setup empty search results
    mock_library.search.return_value = []

    # Initialize plex service
    plex_service.initialize()
    plex_service._music_libraries = [mock_library]
    plex_service._server = mock_server.return_value

    # Test playlist creation with no matches
    track_recommendations = [{"artist": "NonexistentArtist", "title": "NonexistentTrack"}]

    with pytest.raises(ValueError, match="No tracks could be matched from recommendations"):
        plex_service.create_curated_playlist("New Playlist", track_recommendations)


def test_fuzzy_track_matching(plex_service, mock_plex_server):
    """Test fuzzy matching of track titles."""
    mock_server, mock_library = mock_plex_server

    # Setup mock track
    track1 = MagicMock()
    track1.title = "Track One (Live Version)"
    track1.artist.return_value = MagicMock(title="Artist1")

    # Setup mock album
    album = MagicMock()
    album.tracks.return_value = [track1]

    # Create artist with mock albums
    search_result_artist = MagicMock()
    search_result_artist.title = "Artist1"
    search_result_artist.genres = []
    search_result_artist.albums.return_value = [album]

    # Setup mock searches to handle both artist and track searches
    def mock_search(*args, **kwargs):  # pylint: disable=unused-argument
        if kwargs.get("libtype") == "artist":
            return [search_result_artist]
        if kwargs.get("libtype") == "track":
            return [track1]
        return []

    mock_library.search.side_effect = mock_search

    # Setup mock playlist creation
    mock_server.return_value.createPlaylist.return_value = MagicMock(title="New Playlist")

    # Initialize plex service
    plex_service.initialize()
    plex_service._music_libraries = [mock_library]
    plex_service._server = mock_server.return_value

    # Test playlist creation with fuzzy matching
    track_recommendations = [{"artist": "Artist1", "title": "Track One"}]

    playlist = plex_service.create_curated_playlist("New Playlist", track_recommendations)

    assert playlist is not None
    mock_server.return_value.createPlaylist.assert_called_once()
