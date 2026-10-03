"""Loads the language-model adapter: Agent 1's Bedrock code or the local mock.

``SAMEPAGE_AGENT_MODE=mock``    deterministic offline adapter (default; UI development)
``SAMEPAGE_AGENT_MODE=bedrock`` imports ``backend.aws.bedrock_agent`` (Agent 1) and
                                fails fast at startup if it cannot be imported, so the
                                judged demo never silently runs on the mock.

Both adapters expose::

    intake_turn(client_id, transcript, selected_option_id, tools) -> dict
    triage_case(confirmed_request, tools) -> dict

Agent 1 may export module-level functions, a class with those methods, or a
factory; sync or async. Calls run with a timeout so a hung model call turns
into a preserved draft plus a useful message instead of a hung request.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable

log = logging.getLogger("samepage.adapter")


class AdapterError(RuntimeError):
    """The model adapter failed; the caller must preserve the draft."""


class AdapterTimeout(AdapterError):
    pass


class AdapterUnavailable(AdapterError):
    """The requested adapter could not be loaded at startup."""


def _run_maybe_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        # We are inside a running loop (unexpected for sync endpoints); run in a fresh thread.
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, result).result()
    return result


_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="samepage-adapter")


def call_with_timeout(fn: Callable[..., Any], timeout_s: float, *args: Any, **kwargs: Any) -> Any:
    future = _executor.submit(_run_maybe_async, fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout as exc:
        raise AdapterTimeout(f"model adapter call exceeded {timeout_s:.0f}s") from exc
    except AdapterError:
        raise
    except Exception as exc:  # noqa: BLE001 - any adapter failure becomes a preserved draft
        raise AdapterError(f"{type(exc).__name__}: {exc}") from exc


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
    name = "bedrock"
    live = True

    def __init__(self, timeout_s: float = 45.0, module_name: str = "backend.aws.bedrock_agent"):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            raise AdapterUnavailable(
                f"SAMEPAGE_AGENT_MODE=bedrock but {module_name} could not be imported ({type(exc).__name__}: {exc}). "
                "Pull Agent 1's branch, install requirements-aws.txt, and configure AWS credentials/region, "
                "or run with SAMEPAGE_AGENT_MODE=mock for offline UI work."
            ) from exc
        intake_fn, triage_fn = self._resolve(module)
        super().__init__(intake_fn, triage_fn, timeout_s)
        self.module_name = module_name

    @staticmethod
    def _resolve(module: Any) -> tuple[Callable[..., Any], Callable[..., Any]]:
        intake = getattr(module, "intake_turn", None)
        triage = getattr(module, "triage_case", None)
        if callable(intake) and callable(triage):
            return intake, triage
        for factory_name in ("get_adapter", "create_adapter", "build_adapter", "get_agent", "create_agent"):
            factory = getattr(module, factory_name, None)
            if callable(factory):
                instance = factory()
                if callable(getattr(instance, "intake_turn", None)) and callable(getattr(instance, "triage_case", None)):
                    return instance.intake_turn, instance.triage_case
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if callable(getattr(cls, "intake_turn", None)) and callable(getattr(cls, "triage_case", None)):
                instance = cls()
                return instance.intake_turn, instance.triage_case
        raise AdapterUnavailable(
            f"{module.__name__} does not export intake_turn/triage_case as functions, a class, or a factory"
        )


def load_adapter(mode: str, timeout_s: float) -> AgentAdapter:
    mode = (mode or "mock").lower()
    if mode == "bedrock":
        adapter: AgentAdapter = BedrockAdapter(timeout_s=timeout_s)
    elif mode == "mock":
        adapter = MockAdapter(timeout_s=timeout_s)
    else:
        raise AdapterUnavailable(f"unknown SAMEPAGE_AGENT_MODE {mode!r}")
    log.info("language-model adapter loaded: %s (live=%s)", adapter.name, adapter.live)
    return adapter
