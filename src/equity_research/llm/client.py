"""Google Gemini Flash LLM Client Wrapper with retry & model fallback support."""
from __future__ import annotations

import time
from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError

from ..config import get_settings
from ..logging_setup import get_logger

log = get_logger(__name__)

# Only models confirmed available on the current Gemini API (v1beta). The older
# gemini-2.0-flash / gemini-1.5-flash / bare "gemini-flash" names now 404, so
# they are not used as fallbacks — that stale list was causing total failures
# whenever the primary model hit a transient error.
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
]


class GeminiClient:
    """Robust wrapper around Google's official `genai.Client` for Gemini models."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model or "gemini-3.6-flash"

        self._client: genai.Client | None = None
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
        else:
            log.warning("GeminiClient initialized without an API key (GEMINI_API_KEY).")

    @property
    def is_available(self) -> bool:
        """Returns True if client is configured with an API key."""
        return self._client is not None

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> str:
        """Generate text using Gemini Flash, with retries on 503/429 and fallback models.

        Args:
            prompt: User prompt or structured query context.
            system_instruction: Optional system instruction/persona prompt.
            temperature: Sampling temperature (default 0.2 for deterministic RAG synthesis).
            max_retries: Number of retry attempts for 503/transient errors.

        Returns:
            The generated text string from Gemini.
        """
        if not self._client:
            raise RuntimeError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in environment or .env."
            )

        config = types.GenerateContentConfig(temperature=temperature)
        if system_instruction:
            config.system_instruction = system_instruction

        candidate_models = [self.model_name]
        for m in FALLBACK_MODELS:
            if m not in candidate_models:
                candidate_models.append(m)

        last_exception: Exception | None = None

        for model in candidate_models:
            log.info("Attempting generation with Gemini model '%s'...", model)
            for attempt in range(1, max_retries + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )
                    if response.text is not None:
                        return response.text
                    return ""
                except (ServerError, APIError) as err:
                    last_exception = err
                    status_code = getattr(err, "code", getattr(err, "status_code", 500))
                    is_transient = status_code in (503, 429, 500, 502, 504) or "capacity" in str(err).lower() or "demand" in str(err).lower()

                    if is_transient and attempt < max_retries:
                        sleep_time = attempt * 2
                        log.warning(
                            "Gemini API transient error (%s) on '%s' (attempt %d/%d). Retrying in %ds...",
                            err, model, attempt, max_retries, sleep_time
                        )
                        time.sleep(sleep_time)
                    else:
                        log.warning("Model '%s' failed (error: %s). Trying fallback if available...", model, err)
                        break
                except Exception as err:
                    log.error("Unexpected error calling Gemini API with model '%s': %s", model, err)
                    last_exception = err
                    break

        raise RuntimeError(f"Gemini API generation failed across models: {last_exception}") from last_exception
