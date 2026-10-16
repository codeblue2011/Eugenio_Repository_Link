
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        expected_token = os.environ.get("MCP_AUTH_TOKEN")

        # Fail closed if the server has no token configured.
        if not expected_token:
            return JSONResponse(
                {"error": "Server authentication is not configured."},
                status_code=500,
            )

        authorization = request.headers.get("authorization", "")
        expected_header = f"Bearer {expected_token}"

        if not hmac.compare_digest(authorization, expected_header):
            return JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
            )

        return await call_next(request)
