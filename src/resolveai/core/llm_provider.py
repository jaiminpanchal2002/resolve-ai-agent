"""LLM provider abstraction with retry/timeout handling.

Design notes:
- Real providers (OpenAI, Gemini) contain no test shortcuts. A separate,
  explicit FakeProvider is returned when settings.USE_FAKE_LLM is true,
  giving tests and CI a deterministic offline mode.
- Every network call is wrapped with a timeout and exponential-backoff
  retries so a single flaky API response cannot kill an agent run.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from resolveai.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def _with_retries(coro_factory: Any, *, op_name: str) -> Any:
    """Run an async callable with timeout + exponential backoff retries."""
    last_exc: Exception | None = None
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=settings.LLM_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 - provider SDKs raise varied types
            last_exc = exc
            if attempt == max_retries:
                break

            exc_str = str(exc).lower()
            if "resource_exhausted" in exc_str or "429" in exc_str or "quota" in exc_str:
                backoff = 65.0
            else:
                backoff = float(2 ** (attempt - 1))

            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %ss",
                op_name,
                attempt,
                max_retries,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)
    raise RuntimeError(f"{op_name} failed after {max_retries} attempts") from last_exc


class LLMProvider(ABC):
    """Common interface. All methods return token usage for cost tracking."""

    model_name: str = "unknown"

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        """Return (text, input_tokens, output_tokens)."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        """Return (parsed_model, input_tokens, output_tokens)."""

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """Return an embedding vector of settings.EMBEDDING_DIMENSION size."""


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        import openai

        self.model_name = settings.OPENAI_MODEL_NAME
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def _messages(self, prompt: str, system_instruction: str | None) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        response = await _with_retries(
            lambda: self.client.chat.completions.create(
                model=self.model_name,
                messages=self._messages(prompt, system_instruction),
                temperature=temperature,
            ),
            op_name="openai.generate_text",
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return (
            content,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        response = await _with_retries(
            lambda: self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=self._messages(prompt, system_instruction),
                response_format=response_model,
                temperature=temperature,
            ),
            op_name="openai.generate_structured",
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise ValueError("OpenAI returned no parseable structured output.")
        usage = response.usage
        return (
            parsed,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    async def get_embedding(self, text: str) -> list[float]:
        response = await _with_retries(
            lambda: self.client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text),
            op_name="openai.get_embedding",
        )
        return list(response.data[0].embedding)


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        import google.generativeai as genai

        self._genai = genai
        self.model_name = settings.GEMINI_MODEL_NAME
        genai.configure(api_key=settings.GEMINI_API_KEY)

    async def _run_blocking(self, fn: Any, op_name: str) -> Any:
        loop = asyncio.get_running_loop()
        return await _with_retries(lambda: loop.run_in_executor(None, fn), op_name=op_name)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        model = self._genai.GenerativeModel(
            model_name=self.model_name, system_instruction=system_instruction
        )
        response = await self._run_blocking(
            lambda: model.generate_content(
                prompt,
                generation_config=self._genai.types.GenerationConfig(temperature=temperature),
            ),
            op_name="gemini.generate_text",
        )
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        return response.text, in_tok, out_tok

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        model = self._genai.GenerativeModel(
            model_name=self.model_name, system_instruction=system_instruction
        )
        schema = response_model.model_json_schema()

        # Inline $defs/references and strip "title" because old
        # google-generativeai client doesn't support them
        def clean_schema(sch: dict) -> dict:
            import copy
            sch = copy.deepcopy(sch)
            defs = sch.pop("$defs", {})

            def resolve(node):
                if isinstance(node, dict):
                    node.pop("title", None)
                    node.pop("additionalProperties", None)
                    if "$ref" in node:
                        ref_path = node["$ref"]
                        if ref_path.startswith("#/$defs/"):
                            def_name = ref_path.split("/")[-1]
                            resolved = copy.deepcopy(defs[def_name])
                            for k, v in node.items():
                                if k != "$ref":
                                    resolved[k] = v
                            return resolve(resolved)
                    return {k: resolve(v) for k, v in node.items()}
                elif isinstance(node, list):
                    return [resolve(item) for item in node]
                return node

            return resolve(sch)

        schema = clean_schema(schema)

        response = await self._run_blocking(
            lambda: model.generate_content(
                prompt,
                generation_config=self._genai.types.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            ),
            op_name="gemini.generate_structured",
        )
        instance = response_model(**json.loads(response.text))
        usage = getattr(response, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        return instance, in_tok, out_tok

    async def get_embedding(self, text: str) -> list[float]:
        response = await self._run_blocking(
            lambda: self._genai.embed_content(model="models/gemini-embedding-001", content=text),
            op_name="gemini.get_embedding",
        )
        return list(response["embedding"])


class FakeProvider(LLMProvider):
    """Deterministic offline provider for tests and CI.

    Selected explicitly via USE_FAKE_LLM=true — never silently in production.
    Structured outputs are built from the Pydantic schema so contract tests
    still exercise real validation.
    """

    model_name = "mock-model"

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        return "[FAKE LLM RESPONSE] Resolved customer inquiry.", 10, 15

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        data = self._mock_data_for_schema(response_model)
        return response_model(**data), 10, 20

    async def get_embedding(self, text: str) -> list[float]:
        # Deterministic but text-dependent so vector tests aren't degenerate.
        seed = sum(ord(c) for c in text) % 97
        dim = settings.EMBEDDING_DIMENSION
        return [((seed + i) % 97) / 97.0 for i in range(dim)]

    @staticmethod
    def _mock_data_for_schema(response_model: type[BaseModel]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name, field in response_model.model_fields.items():
            annotation = field.annotation
            text = str(annotation)
            members = list(getattr(annotation, "__members__", {}).values())
            args = getattr(annotation, "__args__", None)
            if members:  # Enum type
                data[name] = members[0].value
            elif "Literal" in text and args:
                first = args[0]
                data[name] = getattr(first, "value", first)
            elif "bool" in text:
                data[name] = False
            elif "int" in text:
                data[name] = 0
            elif "float" in text or "Decimal" in text:
                data[name] = 0.0
            elif "list" in text:
                data[name] = []
            elif "dict" in text:
                data[name] = {}
            else:
                data[name] = "mock"
        return data


def get_llm_provider() -> LLMProvider:
    """Factory. Fake mode must be requested explicitly via configuration."""
    if settings.USE_FAKE_LLM:
        return FakeProvider()
    if settings.DEFAULT_PROVIDER == "gemini":
        return GeminiProvider()
    return OpenAIProvider()
