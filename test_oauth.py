
import asyncio
import time

from pydantic import AnyHttpUrl
from mcp.server.auth.provider import AuthorizationCode
from mcp.shared.auth import OAuthClientInformationFull

from oauth_provider import SimpleAuthSettings, SimpleOAuthProvider


async def main():
    settings = SimpleAuthSettings(
        demo_username="test-user",
        demo_password="test-password",
    )

    provider = SimpleOAuthProvider(
        settings=settings,
        auth_callback_url="http://127.0.0.1:8000/login",
        server_url="http://127.0.0.1:8000",
    )

    client = OAuthClientInformationFull(
        client_id="test-client",
        redirect_uris=[AnyHttpUrl("http://localhost:8765/callback")],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
    )

    await provider.register_client(client)

    # Create a test authorization code.
    code = AuthorizationCode(
        code="test-authorization-code",
        client_id=client.client_id,
        redirect_uri=AnyHttpUrl("http://localhost:8765/callback"),
        redirect_uri_provided_explicitly=True,
        expires_at=int(time.time()) + 300,
        scopes=["user"],
        code_challenge="test-challenge",
        subject="test-user",
    )
    provider.auth_codes[code.code] = code

    # Exchange the authorization code for tokens.
    first_tokens = await provider.exchange_authorization_code(client, code)
    assert first_tokens.access_token
    assert first_tokens.refresh_token
    assert await provider.load_access_token(first_tokens.access_token)

    # Refresh the tokens.
    old_refresh = first_tokens.refresh_token
    stored_refresh = await provider.load_refresh_token(client, old_refresh)
    assert stored_refresh is not None

    second_tokens = await provider.exchange_refresh_token(
        client, stored_refresh, ["user"]
    )
    assert second_tokens.access_token
    assert second_tokens.refresh_token
    assert second_tokens.refresh_token != old_refresh

    # Confirm the old refresh token cannot be reused.
    assert await provider.load_refresh_token(client, old_refresh) is None

    # Revoke the new access token.
    new_access = await provider.load_access_token(second_tokens.access_token)
    assert new_access is not None
    await provider.revoke_token(new_access)
    assert await provider.load_access_token(second_tokens.access_token) is None

    print("PASS: Authorization code exchange")
    print("PASS: Access and refresh token creation")
    print("PASS: Refresh token rotation")
    print("PASS: Old refresh token rejected")
    print("PASS: Access token revocation")
    print("\nAll token-method tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
