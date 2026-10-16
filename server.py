
import os
from pathlib import Path

import uvicorn
from pydantic import AnyHttpUrl
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from oauth_provider import SimpleAuthSettings, SimpleOAuthProvider


# ============================================================
# SERVER AND OAUTH CONFIGURATION
# ============================================================

# Use localhost for local testing.
# Set MCP_SERVER_URL to the public HTTPS URL when deploying.
SERVER_URL = os.environ.get(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

# Load credentials from environment variables.
# Required variables: MCP_DEMO_USERNAME and MCP_DEMO_PASSWORD.
auth_settings = SimpleAuthSettings()

# Initialize the OAuth provider.
oauth_provider = SimpleOAuthProvider(
    settings=auth_settings,
    auth_callback_url=f"{SERVER_URL}/login",
    server_url=SERVER_URL,
)

# Create the MCP server with OAuth authentication.
mcp = MCPServer(
    "Local File Server",
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(SERVER_URL),
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[auth_settings.mcp_scope],
            default_scopes=[auth_settings.mcp_scope],
        ),
        required_scopes=[auth_settings.mcp_scope],
        resource_server_url=None,
    ),
)


# ============================================================
# WORKSPACE SANDBOX
# ============================================================

# This is the ONLY folder the MCP server is allowed to access.
ROOT_FOLDER = (Path.home() / "MCP-File-Server").resolve()


def get_safe_path(relative_path: str) -> Path:
    """
    Convert a relative path into a safe path inside ROOT_FOLDER.
    Reject paths that attempt to escape the workspace.
    """
    requested_path = (ROOT_FOLDER / relative_path).resolve()

    try:
        requested_path.relative_to(ROOT_FOLDER)
    except ValueError:
        raise ValueError(
            "Access denied: path is outside the workspace."
        )

    return requested_path


# ============================================================
# OAUTH LOGIN ROUTES
# ============================================================

@mcp.custom_route("/login", methods=["GET"])
async def login_page_handler(request: Request) -> Response:
    """Display the login page during the OAuth authorization flow."""
    state = request.query_params.get("state")

    if not state:
        raise HTTPException(
            status_code=400,
            detail="Missing state parameter.",
        )

    return await oauth_provider.get_login_page(state)


@mcp.custom_route("/login/callback", methods=["POST"])
async def login_callback_handler(request: Request) -> Response:
    """Validate login credentials and redirect to the OAuth client."""
    return await oauth_provider.handle_login_callback(request)


# ============================================================
# TOOL 1: LIST FILES
# ============================================================

@mcp.tool()
def list_files() -> str:
    """List the files and folders inside the authorized workspace."""
    if not ROOT_FOLDER.is_dir():
        return "Workspace folder does not exist."

    items = []

    for item in sorted(ROOT_FOLDER.iterdir()):
        if item.is_dir():
            items.append(f"[Folder] {item.name}")
        else:
            items.append(f"[File] {item.name}")

    return "\n".join(items) if items else "The workspace is empty."


# ============================================================
# TOOL 2: READ FILE
# ============================================================

@mcp.tool()
def read_file(relative_path: str) -> str:
    """Read a text file inside the authorized workspace."""
    file_path = get_safe_path(relative_path)

    if not file_path.is_file():
        raise ValueError("The requested path is not a file.")

    return file_path.read_text(encoding="utf-8")


# ============================================================
# TOOL 3: WRITE FILE
# ============================================================

@mcp.tool()
def write_file(relative_path: str, content: str) -> str:
    """Create or overwrite a text file inside the authorized workspace."""
    file_path = get_safe_path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return f"File written successfully: {relative_path}"


# ============================================================
# TOOL 4: REPLACE TEXT
# ============================================================

@mcp.tool()
def str_replace(
    relative_path: str,
    old_text: str,
    new_text: str,
) -> str:
    """Replace specific text inside a text file."""
    file_path = get_safe_path(relative_path)

    if not file_path.is_file():
        raise ValueError("The requested path is not a file.")

    content = file_path.read_text(encoding="utf-8")

    if old_text not in content:
        raise ValueError("The text to replace was not found in the file.")

    updated_content = content.replace(old_text, new_text)
    file_path.write_text(updated_content, encoding="utf-8")

    return f"Text replaced successfully in: {relative_path}"


# ============================================================
# TOOL 5: DELETE FILE
# ============================================================

@mcp.tool()
def delete_file(relative_path: str) -> str:
    """Delete a file inside the authorized workspace."""
    file_path = get_safe_path(relative_path)

    if not file_path.is_file():
        raise ValueError("The requested path is not a file.")

    file_path.unlink()

    return f"File deleted successfully: {relative_path}"


# ============================================================
# TOOL 6: SEARCH FILES
# ============================================================

@mcp.tool()
def search_files(search_text: str) -> str:
    """Search for text inside files in the authorized workspace."""
    results = []

    for file_path in ROOT_FOLDER.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        if search_text.lower() in content.lower():
            results.append(str(file_path.relative_to(ROOT_FOLDER)))

    if not results:
        return f"No files found containing: {search_text}"

    return "Files containing the search text:\n" + "\n".join(results)


# ============================================================
# TOOL 7: CREATE DIRECTORY
# ============================================================

@mcp.tool()
def make_directory(relative_path: str) -> str:
    """Create a directory inside the authorized workspace."""
    directory_path = get_safe_path(relative_path)
    directory_path.mkdir(parents=True, exist_ok=True)

    return f"Directory created successfully: {relative_path}"


# ============================================================
# TOOL 8: GIT STATUS
# ============================================================

@mcp.tool()
def git_status() -> str:
    """Show the Git status of the authorized workspace."""
    import subprocess

    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT_FOLDER,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"Git error: {result.stderr.strip()}"

    if not result.stdout.strip():
        return "Git status: working tree is clean."

    return "Git status:\n" + result.stdout


# ============================================================
# START THE MCP SERVER
# ============================================================

if __name__ == "__main__":
    app = mcp.streamable_http_app(
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                "127.0.0.1:*",
                "localhost:*",
                "induction-caution-bedrooms-mostly.trycloudflare.com",
            ],
        ),
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
