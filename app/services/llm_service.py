import logging
from typing import List
import os
import json
from litellm import completion
from ..models import Artist

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, openai_key: str, anthropic_key: str | None = None):
        os.environ["OPENAI_API_KEY"] = openai_key
        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        
        self.MODEL_MAPPING = {
            "gpt-4": "gpt-4",
            "claude": "anthropic/claude-3-5-sonnet-latest"
        }

    def get_recommendations(self, prompt: str, artists: List[Artist], model: str = "gpt-4"):
        """Get playlist recommendations using LiteLLM"""
        try:
            model_id = self.MODEL_MAPPING.get(model, model)
            
            # Create context with available artists
            artist_context = "Available artists and their genres:\n" + \
                            "\n".join([
                                f"{a.name} - {', '.join(a.genres)}"
                                for a in artists if a.name  # Skip empty names
                            ])
            
            system_prompt = """You are a music curator helping to create playlists. 
            Analyze the available artists and their genres, then select the most appropriate ones for the requested playlist.
            Return your response as a JSON object with:
            - 'artists': array of 15-20 artist names from the provided list.
            Only include artists from the provided list."""
            
            response = completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context: {artist_context}\n\nCreate a playlist for: {prompt}"}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('artists', [])  # Return just the artists list
            
        except Exception as e:
            logger.error(f"AI recommendation failed: {str(e)}")
            raise
    
    def get_artist_recommendations(self, prompt: str, artists: List[Artist], model: str = "gpt-4"):
        """First step: Get relevant artists based on the prompt"""
        try:
            artist_context = "Available artists and their genres:\n" + \
                        "\n".join([
                            f"{a.name} - {', '.join(a.genres)}"
                            for a in artists if a.name
                        ])
            
            system_prompt = """You are a multilingual music curator helping to create playlists. 
            Your responses must ALWAYS be in English, even when the prompt is in another language.
            Analyze the available artists and their genres, then select the most appropriate ones for the requested playlist.
            
            You must ALWAYS respond with valid JSON only, in this exact format:
            {"artists": ["Artist1", "Artist2", "Artist3"]}
            
            Do not add any explanations or other text - just the JSON object.
            Select 10-15 artists that match the mood/theme, only from the provided list."""
            
            response = completion(
                model=self.MODEL_MAPPING.get(model, model),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context: {artist_context}\n\nCreate a playlist for: {prompt}"}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw LLM response: {content}")
            
            try:
                result = json.loads(content)
                artists_list = result.get('artists', [])
                if not artists_list:
                    raise ValueError("No artists found in response")
                
                logger.info(f"Selected artists: {artists_list}")
                return artists_list
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                logger.error(f"Received content: {content}")
                raise
                
        except Exception as e:
            logger.error(f"Artist recommendation failed: {str(e)}")
            raise   
    
    def get_track_recommendations(self, prompt: str, artist_tracks: dict, model: str = "gpt-4"):
        """Second step: Get specific tracks based on the prompt"""
        try:
            # Format track information for LLM
            tracks_context = "Available tracks by artist:\n"
            for artist, albums in artist_tracks.items():
                tracks_context += f"\n{artist}:\n"
                for album in albums:
                    tracks_context += f"Album: {album['name']}\n"
                    for track in album['tracks']:
                        tracks_context += f"- {track['title']}\n"

            system_prompt = """You are a multilingual music curator creating a cohesive playlist.
            Your responses must ALWAYS be in English and contain ONLY a valid JSON object.
            
            Based on the available tracks and the playlist theme, select specific songs that:
            1. Flow well together
            2. Match the requested mood/theme
            3. Create a balanced representation of artists
            
            You must respond with ONLY a JSON object in this exact format:
            {
                "tracks": [
                    {"artist": "artist name", "title": "track title"}
                ]
            }
            
            Select 20-30 tracks total. Do not add any explanations or additional text."""

            response = completion(
                model=self.MODEL_MAPPING.get(model, model),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context: {tracks_context}\n\nCreate a playlist for: {prompt}"}
                ],
                max_tokens=2048,
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()
            logger.debug(f"Raw LLM response for track selection: {content}")

            try:
                result = json.loads(content)
                tracks_list = result.get('tracks', [])
                if not tracks_list:
                    raise ValueError("No tracks found in response")
                
                logger.info(f"Selected tracks: {tracks_list}")
                return tracks_list
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from track selection: {e}")
                logger.error(f"Received content: {content}")
                raise

        except Exception as e:
            logger.error(f"Track recommendation failed: {str(e)}")
            raise