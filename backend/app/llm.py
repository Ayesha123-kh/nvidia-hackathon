"""Token Factory client: OpenAI-compatible, schema-enforced JSON, per-call telemetry."""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from . import config

T = TypeVar("T", bound=BaseModel)


@dataclass
class CallStat:
    tier: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


@dataclass
class LLM:
    client: AsyncOpenAI
    fast_model: str = ""
    ultra_model: str = ""
    stats: list[CallStat] = field(default_factory=list)
    on_stat: Optional[Callable[[CallStat], None]] = None
    sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(config.MAX_CONCURRENCY))

    @classmethod
    async def create(cls) -> "LLM":
        client = AsyncOpenAI(api_key=config.TOKEN_FACTORY_API_KEY, base_url=config.TOKEN_FACTORY_BASE_URL)
        llm = cls(client=client)
        await llm.bind_models()
        return llm

    async def bind_models(self) -> None:
        """Bind tiers to what GET /v1/models returns; dossier IDs are unverified."""
        ids = [m.id async for m in self.client.models.list()]
        self.fast_model = config.FAST_MODEL or _pick(ids, ("nano", "lightning", "fast"))
        self.ultra_model = config.ULTRA_MODEL or _pick(ids, ("ultra",))
        if not self.fast_model or not self.ultra_model:
            raise RuntimeError(
                f"Could not pick Nemotron tiers from /v1/models; set TIER_FAST_MODEL/TIER_ULTRA_MODEL. Got: {ids}"
            )

    def model_for(self, tier: str) -> str:
        return self.ultra_model if tier == "ultra" else self.fast_model

    async def json_call(self, tier: str, system: str, user: str, schema: Type[T], retries: int = 1) -> T:
        model = self.model_for(tier)
        msgs = [
            {"role": "system", "content": system + "\nReply with JSON only matching: " + str(schema.model_json_schema())},
            {"role": "user", "content": user},
        ]
        err: Exception | None = None
        for _ in range(retries + 1):
            async with self.sem:
                t0 = time.perf_counter()
                resp = await self.client.chat.completions.create(
                    model=model, messages=msgs, response_format={"type": "json_object"}
                )
            stat = CallStat(
                tier, model,
                getattr(resp.usage, "prompt_tokens", 0) or 0,
                getattr(resp.usage, "completion_tokens", 0) or 0,
                int((time.perf_counter() - t0) * 1000),
            )
            self.stats.append(stat)
            if self.on_stat:
                self.on_stat(stat)
            try:
                return schema.model_validate_json(resp.choices[0].message.content)
            except ValidationError as e:
                err = e
                msgs.append({"role": "user", "content": f"Invalid JSON for the schema: {e}. Try again."})
        raise RuntimeError(f"Schema validation failed after retry: {err}")


def _pick(ids: list[str], needles: tuple[str, ...]) -> str:
    nemo = [i for i in ids if "nemotron" in i.lower()] or ids
    for n in needles:
        for i in nemo:
            if n in i.lower():
                return i
    return ""
