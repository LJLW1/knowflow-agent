"""OpenAI-compatible LLM boundary plus deterministic test double."""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import OpenAI

from knowflow.domain.models import RetrievalHit, UsageRecord


class LLMNotConfigured(RuntimeError):
    pass


@dataclass(slots=True)
class LLMAnswer:
    answer: str
    cited_chunk_ids: list[str]
    refusal_reason: str | None = None
    usage: UsageRecord | None = None


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @property
    def model_name(self) -> str | None:
        return self.model

    def generate(self, question: str, hits: list[RetrievalHit], prompt: str) -> LLMAnswer:
        if not self.api_key or not self.model:
            raise LLMNotConfigured("LLM_NOT_CONFIGURED")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "evidence": [
                                {"chunk_id": hit.chunk.chunk_id, "text": hit.chunk.text}
                                for hit in hits
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        usage = response.usage
        return LLMAnswer(
            answer=str(payload.get("answer", "")),
            cited_chunk_ids=list(payload.get("cited_chunk_ids", [])),
            refusal_reason=payload.get("refusal_reason"),
            usage=UsageRecord(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            if usage
            else None,
        )


class FakeLLM:
    """Test double. Its outputs must never be reported as model-quality results."""

    model_name = "fake-llm"

    def __init__(self, *, force_refusal: bool = False) -> None:
        self.force_refusal = force_refusal

    def generate(self, question: str, hits: list[RetrievalHit], prompt: str) -> LLMAnswer:
        del question, prompt
        if self.force_refusal or not hits:
            return LLMAnswer(
                answer="知识库中没有足够证据。",
                cited_chunk_ids=[],
                refusal_reason="INSUFFICIENT_EVIDENCE",
            )
        hit = hits[0]
        return LLMAnswer(answer=hit.chunk.text, cited_chunk_ids=[hit.chunk.chunk_id])
