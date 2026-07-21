"""
Defines the data models used in the application.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Artist(BaseModel):
    """Artist model with name and genres"""

    id: str
    name: str
    genres: List[str] = []


class PlaylistRequest(BaseModel):
    """Request model for playlist generation"""

    prompt: str = Field(..., description="Description of the desired playlist")
    model: Optional[str] = Field(
        default=None, description="LiteLLM model string to use; defaults to the server-configured model"
    )
    min_tracks: int = Field(default=30, ge=1, le=100, description="Minimum number of tracks")
    max_tracks: int = Field(default=50, ge=1, le=200, description="Maximum number of tracks")


class Track(BaseModel):
    """Track model"""

    artist: str
    title: str


class PlaylistResponse(BaseModel):
    """Response model for playlist generation"""

    name: str
    track_count: int
    tracks: List[Track]
    id: Optional[str] = None
    machine_identifier: Optional[str] = None


class AIRecommendation(BaseModel):
    """Model for AI recommendations"""

    artists: List[str]
    explanation: Optional[str] = None
