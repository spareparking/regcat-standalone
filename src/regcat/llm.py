"""LLM wrapper with provider-specific modes:

  - `live`        : Anthropic API (needs ANTHROPIC_API_KEY)
  - `claude-code` : Claude Agent SDK (uses your Claude Code subscription auth,
                    no API key required; needs `claude-agent-sdk` installed)
  - `openai`      : OpenAI API (needs OPENAI_API_KEY; explicit mode only)
  - `mock`        : pre-recorded JSON fixtures under data/fixtures/<agent>/<key>.json

`auto` resolves to `claude-code` first so local extraction/build jobs use your
Claude Code subscription auth by default. API-backed providers are only used
when the mode is passed explicitly.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-7"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
MOCK_FIXTURES_ROOT = Path("data/fixtures")


def _claude_call_timeout_seconds() -> float:
    """Per-call wall-clock cap for a single live SDK invocation.

    Default is generous (600s) so legitimately slow stages are not cut short —
    the heaviest rule-extraction call (eligibility criteria over a ~10-page span)
    measured >180s and was being killed mid-flight by the old cap. Overridable
    via ANVIL_LLM_CALL_TIMEOUT_SECONDS for tuning. A non-positive or unparseable
    value falls back to the default.
    """
    raw = os.environ.get("ANVIL_LLM_CALL_TIMEOUT_SECONDS")
    if raw is None:
        return CLAUDE_CALL_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return CLAUDE_CALL_TIMEOUT_SECONDS
    return value if value > 0 else CLAUDE_CALL_TIMEOUT_SECONDS


CLAUDE_CALL_TIMEOUT_SECONDS = 600.0


class LLMError(RuntimeError):
    pass


class ClaudeCallTimeout(LLMError):
    """A single live SDK call exceeded its per-call wall-clock cap."""
    pass


def load_dotenv(root: Optional[Path] = None) -> None:
    """Load simple KEY=VALUE pairs from a root .env file if present.

    Existing process environment values win, so shell-provided secrets or model
    overrides are never replaced by the file.
    """
    if root is None:
        root = Path.cwd()
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class LLMClient:
    """Thin Claude client with mock fallback.

    All calls go through `complete_json(agent, key, system, user)`. The agent and
    key together pick the mock fixture path; in live mode they are used only for
    logging / cache identification.
    """

    def __init__(
        self,
        mode: str = "auto",          # "auto" | "live" | "claude-code" | "openai" | "mock"
        model: Optional[str] = None,
        max_tokens: int = 4096,
        fixtures_root: Path = MOCK_FIXTURES_ROOT,
        env_root: Optional[Path] = None,
    ):
        load_dotenv(env_root)
        self.max_tokens = max_tokens
        self.fixtures_root = Path(fixtures_root)

        if mode == "auto":
            mode = "claude-code"
        if mode not in ("live", "claude-code", "openai", "mock"):
            raise LLMError(f"unknown LLM mode: {mode}")
        self.mode = mode
        self.model = model or self._default_model_for_mode(mode)

        self._anthropic = None
        self._openai = None
        self._sdk_imports = None
        if self.mode == "live":
            try:
                import anthropic  # noqa: F401
                self._anthropic = anthropic.Anthropic()
            except ImportError as e:
                raise LLMError(
                    "anthropic package not installed; run `pip install anthropic`"
                ) from e
        elif self.mode == "claude-code":
            try:
                from claude_agent_sdk import (
                    query, ClaudeAgentOptions, AssistantMessage, TextBlock,
                )
                self._sdk_imports = (query, ClaudeAgentOptions, AssistantMessage, TextBlock)
            except ImportError as e:
                raise LLMError(
                    "claude-agent-sdk not installed; run "
                    "`pip install claude-agent-sdk` and ensure the `claude` CLI is on PATH "
                    "and you are logged in (`claude login`)."
                ) from e
        elif self.mode == "openai":
            try:
                from openai import OpenAI
                self._openai = OpenAI()
            except ImportError as e:
                raise LLMError(
                    "openai package not installed; run `pip install openai` "
                    "or `pip install -e .` after updating dependencies."
                ) from e

    @staticmethod
    def _default_model_for_mode(mode: str) -> Optional[str]:
        if mode == "live":
            return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        if mode == "claude-code":
            return os.environ.get("ANTHROPIC_MODEL")
        if mode == "openai":
            return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return "mock"

    # -- public API ----------------------------------------------------------

    def complete_json(
        self,
        agent: str,
        key: str,
        system: str,
        user: str,
        cache_system: bool = True,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Run an LLM call and parse the response as JSON.

        Retries up to `max_retries` times on JSON parse failures, appending a
        targeted "your previous JSON was invalid" instruction on each retry.
        Mock mode does not retry (fixtures are deterministic).
        """
        if self.mode == "mock":
            return self._load_mock(agent, key)

        last_text = ""
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            this_user = user if attempt == 0 else (
                f"{user}\n\n[RETRY {attempt}] Your previous response was not valid JSON. "
                f"Error: {last_err}\nPrevious response (first 800 chars):\n{last_text[:800]}\n"
                "Respond again with strict JSON only — no prose, no code fences, no trailing commas, "
                "no stray brackets."
            )
            try:
                if self.mode == "claude-code":
                    # No OpenAI auto-fallback: this deployment runs Claude-only.
                    # Genuinely transient provider errors (429/529/overloaded) are
                    # retried inside _call_claude_code_with_provider_retries; a real
                    # error then surfaces honestly so the caller can degrade the
                    # optional stage instead of dying on an unrelated invalid key.
                    text = self._call_claude_code_with_provider_retries(system, this_user)
                elif self.mode == "openai":
                    text = self._call_openai(system, this_user, max_tokens=max_tokens)
                else:
                    text = self._call_live(
                        system,
                        this_user,
                        cache_system=cache_system,
                        max_tokens=max_tokens,
                    )
            except Exception as e:
                raise LLMError(f"agent={agent} key={key}: provider call failed: {e}") from e
            text = _unwrap_code_fence(text)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_err = e
                last_text = text
                # Try a defensive auto-repair on the last attempt before giving up
                repaired = _attempt_json_repair(text)
                if repaired is not None:
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass
        raise LLMError(
            f"agent={agent} key={key}: response was not valid JSON after {max_retries} attempts. "
            f"Last error: {last_err}\n--- last response ---\n{last_text}"
        )

    def complete_json_with_images(
        self,
        agent: str,
        key: str,
        system: str,
        user: str,
        images: list[dict[str, Any]],
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Run a JSON extraction call with rendered page images.

        Image dictionaries must include ``mime_type`` and ``data_base64``.
        In ``claude-code`` mode the images are written to local PNG files and
        the agent is allowed to use only the Read tool for that one call.
        """
        if self.mode == "mock":
            return self._load_mock(agent, key)

        last_text = ""
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            this_user = user if attempt == 0 else (
                f"{user}\n\n[RETRY {attempt}] Your previous response was not valid JSON. "
                f"Error: {last_err}\nPrevious response (first 800 chars):\n{last_text[:800]}\n"
                "Respond again with strict JSON only."
            )
            try:
                if self.mode == "claude-code":
                    # Claude-only: see complete_json above for rationale.
                    text = self._call_claude_code_with_images_provider_retries(
                        system,
                        this_user,
                        images,
                        agent=agent,
                        key=key,
                    )
                elif self.mode == "openai":
                    text = self._call_openai_with_images(system, this_user, images, max_tokens=max_tokens)
                else:
                    text = self._call_live_with_images(system, this_user, images, max_tokens=max_tokens)
            except Exception as e:
                raise LLMError(f"agent={agent} key={key}: provider image call failed: {e}") from e
            text = _unwrap_code_fence(text)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_err = e
                last_text = text
                repaired = _attempt_json_repair(text)
                if repaired is not None:
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass
        raise LLMError(
            f"agent={agent} key={key}: image response was not valid JSON after {max_retries} attempts. "
            f"Last error: {last_err}\n--- last response ---\n{last_text}"
        )

    # -- internals -----------------------------------------------------------

    def _call_live(
        self,
        system: str,
        user: str,
        cache_system: bool,
        max_tokens: Optional[int] = None,
    ) -> str:
        msg_system: Any
        if cache_system:
            msg_system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        else:
            msg_system = system

        response = self._anthropic.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=msg_system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()

    def _call_live_with_images(
        self,
        system: str,
        user: str,
        images: list[dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        msg_system: Any = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for image in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image["mime_type"],
                    "data": image["data_base64"],
                },
            })
        response = self._anthropic.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=msg_system,
            messages=[{"role": "user", "content": content}],
        )
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()

    def _call_openai(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        """Run one OpenAI Responses API call and return JSON text.

        The existing pipeline already validates and repairs JSON after the call,
        so this method asks OpenAI for JSON object mode and lets `complete_json`
        handle parsing/retry behavior consistently across providers.
        """
        response = self._call_openai_with_retries(system, user, max_tokens=max_tokens)
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()

        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) in {"output_text", "text"}:
                    parts.append(getattr(content, "text", ""))
        return "".join(parts).strip()

    def _call_openai_with_images(
        self,
        system: str,
        user: str,
        images: list[dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user}]
        for image in images:
            content.append({
                "type": "input_image",
                "image_url": f"data:{image['mime_type']};base64,{image['data_base64']}",
            })
        response = self._openai.responses.create(
            model=self.model,
            max_output_tokens=max_tokens or self.max_tokens,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            text={"format": {"type": "json_object"}},
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content_item in getattr(item, "content", []) or []:
                if getattr(content_item, "type", None) in {"output_text", "text"}:
                    parts.append(getattr(content_item, "text", ""))
        return "".join(parts).strip()

    # NOTE: there is deliberately no OpenAI auto-fallback for the claude-code
    # path. This deployment is Claude-only; a missing/invalid OPENAI_API_KEY was
    # turning a recoverable "Claude call needs more time" into a hard, mis-attributed
    # failure. claude-code mode now retries Claude on genuinely transient provider
    # errors and otherwise surfaces the real error for graceful per-stage degradation.

    def _call_openai_with_retries(self, system: str, user: str, max_tokens: Optional[int] = None):
        transient_names = {
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "RateLimitError",
        }
        last_exc: Optional[Exception] = None
        for attempt in range(10):
            try:
                return self._openai.responses.create(
                    model=self.model,
                    max_output_tokens=max_tokens or self.max_tokens,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    text={"format": {"type": "json_object"}},
                )
            except Exception as e:
                last_exc = e
                if e.__class__.__name__ not in transient_names:
                    raise
                retry_after = _retry_after_seconds(e)
                if retry_after is None:
                    retry_after = min(60.0, 0.5 * (2 ** attempt))
                time.sleep(retry_after)
        raise LLMError(f"OpenAI request failed after retries: {last_exc}") from last_exc

    def _call_claude_code(self, system: str, user: str) -> str:
        """Run one Claude Code agent call via the Claude Agent SDK.

        We disable tool use entirely (`allowed_tools=[]`, `max_turns=1`) — this stage
        only needs text-in / JSON-out, so we don't need filesystem or bash. Each call
        is its own one-shot conversation; no state crosses calls.
        """
        import asyncio
        query, ClaudeAgentOptions, AssistantMessage, TextBlock = self._sdk_imports

        async def _run() -> str:
            parts: list[str] = []
            options = ClaudeAgentOptions(
                system_prompt=system,
                allowed_tools=[],
                disallowed_tools=["*"],
                # Allow Claude up to a few turns for very large outputs (relate stage on
                # big catalogs can need internal thinking/continuation). Tools are still
                # disabled so this only affects single-response generation behavior.
                max_turns=5,
                model=self.model,
            )
            async for msg in query(prompt=user, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
            return "".join(parts).strip()

        timeout = _claude_call_timeout_seconds()

        async def _run_bounded() -> str:
            return await asyncio.wait_for(_run(), timeout=timeout)

        try:
            return asyncio.run(_run_bounded())
        except asyncio.TimeoutError as e:
            raise ClaudeCallTimeout(
                f"Claude Code call exceeded {timeout:.0f}s per-call timeout"
            ) from e

    def _call_claude_code_with_provider_retries(self, system: str, user: str) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                return self._call_claude_code(system, user)
            except Exception as e:
                last_error = e
                if not _is_retryable_claude_code_provider_error(e) or attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        raise last_error or LLMError("Claude Code provider failed")

    def _call_claude_code_with_images(
        self,
        system: str,
        user: str,
        images: list[dict[str, Any]],
        *,
        agent: str,
        key: str,
    ) -> str:
        """Run one Claude Code call over local rendered image files.

        The SDK prompt channel is text, so we persist images under the project
        workspace and let Claude Code inspect them with its Read tool. Tools are
        still tightly scoped: no Bash/Edit/Write, only Read.
        """
        import asyncio
        query, ClaudeAgentOptions, AssistantMessage, TextBlock = self._sdk_imports
        image_dir = Path.cwd() / "_set_aside" / "claude_code_image_inputs" / _safe_path_part(agent) / _safe_path_part(key)
        image_dir.mkdir(parents=True, exist_ok=True)
        image_refs: list[dict[str, Any]] = []
        for idx, image in enumerate(images, start=1):
            suffix = "png" if image.get("mime_type") == "image/png" else "img"
            page_no = image.get("page_no") or idx
            path = image_dir / f"page_{page_no}_{idx}.{suffix}"
            path.write_bytes(base64.b64decode(image["data_base64"]))
            image_refs.append({
                "page_no": page_no,
                "path": str(path),
                "mime_type": image.get("mime_type"),
                "width": image.get("width"),
                "height": image.get("height"),
                "dpi": image.get("dpi"),
            })
        image_prompt = (
            f"{user}\n\nRendered page image files are available locally. "
            "Use the Read tool to inspect these images and return strict JSON only:\n"
            f"{json.dumps(image_refs, indent=2)}"
        )

        async def _run() -> str:
            parts: list[str] = []
            options = ClaudeAgentOptions(
                system_prompt=system,
                allowed_tools=["Read"],
                disallowed_tools=["Bash", "Edit", "MultiEdit", "Write", "NotebookEdit", "WebFetch", "WebSearch"],
                max_turns=8,
                model=self.model,
                cwd=Path.cwd(),
                add_dirs=[image_dir],
            )
            async for msg in query(prompt=image_prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
            return "".join(parts).strip()

        timeout = _claude_call_timeout_seconds()

        async def _run_bounded() -> str:
            return await asyncio.wait_for(_run(), timeout=timeout)

        try:
            return asyncio.run(_run_bounded())
        except asyncio.TimeoutError as e:
            raise ClaudeCallTimeout(
                f"Claude Code image call exceeded {timeout:.0f}s per-call timeout"
            ) from e

    def _call_claude_code_with_images_provider_retries(
        self,
        system: str,
        user: str,
        images: list[dict[str, Any]],
        *,
        agent: str,
        key: str,
    ) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                return self._call_claude_code_with_images(system, user, images, agent=agent, key=key)
            except Exception as e:
                last_error = e
                if not _is_retryable_claude_code_provider_error(e) or attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        raise last_error or LLMError("Claude Code provider image call failed")

    def _load_mock(self, agent: str, key: str) -> dict[str, Any]:
        path = self.fixtures_root / agent / f"{key}.json"
        if not path.exists():
            raise LLMError(
                f"mock fixture missing: {path}\n"
                f"  agent={agent} key={key}\n"
                f"  re-run in claude-code mode, use an explicit API-backed mode, "
                f"or add the fixture by hand."
            )
        return json.loads(path.read_text(encoding="utf-8"))


def _unwrap_code_fence(text: str) -> str:
    """Strip leading/trailing ```json or ``` fences if present."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3].rstrip()
    return t


def _safe_path_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "image_call").strip("._")
    return value[:120] or "image_call"


def _is_retryable_claude_code_provider_error(exc: Exception) -> bool:
    if isinstance(exc, ClaudeCallTimeout):
        # NOT retryable: the per-call timeout is already generous (600s). Hitting
        # it means the call is genuinely too heavy for the budget, so retrying at
        # the same budget just burns another full window. Surface it immediately
        # and let the optional stage degrade (or raise ANVIL_LLM_CALL_TIMEOUT_SECONDS).
        return False
    text = str(exc)
    return (
        "Claude Code returned an error result: success" in text
        or "error_max_turns" in text
        or "429" in text
        or "529" in text
        or "overloaded" in text.lower()
    )


def _redact_provider_error(exc: Exception) -> str:
    text = str(exc)
    if "invalid_api_key" in text or "Incorrect API key provided" in text:
        return "invalid_api_key"
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-[redacted]", text)
    text = re.sub(r"(?i)(api[_ -]?key[^:]*:\s*)[^,}\n]+", r"\1[redacted]", text)
    text = re.sub(r"Incorrect API key provided: [^'.}]+", "Incorrect API key provided: [redacted]", text)
    return text[:1000]


def _attempt_json_repair(text: str) -> Optional[str]:
    """Heuristic repair for common LLM JSON mistakes. Returns repaired text or None.

    Handles patterns we've actually seen in practice:
      - Spurious `]` after a string-valued field: `"reason": "...."]` => `"reason": "...."`
      - Trailing comma before closing brace/bracket
    """
    import re
    repaired = text
    # Pattern: `"<key>": "..."` followed by `]` (not preceded by `[`) — drop the stray `]`.
    # Specifically: `"<text>"]` where the `]` doesn't belong to a real list.
    repaired = re.sub(r'(":\s*"[^"]*")\]', r'\1', repaired)
    # Trailing commas before } or ]
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired if repaired != text else None


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after") or headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]
