"""Simple password authentication for the app."""

import secrets
from fastapi import Request, HTTPException, status
from fastapi.responses import HTMLResponse

from app.config import get_settings

settings = get_settings()

# Simple session storage (in-memory, resets on restart)
# For production, consider using signed cookies or a proper session store
authenticated_sessions: set[str] = set()


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def verify_password(password: str) -> bool:
    """Check if the provided password matches."""
    if not settings.auth_enabled:
        return True
    return secrets.compare_digest(password, settings.app_password)


def get_session_token(request: Request) -> str | None:
    """Extract session token from cookie."""
    return request.cookies.get("session_token")


def is_authenticated(request: Request) -> bool:
    """Check if the request is authenticated."""
    if not settings.auth_enabled:
        return True
    token = get_session_token(request)
    return token is not None and token in authenticated_sessions


def require_auth(request: Request) -> None:
    """Dependency that requires authentication."""
    if not settings.auth_enabled:
        return
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )


LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - MyCon Learn</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-xl shadow-lg w-full max-w-sm">
        <h1 class="text-2xl font-bold text-center mb-6">MyCon Learn</h1>
        {error}
        <form method="POST" action="/login" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                    type="password"
                    name="password"
                    class="w-full px-3 py-2 border border-gray-300 rounded focus:border-blue-500 focus:outline-none"
                    autofocus
                    required
                >
            </div>
            <button
                type="submit"
                class="w-full bg-blue-600 text-white py-2 rounded font-medium hover:bg-blue-700"
            >
                Login
            </button>
        </form>
    </div>
</body>
</html>
"""


def get_login_page(error: str = "") -> HTMLResponse:
    """Return the login page HTML."""
    error_html = ""
    if error:
        error_html = f'<div class="bg-red-100 text-red-800 p-3 rounded mb-4 text-sm">{error}</div>'
    return HTMLResponse(LOGIN_PAGE_HTML.format(error=error_html))
