"""
RailOpt — Shared LLM client mixin (NVIDIA-hosted models, OpenAI-compatible API).

Every genai class (BriefingGenerator, ExplainabilityEngine, NLQueryEngine,
DefectTextClassifier) shares one client and one fallback rule:
if there is no key, no package, or a call fails, the caller uses its template.

Setup:
    pip install openai python-dotenv
    NVIDIA_API_KEY=...   in your environment or in a .env file at the project root
    NVIDIA_MODEL=...     optional, overrides the default model
"""

from __future__ import annotations

import logging
import os

# Load .env early so the key is there before _init_llm runs.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


class LLMMixin:
    """
    Gives any class:
      - self.use_llm: bool
      - self._client: OpenAI client or None
      - self._default_model: str
      - self.llm_available (property)
      - self._llm_generate(prompt) -> str | None   (None means "use your template")

    Usage:
        class MyEngine(LLMMixin):
            def __init__(self, use_llm=True):
                self._init_llm(use_llm)
    """

    def _init_llm(self, use_llm: bool = True, model: str | None = None) -> None:
        """Create the NVIDIA client, or turn the LLM off with a warning."""
        self.use_llm = use_llm
        self._client = None

        # Old callers still pass model="gemini-2.0-flash". Ignore any gemini
        # name and use the NVIDIA default (or NVIDIA_MODEL from the environment).
        if model and not model.startswith("gemini"):
            self._default_model = model
        else:
            self._default_model = os.environ.get("NVIDIA_MODEL", DEFAULT_MODEL)

        if not use_llm:
            return

        if not os.environ.get("NVIDIA_API_KEY"):
            logger.warning(
                "%s: NVIDIA_API_KEY not found in environment — falling back to templates",
                self.__class__.__name__,
            )
            self.use_llm = False
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=os.environ["NVIDIA_API_KEY"],
                timeout=20,
                max_retries=1,
            )
            logger.info(
                "%s: NVIDIA LLM initialized (model=%s)",
                self.__class__.__name__, self._default_model,
            )
        except ImportError:
            logger.warning(
                "%s: openai package not installed — falling back to templates",
                self.__class__.__name__,
            )
            self.use_llm = False
        except Exception as e:
            logger.warning(
                "%s: Failed to create NVIDIA client (%s) — falling back to templates",
                self.__class__.__name__, e,
            )
            self.use_llm = False

    @property
    def llm_available(self) -> bool:
        """True only if the LLM is really usable."""
        return self.use_llm and self._client is not None

    def _llm_generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> str | None:
        """
        Ask the LLM. Returns None on any failure or empty reply,
        so callers can fall back to their template.
        """
        if not self.llm_available:
            return None
        try:
            response = self._client.chat.completions.create(
                model=model or self._default_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                # Thinking off: faster, and no reasoning text in the answer.
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                logger.warning(
                    "%s: LLM returned an empty reply — using template fallback",
                    self.__class__.__name__,
                )
                return None
            return text
        except Exception as e:
            logger.warning(
                "%s: LLM generation failed (%s) — using template fallback",
                self.__class__.__name__, e,
            )
            return None


# Old name kept so existing imports (`from genai.llm_mixin import GeminiMixin`)
# keep working without edits. Rename the imports later if you want.
GeminiMixin = LLMMixin