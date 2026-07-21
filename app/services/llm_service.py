"""
LLM Service

This module provides the LLMService class for generating playlist recommendations
using language models via LiteLLM. The model (and therefore provider) is
configurable, and the required API key is validated before every call so that a
missing or empty key produces a clear, actionable error instead of an opaque
provider failure.
"""

import json
import logging
import os
import re
from typing import List, Optional

import litellm
from litellm import completion

from app.config import get_settings
from app.models import Artist

logger = logging.getLogger(__name__)


def clean_llm_response(content: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks"""
    # Check for ```json ... ``` pattern
    json_block_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    if json_block_match:
        return json_block_match.group(1)
    return content.strip()


class LLMService:
    """
    A service class for generating playlist recommendations using language models.
    """

    def _resolve_model(self, model: Optional[str]) -> str:
        """Fall back to the configured default model when none is provided."""
        return model or get_settings().default_model

    @staticmethod
    def _validate_model_environment(model: str) -> None:
        """
        Ensure the API key required by ``model``'s provider is set and non-empty.

        LiteLLM's ``validate_environment`` only checks that the key is *present*
        in the environment, so an empty string (e.g. ``OPENAI_API_KEY=``) slips
        through and fails later with an opaque error. We temporarily drop
        empty/whitespace ``*_API_KEY`` variables so they are correctly reported
        as missing, then raise a clear error naming what to set.
        """
        blanked = {k: v for k, v in os.environ.items() if k.endswith("_API_KEY") and not v.strip()}
        for key in blanked:
            del os.environ[key]
        try:
            result = litellm.validate_environment(model=model)
        finally:
            os.environ.update(blanked)

        if not result.get("keys_in_environment", False):
            missing = ", ".join(result.get("missing_keys", [])) or "the required API key"
            raise ValueError(
                f"Missing or empty API key for model '{model}'. "
                f"Set the following environment variable(s): {missing}."
            )

    def _complete(self, model: Optional[str], messages: List[dict], temperature: float = 0.7):
        """Validate credentials for the chosen model, then run the completion."""
        resolved = self._resolve_model(model)
        self._validate_model_environment(resolved)
        logger.debug("Requesting completion from model: %s", resolved)
        return completion(model=resolved, messages=messages, temperature=temperature)

    def get_artist_recommendations(self, prompt: str, artists: List[Artist], model: str = None):
        """First step: Get relevant artists based on the prompt"""
        try:
            artist_context = "Available artists and their genres:\n" + "\n".join(
                [f"{a.name} - {', '.join(a.genres)}" for a in artists if a.name]
            )

            system_prompt = """You are a multilingual music curator helping to create playlists.
            Your responses must ALWAYS be in English, even when the prompt is in another language.
            Analyze the available artists and their genres,
            then select the most appropriate ones for the requested playlist.

            You must ALWAYS respond with valid JSON only, in this exact format:
            {"artists": ["Artist1", "Artist2", "Artist3"]}

            Do not add any explanations or other text - just the JSON object.
            Select 10-15 artists that match the mood/theme, only from the provided list."""

            response = self._complete(
                model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Context: {artist_context}\n\nCreate a playlist for: {prompt}",
                    },
                ],
                temperature=0.7,
            )

            content = clean_llm_response(response.choices[0].message.content)
            logger.debug("Raw LLM response: %s", content)

            try:
                result = json.loads(content)
                artists_list = result.get("artists", [])
                if not artists_list:
                    raise ValueError("No artists found in response")

                logger.info("Selected artists: %s", artists_list)
                return artists_list

            except json.JSONDecodeError as e:
                logger.error("Failed to parse JSON: %s", e)
                logger.error("Received content: %s", content)
                raise

        except Exception as e:
            logger.error("Artist recommendation failed: %s", str(e))
            raise

    def get_track_recommendations(
        self, prompt: str, artist_tracks: dict, model: str = None, min_tracks: int = 30, max_tracks: int = 50
    ):  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        """Get track recommendations with simplified album context"""
        try:
            # Format just album information for context
            albums_context = "Available albums by artist:\n"
            for artist, albums in artist_tracks.items():
                albums_context += f"\n{artist}:\n"
                for album in albums:
                    albums_context += f"- {album['name']} ({album['year']})\n"

            system_prompt = f"""You are a multilingual music curator creating a cohesive playlist.
            Your responses must ALWAYS be in English and contain ONLY a valid JSON object.

            Based on your knowledge of these artists' albums and the playlist theme,
            recommend specific songs that would create a great playlist. You can recommend
            any tracks you know exist on these albums - you don't need to see the track list.

            You must respond with ONLY a JSON object in this exact format:
            {{
                "tracks": [
                    {{"artist": "artist name", "title": "track title"}}
                ]
            }}

            You MUST select between {min_tracks} and {max_tracks} tracks in total.
            Ensure variety by selecting different tracks from different albums and artists.
            Avoid repeating the same tracks or selecting too many tracks from the same album.
            Do not add any explanations or additional text."""

            response = self._complete(
                model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"""Context: {albums_context}\n\n
                        Create a playlist with {min_tracks}-{max_tracks} tracks for: {prompt}
                        """,
                    },
                ],
                temperature=0.8,
            )

            content = clean_llm_response(response.choices[0].message.content)
            result = json.loads(content)
            tracks_list = result.get("tracks", [])

            if not tracks_list:
                raise ValueError("No tracks found in response")

            logger.info("Selected tracks: %s", tracks_list)
            return tracks_list

        except Exception as e:
            logger.error("Track recommendation failed: %s", str(e))
            raise

    def generate_playlist_name(self, prompt: str, model: str = None) -> str:
        """Generate a playlist name based on the prompt"""
        try:
            system_prompt = """
            You are a creative assistant.
            Generate a SINGLE catchy and relevant playlist name based on the following prompt. Do not wrap in quotes.
            """

            response = self._complete(
                model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            name = response.choices[0].message.content.strip()
            logger.info("Generated playlist name: %s", name)
            return name

        except Exception as e:
            logger.error("Failed to generate playlist name: %s", str(e))
            raise
