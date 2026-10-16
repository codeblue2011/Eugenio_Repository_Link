
"""Simple OAuth provider for MCP servers.

This is a simplified OAuth implementation for local development.
Credentials are read from environment variables.

This example is not production-ready. Client registrations, authorization
codes, and tokens are stored in memory and are lost when the server restarts.
"""

import html
import secrets
import time
from typing import Any

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class SimpleAuthSettings(BaseSettings):
    """OAuth settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="MCP_")

    demo_username: str
    demo_password: str
    mcp_scope: str = "user"


class SimpleOAuthProvider(
    OAuthAuthorizationServerProvider[
        AuthorizationCode, RefreshToken, AccessToken
    ]
):
    """A basic OAuth provider for the local MCP file server."""

    def __init__(
        self,
        settings: SimpleAuthSettings,
        auth_callback_url: str,
        server_url: str,
    ):
        self.settings = settings
        self.auth_callback_url = auth_callback_url
        self.server_url = server_url.rstrip("/")

        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.state_mapping: dict[str, dict[str, str | None]] = {}
        self.user_data: dict[str, dict[str, Any]] = {}

    async def get_client(
        self, client_id: str
    ) -> OAuthClientInformationFull | None:
        """Return a registered OAuth client."""
        return self.clients.get(client_id)

    async def register_client(
        self, client_info: OAuthClientInformationFull
    ) -> None:
        """Register an OAuth client."""
        if not client_info.client_id:
            raise ValueError("No client_id provided")

        self.clients[client_info.client_id] = client_info

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """Start the login flow and store authorization state."""
        if not client.client_id:
            raise ValueError("No client_id provided")

        state = params.state or secrets.token_urlsafe(24)

        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": str(
                params.redirect_uri_provided_explicitly
            ),
            "client_id": client.client_id,
            "resource": params.resource,
        }

        return (
            f"{self.auth_callback_url}"
            f"?state={state}&client_id={client.client_id}"
        )

    async def get_login_page(self, state: str) -> HTMLResponse:
        """Display the username and password form."""
        if not state or state not in self.state_mapping:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        safe_state = html.escape(state, quote=True)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Local File Server Sign In</title>
        </head>
        <body>
            <h2>Local File Server Sign In</h2>
            <p>Enter your configured credentials to continue.</p>
            <form action="{self.server_url}/login/callback" method="post">
                <input type="hidden" name="state" value="{safe_state}">
                <div>
                    <label for="username">Username:</label>
                    <input id="username" type="text" name="username"
                           autocomplete="username" required>
                </div>
                <div>
                    <label for="password">Password:</label>
                    <input id="password" type="password" name="password"
                           autocomplete="current-password" required>
                </div>
                <button type="submit">Sign In</button>
            </form>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    async def handle_login_callback(self, request: Request) -> Response:
        """Validate the submitted credentials and redirect the client."""
        form = await request.form()

        username = form.get("username")
        password = form.get("password")
        state = form.get("state")

        if not username or not password or not state:
            raise HTTPException(
                status_code=400,
                detail="Missing username, password, or state parameter",
            )

        if not all(
            isinstance(value, str)
            for value in (username, password, state)
        ):
            raise HTTPException(status_code=400, detail="Invalid parameter types")

        redirect_uri = await self.handle_simple_callback(
            username, password, state
        )

        return RedirectResponse(url=redirect_uri, status_code=302)

    async def handle_simple_callback(
        self, username: str, password: str, state: str
    ) -> str:
        """Authenticate the user and create an authorization code."""
        state_data = self.state_mapping.get(state)

        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        redirect_uri = state_data.get("redirect_uri")
        code_challenge = state_data.get("code_challenge")
        client_id = state_data.get("client_id")
        resource = state_data.get("resource")
        redirect_uri_provided_explicitly = (
            state_data.get("redirect_uri_provided_explicitly") == "True"
        )

        if not redirect_uri or not code_challenge or not client_id:
            raise HTTPException(
                status_code=400, detail="Incomplete authorization request"
            )

        if (
            username != self.settings.demo_username
            or password != self.settings.demo_password
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        new_code = f"mcp_{secrets.token_urlsafe(32)}"

        auth_code = AuthorizationCode(
            code=new_code,
            client_id=client_id,
            redirect_uri=AnyHttpUrl(redirect_uri),
            redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
            expires_at=int(time.time()) + 300,
            scopes=[self.settings.mcp_scope],
            code_challenge=code_challenge,
            resource=resource,
            subject=username,
        )

        self.auth_codes[new_code] = auth_code

        self.user_data[username] = {
            "username": username,
            "user_id": f"user_{secrets.token_hex(8)}",
            "authenticated_at": time.time(),
        }

        del self.state_mapping[state]

        return construct_redirect_uri(
            redirect_uri,
            code=new_code,
            state=state,
        )

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        """Load an authorization code for the requesting client."""
        code = self.auth_codes.get(authorization_code)

        if code is None:
            return None

        if code.client_id != client.client_id:
            return None

        if code.expires_at and code.expires_at < time.time():
            del self.auth_codes[authorization_code]
            return None

        return code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Exchange an authorization code for access and refresh tokens."""
        if authorization_code.code not in self.auth_codes:
            raise ValueError("Invalid authorization code")

        if not client.client_id:
            raise ValueError("No client_id provided")

        if authorization_code.client_id != client.client_id:
            raise ValueError("Authorization code belongs to another client")

        if (
            authorization_code.expires_at
            and authorization_code.expires_at < time.time()
        ):
            del self.auth_codes[authorization_code.code]
            raise ValueError("Authorization code expired")

        access_token_value = f"mcp_{secrets.token_urlsafe(32)}"
        refresh_token_value = f"refresh_{secrets.token_urlsafe(32)}"

        self.tokens[access_token_value] = AccessToken(
            token=access_token_value,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 3600,
            resource=authorization_code.resource,
            subject=authorization_code.subject,
        )

        self.refresh_tokens[refresh_token_value] = RefreshToken(
            token=refresh_token_value,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + (30 * 24 * 3600),
            resource=authorization_code.resource,
            subject=authorization_code.subject,
        )

        username = authorization_code.subject or self.settings.demo_username

        self.user_data[access_token_value] = {
            "username": username,
            "user_id": f"user_{secrets.token_hex(8)}",
            "authenticated_at": time.time(),
        }

        del self.auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=access_token_value,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh_token_value,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load an access token if it has not expired."""
        access_token = self.tokens.get(token)

        if access_token is None:
            return None

        if (
            access_token.expires_at is not None
            and access_token.expires_at < time.time()
        ):
            del self.tokens[token]
            self.user_data.pop(token, None)
            return None

        return access_token

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        """Load a valid refresh token belonging to the requesting client."""
        token = self.refresh_tokens.get(refresh_token)

        if token is None:
            return None

        if token.client_id != client.client_id:
            return None

        if token.expires_at is not None and token.expires_at < time.time():
            del self.refresh_tokens[refresh_token]
            return None

        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Exchange a refresh token for new access and refresh tokens."""
        if not client.client_id or refresh_token.client_id != client.client_id:
            raise ValueError("Invalid refresh token client")

        stored_token = self.refresh_tokens.get(refresh_token.token)

        if stored_token is None:
            raise ValueError("Invalid refresh token")

        if (
            stored_token.expires_at is not None
            and stored_token.expires_at < time.time()
        ):
            del self.refresh_tokens[stored_token.token]
            raise ValueError("Refresh token expired")

        requested_scopes = scopes or stored_token.scopes

        if not set(requested_scopes).issubset(set(stored_token.scopes)):
            raise ValueError("Requested scopes exceed granted scopes")

        # Rotate the refresh token so the old one cannot be reused.
        del self.refresh_tokens[stored_token.token]

        new_access_token = f"mcp_{secrets.token_urlsafe(32)}"
        new_refresh_token = f"refresh_{secrets.token_urlsafe(32)}"

        self.tokens[new_access_token] = AccessToken(
            token=new_access_token,
            client_id=client.client_id,
            scopes=requested_scopes,
            expires_at=int(time.time()) + 3600,
            resource=stored_token.resource,
            subject=stored_token.subject,
        )

        self.refresh_tokens[new_refresh_token] = RefreshToken(
            token=new_refresh_token,
            client_id=client.client_id,
            scopes=requested_scopes,
            expires_at=int(time.time()) + (30 * 24 * 3600),
            resource=stored_token.resource,
            subject=stored_token.subject,
        )

        username = stored_token.subject or self.settings.demo_username

        self.user_data[new_access_token] = {
            "username": username,
            "user_id": f"user_{secrets.token_hex(8)}",
            "authenticated_at": time.time(),
        }

        return OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(requested_scopes),
            refresh_token=new_refresh_token,
        )

    async def revoke_token(
        self,
        token: AccessToken | RefreshToken,
    ) -> None:
        """Revoke an access token or refresh token."""
        self.tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)
        self.user_data.pop(token.token, None)
