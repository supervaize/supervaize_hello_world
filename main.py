from supervaizer.server import API_VERSION, VERSION

from supervaizer_control import AGENT_VERSION, app, sv_server

# Expose the FastAPI app instance
__all__ = ["app"]


@app.get("/api/context")
def api_context() -> dict:
    """Return context for the home page (version, base URLs, show_admin)."""
    base = (
        sv_server.public_url
        or f"{sv_server.scheme}://{sv_server.host}:{sv_server.port}"
    )
    return {
        "agent_version": AGENT_VERSION,
        "version": VERSION,
        "api_version": API_VERSION,
        "base": base,
        "public_url": sv_server.public_url or base,
        "full_url": f"{sv_server.scheme}://{sv_server.host}:{sv_server.port}",
        "show_admin": bool(sv_server.api_key),
    }
