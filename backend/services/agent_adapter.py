"""Loads the language-model adapter: Agent 1's Bedrock code or the local mock.

``SAMEPAGE_AI_MODE=bedrock``  imports ``backend.aws.bedrock_agent`` (Agent 1) and fails fast at
                              startup if it cannot, so the judged demo never silently runs on a mock.
``SAMEPAGE_AI_MODE=stub``     Agent 1's adapter in its own offline stub mode (their module decides).
``SAMEPAGE_AI_MODE=mock``     Agent 2's deterministic mock (default; offline UI development).

Both adapters expose::

    intake_turn(client_id, transcript, selected_option_id, tools) -> dict
    triage_case(confirmed_request, tools) -> dict

Agent 1 may export module-level functions, a class with those methods, or a
factory; sync or async. Calls run with a timeout so a hung model call becomes a
preserved draft plus a useful message instead of a hung request. Agent 1's
``BedrockAdapterError(code, message)`` is surfaced as ``AdapterError`` with the
same user-facing ``message``.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

log = logging.getLogger("samepage.adapter")


class AdapterError(RuntimeError):
    """The model adapter failed; the caller must preserve the draft."""

    def __init__(self, detail: str, *, code: str | None = None, user_message: str | None = None):
        super().__init__(detail)
        self.code = code or "ADAPTER_ERROR"
        self.user_message = user_message


class AdapterTimeout(AdapterError):
    def __init__(self, detail: str):
        super().__init__(detail, code="ADAPTER_TIMEOUT")


class AdapterUnavailable(AdapterError):
    """The requested adapter could not be loaded at startup."""

    def __init__(self, detail: str):
        super().__init__(detail, code="ADAPTER_UNAVAILABLE")


def _run_maybe_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, result).result()
    return result


def call_with_timeout(fn: Callable[..., Any], timeout_s: float, *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` on its own daemon thread. A hung call is abandoned on timeout and cannot block
    later calls (no shared pool to exhaust); it simply finishes in the background."""
    done = threading.Event()
    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["result"] = _run_maybe_async(fn, *args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - captured and re-raised on the caller's thread
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=runner, name="samepage-adapter-call", daemon=True).start()
    if not done.wait(timeout_s):
        raise AdapterTimeout(f"model adapter call exceeded {timeout_s:.0f}s")
    if "error" in box:
        exc = box["error"]
        if isinstance(exc, AdapterError):
            raise exc
        code = getattr(exc, "code", None)
        message = getattr(exc, "message", None)
        raise AdapterError(
            f"{type(exc).__name__}: {exc}",
            code=str(code) if code else type(exc).__name__,
            user_message=str(message) if isinstance(message, str) and message.strip() else None,
        ) from exc
    return box.get("result")


class AgentAdapter:
    name = "unknown"
    live = False

    def __init__(self, intake_fn: Callable[..., Any], triage_fn: Callable[..., Any], timeout_s: float):
        self._intake = intake_fn
        self._triage = triage_fn
        self.timeout_s = timeout_s

    def intake_turn(self, client_id: str, transcript: str, selected_option_id: str | None, tools: Any) -> dict[str, Any]:
        return call_with_timeout(self._intake, self.timeout_s, client_id, transcript, selected_option_id, tools)

    def triage_case(self, confirmed_request: dict[str, Any], tools: Any) -> dict[str, Any]:
        return call_with_timeout(self._triage, self.timeout_s, confirmed_request, tools)


class MockAdapter(AgentAdapter):
    name = "mock"
    live = False

    def __init__(self, timeout_s: float = 30.0):
        from backend.services import mock_agent

        super().__init__(mock_agent.intake_turn, mock_agent.triage_case, timeout_s)


class BedrockAdapter(AgentAdapter):
    """Agent 1's adapter. ``live`` is True only in bedrock mode (not stub)."""

    def __init__(self, timeout_s: float = 90.0, module_name: str = "backend.aws.bedrock_agent", mode: str = "bedrock"):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            raise AdapterUnavailable(
                f"SAMEPAGE_AI_MODE={mode} but {module_name} could not be imported ({type(exc).__name__}: {exc}). "
                "Merge/pull Agent 1's branch, run `pip install -r requirements.txt`, and set AWS_REGION / "
                "BEDROCK_MODEL_ID (see AWS_SETUP.md), or run with SAMEPAGE_AI_MODE=mock for offline UI work."
            ) from exc
        intake_fn, triage_fn = self._resolve(module)
        super().__init__(intake_fn, triage_fn, timeout_s)
        self.module_name = module_name
        self.name = "bedrock" if mode == "bedrock" else "bedrock-stub"
        self.live = mode == "bedrock"

    @staticmethod
    def _resolve(module: Any) -> tuple[Callable[..., Any], Callable[..., Any]]:
        intake = getattr(module, "intake_turn", None)
        triage = getattr(module, "triage_case", None)
        if callable(intake) and callable(triage):
            return intake, triage

        def instantiate(callable_obj: Any, what: str) -> Any:
            try:
                return callable_obj()
            except Exception as exc:  # noqa: BLE001
                raise AdapterUnavailable(
                    f"{module.__name__}.{what} must be constructible with no arguments to be used as the adapter "
                    f"({type(exc).__name__}: {exc}). Export module-level intake_turn/triage_case instead."
                ) from exc

        for factory_name in ("get_adapter", "create_adapter", "build_adapter", "get_agent", "create_agent"):
            factory = getattr(module, factory_name, None)
            if callable(factory):
                instance = instantiate(factory, factory_name)
                if callable(getattr(instance, "intake_turn", None)) and callable(getattr(instance, "triage_case", None)):
                    return instance.intake_turn, instance.triage_case
        classes = [cls for _, cls in inspect.getmembers(module, inspect.isclass)
                   if callable(getattr(cls, "intake_turn", None)) and callable(getattr(cls, "triage_case", None))]
        classes.sort(key=lambda cls: cls.__module__ != module.__name__)  # prefer classes defined in the module
        for cls in classes:
            instance = instantiate(cls, cls.__name__)
            return instance.intake_turn, instance.triage_case
        raise AdapterUnavailable(f"{module.__name__} does not export intake_turn/triage_case as functions, a class, or a factory")


def load_adapter(mode: str, timeout_s: float) -> AgentAdapter:
    mode = (mode or "mock").lower()
    if mode in ("bedrock", "stub"):
        adapter: AgentAdapter = BedrockAdapter(timeout_s=timeout_s, mode=mode)
    elif mode == "mock":
        adapter = MockAdapter(timeout_s=timeout_s)
    else:
        raise AdapterUnavailable(f"unknown SAMEPAGE_AI_MODE {mode!r}")
    log.info("language-model adapter loaded: %s (live=%s)", adapter.name, adapter.live)
    return adapter
