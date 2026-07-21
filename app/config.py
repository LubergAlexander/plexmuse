"""
Application configuration sourced from environment variables.

This makes the LLM model/provider (and therefore which API key is required)
configurable at runtime, e.g. when launching the Docker container:

    docker run -e PLEXMUSE_MODEL=anthropic/claude-3-5-sonnet-latest \
               -e ANTHROPIC_API_KEY=sk-... ...

Any model string supported by LiteLLM works, so switching provider is just a
matter of changing ``PLEXMUSE_MODEL`` and supplying the matching API key.
"""

import os
from functools import lru_cache
from typing import List

# Used only when ``PLEXMUSE_MODEL`` is not set.
DEFAULT_MODEL = "gpt-4"


class Settings:  # pylint: disable=too-few-public-methods
    """Runtime settings resolved from environment variables."""

    def __init__(self) -> None:
        # The model used when a request does not specify one.
        self.default_model: str = (os.getenv("PLEXMUSE_MODEL") or DEFAULT_MODEL).strip()

        # Optional comma-separated list of models offered in the UI dropdown.
        raw_models = os.getenv("PLEXMUSE_MODELS", "")
        models: List[str] = [m.strip() for m in raw_models.split(",") if m.strip()]

        # The default model must always be selectable, listed first.
        if self.default_model in models:
            models.remove(self.default_model)
        models.insert(0, self.default_model)

        self.available_models: List[str] = models


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton (read once after dotenv loads)."""
    return Settings()
