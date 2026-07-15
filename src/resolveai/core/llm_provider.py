import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Union

import google.generativeai as genai
import openai
from pydantic import BaseModel

from resolveai.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:  # Returns (text, input_tokens, output_tokens)
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:  # Returns (pydantic_instance, input_tokens, output_tokens)
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        pass


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL_NAME
        self.is_mock = self.api_key == "mock-key-or-real-key" or not self.api_key
        if not self.is_mock:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        if self.is_mock:
            return "[MOCK OPENAI RESPONSE] Resolved customer inquiry.", 10, 15

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return content, input_tokens, output_tokens

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        if self.is_mock:
            # Create a mock instance of the response model
            mock_data = self._generate_mock_schema_data(response_model)
            return response_model(**mock_data), 10, 20

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_model,
            temperature=temperature,
        )
        content = response.choices[0].message.parsed
        if not content:
            raise ValueError("Failed to parse structured output from OpenAI.")
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return content, input_tokens, output_tokens

    async def get_embedding(self, text: str) -> list[float]:
        if self.is_mock:
            # Return a deterministic mock vector of the required dimension
            dim = settings.EMBEDDING_DIMENSION
            return [0.1] * dim

        response = await self.client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    def _generate_mock_schema_data(self, model: type[BaseModel]) -> dict[str, Any]:
        """Generates realistic mock data based on Pydantic field definitions."""
        import typing
        import types
        from typing import get_origin, get_args, Literal

        data = {}
        for field_name, field in model.model_fields.items():
            field_type = field.annotation
            
            # Handle Optionals and Unions
            origin = get_origin(field_type)
            if origin is Union or (hasattr(types, "UnionType") and isinstance(field_type, types.UnionType)):
                args = get_args(field_type)
                non_none_args = [a for a in args if a is not type(None)]
                if non_none_args:
                    field_type = non_none_args[0]
                    origin = get_origin(field_type)

            type_name = str(field_type)
            args = get_args(field_type)

            # Literal matching
            if origin is Literal or "Literal" in type_name:
                data[field_name] = args[0] if args else "RESOLVED"
            # Collection matching (list/set)
            elif origin in (list, set) or "list" in type_name.lower() or "set" in type_name.lower():
                if args:
                    inner_type = args[0]
                    inner_origin = get_origin(inner_type)
                    inner_name = str(inner_type)
                    if inner_origin is Literal or "Literal" in inner_name:
                        inner_args = get_args(inner_type)
                        data[field_name] = [inner_args[0]] if inner_args else ["mock_item"]
                    elif "int" in inner_name:
                        data[field_name] = [1]
                    else:
                        data[field_name] = ["mock_item"]
                else:
                    data[field_name] = ["mock_item"]
            elif "bool" in type_name:
                data[field_name] = True
            elif "int" in type_name:
                data[field_name] = 1
            elif "float" in type_name or "decimal" in type_name.lower():
                data[field_name] = 1.0
            elif "str" in type_name:
                if field_name == "intent":
                    data[field_name] = "REPORT_MISSING_DELIVERY"
                elif "reason" in field_name.lower():
                    data[field_name] = "High-value delivery dispute with missing proof of delivery"
                elif "category" in field_name.lower():
                    data[field_name] = "DELIVERY_DISPUTE"
                elif "severity" in field_name.lower():
                    data[field_name] = "HIGH"
                else:
                    data[field_name] = "mock_value"
            else:
                if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                    data[field_name] = self._generate_mock_schema_data(field_type)
                else:
                    data[field_name] = None
        return data


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL_NAME
        self.is_mock = self.api_key == "mock-key-or-real-key" or not self.api_key
        if not self.is_mock:
            genai.configure(api_key=self.api_key)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[str, int, int]:
        if self.is_mock:
            return "[MOCK GEMINI RESPONSE] Resolved customer inquiry.", 10, 15

        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_instruction,
        )
        # Using executor since SDK method might be blocky
        import asyncio
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
        )
        # Count tokens roughly or query the API
        input_tokens = len(prompt.split())  # rough approximation if API doesn't return usage
        output_tokens = len(response.text.split()) if response.text else 0
        return response.text, input_tokens, output_tokens

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[T, int, int]:
        if self.is_mock:
            mock_data = OpenAIProvider()._generate_mock_schema_data(response_model)
            return response_model(**mock_data), 10, 20

        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_instruction,
        )
        import asyncio
        loop = asyncio.get_running_loop()
        
        # Pydantic v2 JSON Schema conversion
        schema = response_model.model_json_schema()
        
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                )
            )
        )
        parsed_json = json.loads(response.text)
        instance = response_model(**parsed_json)
        input_tokens = len(prompt.split())
        output_tokens = len(response.text.split())
        return instance, input_tokens, output_tokens

    async def get_embedding(self, text: str) -> list[float]:
        if self.is_mock:
            dim = settings.EMBEDDING_DIMENSION
            return [0.1] * dim

        # Use Google's standard text embedding model
        import asyncio
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model="models/text-embedding-004",
                contents=text,
            )
        )
        return response["embedding"]


def get_llm_provider() -> LLMProvider:
    if settings.DEFAULT_PROVIDER == "gemini":
        return GeminiProvider()
    return OpenAIProvider()
