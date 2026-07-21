"""
Plexmuse API with initialization
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models import Artist, PlaylistRequest, PlaylistResponse, Track

from .services.llm_service import LLMService
from .services.plex_service import PlexService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize services
plex_service = PlexService(base_url=os.getenv("PLEX_BASE_URL"), token=os.getenv("PLEX_TOKEN"))
llm_service = LLMService()


@asynccontextmanager
async def lifespan(app_context: FastAPI):  # pylint: disable=unused-argument
    """Lifespan event handler for service initialization and cleanup"""
    # Initialize services on startup
    plex_service.initialize()
    yield
    # Cleanup on shutdown (if needed in the future)


app = FastAPI(
    title="Plexmuse API",
    description="API for generating AI-powered playlists from your Plex music library",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the index.html file with Plex and model configuration injected"""
    plex_base_url = os.getenv("PLEX_BASE_URL")
    plex_token = os.getenv("PLEX_TOKEN")
    settings = get_settings()

    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # Inject Plex and model configuration before closing body tag
    script_tag = f"""<script>
        window.plexBaseUrl = "{plex_base_url}";
        window.plexToken = "{plex_token}";
        window.defaultModel = {json.dumps(settings.default_model)};
        window.availableModels = {json.dumps(settings.available_models)};
    </script>"""
    html_content = html_content.replace("</body>", f"{script_tag}</body>")

    return HTMLResponse(content=html_content)


@app.get("/config")
async def get_config():
    """Expose the runtime model configuration to clients"""
    settings = get_settings()
    return {"default_model": settings.default_model, "available_models": settings.available_models}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "cache_size": plex_service.get_cache_size()}


@app.get("/artists", response_model=List[Artist])
async def get_artists():
    """Get all artists from the Plex music library"""
    return plex_service.get_all_artists()


@app.post("/recommendations", response_model=PlaylistResponse)
async def create_recommendations(request: PlaylistRequest):
    """Create playlist recommendations"""
    try:
        # Resolve the model once so the request, prompts, and playlist metadata agree.
        model = request.model or get_settings().default_model

        # Step 1: Get artist recommendations
        artists = plex_service.get_all_artists()
        recommended_artists = llm_service.get_artist_recommendations(
            prompt=request.prompt, artists=artists, model=model
        )

        # Step 2: Get all recommended artists' albums in one call
        artist_albums = plex_service.get_artists_albums_bulk(recommended_artists)

        # Step 3: Get track recommendations
        track_recommendations = llm_service.get_track_recommendations(
            prompt=request.prompt,
            artist_tracks=artist_albums,
            model=model,
            min_tracks=request.min_tracks,
            max_tracks=request.max_tracks,
        )

        # Step 4: Generate playlist name
        playlist_name = llm_service.generate_playlist_name(prompt=request.prompt, model=model)

        # Step 5: Create the playlist
        playlist = plex_service.create_curated_playlist(
            name=playlist_name,
            track_recommendations=track_recommendations,
            prompt=request.prompt,
            model=model,
        )
        return PlaylistResponse(
            name=playlist.title,
            track_count=len(track_recommendations),
            tracks=[Track(artist=rec["artist"], title=rec["title"]) for rec in track_recommendations],
            id=str(playlist.ratingKey) if hasattr(playlist, "ratingKey") else None,
            machine_identifier=plex_service.machine_identifier,
        )
    except Exception as e:
        logger.error("Error creating playlist: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
