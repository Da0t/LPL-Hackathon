"""SamePage FastAPI application (Agent 2).

Run (one command, port 8000)::

    python -m backend.main                            # mock adapter, offline
    SAMEPAGE_AI_MODE=bedrock python -m backend.main   # live Bedrock via Agent 1's adapter

``python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`` (the
INTEGRATION_RUNBOOK.md command) also works. ``create_app`` builds an isolated
application for tests.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import api
from backend.errors import ApiError
from backend.services.agent_adapter import AgentAdapter, load_adapter
from backend.services.intake import IntakeService
from backend.services.staff import StaffService
from backend.settings import Settings, load_settings
from backend.store import Store

log = logging.getLogger("samepage")

PLACEHOLDER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SamePage {name} page</title>
<style>body{{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.5;font-size:1.1rem}}
code{{background:#f3f3f3;padding:.1rem .3rem;border-radius:.2rem}}</style></head>
<body><h1>SamePage {name} page is not here yet</h1>
<p>The backend is running and serving <code>{route}</code>, but <code>{directory}</code> has no <code>index.html</code>.
{owner} owns that page. Once their files exist on disk this route serves them without a restart.</p>
<p>Useful while you wait: <a href="/docs">interactive API docs</a>, <a href="/health">/health</a>, <a href="/demo/clients">/demo/clients</a>.</p>
<p><small>Demo role switcher is simulated access control: send header <code>X-Demo-Role: client</code> or <code>staff</code>.</small></p>
</body></html>"""

LANDING = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SamePage</title>
<style>body{{font-family:system-ui,sans-serif;max-width:44rem;margin:4rem auto;padding:0 1rem;line-height:1.6;font-size:1.1rem}}
.badge{{display:inline-block;padding:.15rem .6rem;border-radius:1rem;background:{badge_bg};color:#fff;font-size:.9rem}}
li{{margin:.3rem 0}}</style></head>
<body><h1>SamePage</h1>
<p>Say what you need in your own words; reach the right advisor without guessing which account you meant.</p>
<p>Language model: <span class="badge">{mode_label}</span> &middot; Data: <code>{data_source}</code> &middot; <code>SAMEPAGE_AI_MODE={ai_mode}</code></p>
<ul>
<li><a href="/client">Client intake page</a> (Agent 3)</li>
<li><a href="/staff">Staff triage page</a> (Agent 4)</li>
<li><a href="/docs">API docs</a> &middot; <a href="/health">health</a> &middot; <a href="/demo/clients">demo clients</a></li>
</ul>
<p><small>All data is synthetic. The demo role switcher (<code>X-Demo-Role</code> header) is simulated access control, not production authentication.</small></p>
</body></html>"""


def create_app(settings: Settings | None = None, *, store: Store | None = None, adapter: AgentAdapter | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=os.getenv("SAMEPAGE_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    store = store or Store(settings.db_path, settings.data_dir, settings.fallback_data_dir)
    if settings.reset_on_start:
        store.reset_state()
    else:
        store.load_seed()
    adapter = adapter or load_adapter(settings.ai_mode, settings.adapter_timeout_s)
    if settings.ai_mode == "bedrock" and not adapter.live:
        raise RuntimeError("SAMEPAGE_AI_MODE=bedrock but a non-live adapter was supplied")
    if not adapter.live:
        log.warning("SAMEPAGE_AI_MODE=%s: language model is SIMULATED (%s). The judged demo must run with SAMEPAGE_AI_MODE=bedrock.", settings.ai_mode, adapter.name)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        log.info(
            "SamePage backend ready: adapter=%s live=%s data=%s client_dir=%s staff_dir=%s",
            adapter.name, adapter.live, store.data_source, settings.client_frontend_dir, settings.staff_frontend_dir,
        )
        yield
        store.close()

    app = FastAPI(
        title="SamePage API",
        version="1.0.0",
        description=(
            "Version-one contract for the SamePage hackathon prototype. Synthetic data only. "
            "The X-Demo-Role header is a simulated access-control switch, not production authentication."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.adapter = adapter
    app.state.intake = IntakeService(store, adapter)
    app.state.staff = StaffService(store)
    app.state.portal = None
    if os.getenv("COHERENT_PORTAL_CONFIG"):
        from backend.portal.service import Portal
        app.state.portal = Portal(os.environ["COHERENT_PORTAL_CONFIG"], store)
        app.state.intake.portal = app.state.portal

    @app.middleware("http")
    async def protect_portal(request: Request, call_next):
        if app.state.portal:
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                allowed = os.getenv("COHERENT_ALLOWED_ORIGINS", "http://127.0.0.1:3200,http://localhost:3200").split(",")
                origin = request.headers.get("origin")
                if origin and origin not in allowed:
                    return JSONResponse(status_code=403, content={"error_code":"ORIGIN_DENIED", "message":"This origin cannot change records."})
        response = await call_next(request)
        if request.url.path.startswith(("/portal", "/auth", "/intake", "/staff/cases")):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Local-only CORS so UI agents can develop with a separate static server if they prefer.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------- errors

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        details = [{k: v for k, v in e.items() if k in ("type", "loc", "msg")} for e in errors]
        if any(str(e.get("type", "")).startswith("json") for e in errors):
            return JSONResponse(status_code=400, content={"error_code": "INVALID_JSON", "message": "Send a JSON object.", "details": details})
        return JSONResponse(status_code=422, content={"error_code": "VALIDATION_ERROR", "message": "Request did not match the API contract.", "details": details})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "PATH_NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 403: "FORBIDDEN", 401: "UNAUTHORIZED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code, content={"error_code": code, "message": str(exc.detail)})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"error_code": "INTERNAL_ERROR", "message": "Something went wrong on our side. Your draft is preserved; please try again."})

    app.include_router(api.router)
    from backend.portal.routes import router as portal_router
    app.include_router(portal_router)

    # ---------------------------------------------------- static pages

    def serve(directory: Path, route: str, name: str, owner: str, path: str = "") -> HTMLResponse | FileResponse:
        placeholder = HTMLResponse(PLACEHOLDER.format(name=name, route=route, directory=escape(str(directory)), owner=owner))
        is_index = not path or path in ("index.html", "/")
        if not directory.is_dir():
            if is_index:
                return placeholder
            raise ApiError(404, "PATH_NOT_FOUND", f"{route} page files are not on disk yet ({owner}).")
        root = directory.resolve()
        try:
            target = (root / path).resolve() if path else root / "index.html"
        except (ValueError, OSError):
            raise ApiError(404, "PATH_NOT_FOUND", "File not found.") from None
        if root != target and root not in target.parents:
            raise ApiError(404, "PATH_NOT_FOUND", "File not found.")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            if is_index:
                return placeholder
            raise ApiError(404, "PATH_NOT_FOUND", "File not found.")
        return FileResponse(target)

    @app.get("/client", include_in_schema=False)
    @app.get("/client/", include_in_schema=False)
    def client_index():
        return serve(settings.client_frontend_dir, "/client", "client", "Agent 3")

    @app.get("/client/{path:path}", include_in_schema=False)
    def client_asset(path: str):
        return serve(settings.client_frontend_dir, "/client", "client", "Agent 3", path)

    @app.get("/intake/{path:path}", include_in_schema=False)
    def intake_get(path: str):
        raise ApiError(405, "METHOD_NOT_ALLOWED", "Intake endpoints accept POST only. See /docs.")

    @app.get("/staff", include_in_schema=False)
    @app.get("/staff/", include_in_schema=False)
    def staff_index():
        return serve(settings.staff_frontend_dir, "/staff", "staff", "Agent 4")

    @app.get("/staff/{path:path}", include_in_schema=False)
    def staff_asset(path: str, request: Request):
        # API paths that fell through (trailing slash or typo) must not be mistaken for page files.
        if path.split("/", 1)[0] == "cases":
            if path.endswith("/"):
                query = f"?{request.url.query}" if request.url.query else ""
                return RedirectResponse(url=f"/staff/{path.rstrip('/')}{query}", status_code=307)
            raise ApiError(404, "PATH_NOT_FOUND", f"No staff API route /staff/{path}. See /docs for the frozen endpoints.")
        return serve(settings.staff_frontend_dir, "/staff", "staff", "Agent 4", path)

    @app.get("/", include_in_schema=False)
    def landing():
        mode_label = "Amazon Bedrock (live)" if adapter.live else "Mock adapter (simulated, offline)"
        return HTMLResponse(LANDING.format(mode_label=mode_label, badge_bg="#1a7f37" if adapter.live else "#8a6d00", data_source=escape(store.data_source), ai_mode=escape(settings.ai_mode)))

    return app


class _LazyApp:
    """ASGI callable that builds the app on first use so importing this module has no side effects."""

    def __init__(self):
        self._app: FastAPI | None = None

    async def __call__(self, scope, receive, send):
        if self._app is None:
            self._app = create_app()
        await self._app(scope, receive, send)


app = _LazyApp()


def main() -> None:
    import uvicorn

    host = os.getenv("SAMEPAGE_HOST", "127.0.0.1")
    port = int(os.getenv("SAMEPAGE_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port, log_level=os.getenv("SAMEPAGE_LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()
