"""
LLM Service

This module provides the LLMService class for generating playlist recommendations
using language models.
"""

import json
import logging
import os
import re
from typing import List

from litellm import completion

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

    def get_artist_recommendations(self, prompt: str, artists: List[Artist], model: str = "gpt-4"):
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

            # Check if OpenAI API key has a value and use it, otherwise fall back to Anthropic
            if ("gpt" in model or "openai" in model) and os.getenv("OPENAI_API_KEY"):
                response = completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Context: {artist_context}\n\nCreate a playlist for: {prompt}",
                        },
                    ],
                    temperature=0.7,
                )
            else:
                if "gpt" in model or "openai" in model:
                    logger.warning("OpenAI API key is empty or not set, falling back to Anthropic")
                    model = "claude-3-opus-20240229"
                
                response = completion(
                    model=model,
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
        self, prompt: str, artist_tracks: dict, model: str = "gpt-4", min_tracks: int = 30, max_tracks: int = 50
    ):  # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
        """Get track recommendations with simplified album context"""
        try:
            # Format just album information for context
            albums_context = "Available albums by artist:\n"
            for artist, albums in artist_tracks.items():
                albums_context += f"\n{artist}:\n"
                for album in albums:
                    albums_context += f"- {album['name']} ({album['year']})\n"

            system_prompt = """You are a multilingual music curator creating a cohesive playlist.
            Your responses must ALWAYS be in English and contain ONLY a valid JSON object.

            Based on your knowledge of these artists' albums and the playlist theme,
            recommend specific songs that would create a great playlist. You can recommend
            any tracks you know exist on these albums - you don't need to see the track list.

            You must respond with ONLY a JSON object in this exact format:
            {
                "tracks": [
                    {"artist": "artist name", "title": "track title"}
                ]
            }

            Select between {min_tracks} and {max_tracks} tracks total.
            Do not add any explanations or additional text."""

            # Check if OpenAI API key has a value and use it, otherwise fall back to Anthropic
            if ("gpt" in model or "openai" in model) and os.getenv("OPENAI_API_KEY"):
                response = completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"""Context: {albums_context}\n\n
                            Create a playlist with {min_tracks}-{max_tracks} tracks for: {prompt}
                            """,
                        },
                    ],
                    temperature=0.7,
                )
            else:
                if "gpt" in model or "openai" in model:
                    logger.warning("OpenAI API key is empty or not set, falling back to Anthropic")
                    model = "claude-3-opus-20240229"
                
                response = completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"""Context: {albums_context}\n\n
                            Create a playlist with {min_tracks}-{max_tracks} tracks for: {prompt}
                            """,
                        },
                    ],
                    temperature=0.7,
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

    def generate_playlist_name(self, prompt: str, model: str = "gpt-4") -> str:
        """Generate a playlist name based on the prompt"""
        try:
            system_prompt = """
            You are a creative assistant.
            Generate a SINGLE catchy and relevant playlist name based on the following prompt. Do not wrap in quotes.
            """

            # Check if OpenAI API key has a value and use it, otherwise fall back to Anthropic
            if ("gpt" in model or "openai" in model) and os.getenv("OPENAI_API_KEY"):
                response = completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                )
            else:
                if "gpt" in model or "openai" in model:
                    logger.warning("OpenAI API key is empty or not set, falling back to Anthropic")
                    model = "claude-3-opus-20240229"
                
                response = completion(
                    model=model,
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
