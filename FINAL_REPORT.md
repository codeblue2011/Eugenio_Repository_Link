# Final Report: Local MCP File Server

Last updated: 2026-10-16

## Project Overview

This project is a local file server built with the Model Context Protocol (MCP). MCP is a standard way for an AI client, such as Claude Desktop, to call tools on a server. The server lets Claude list, read, write, edit, search, and delete files inside one authorized workspace folder, and it is reachable from Claude Desktop over HTTPS. The goal was to do this safely: Claude should only be able to touch files inside the workspace, and only after logging in.

## Technology Stack

- **Language and SDK:** Python 3.13 with MCP SDK 2.3.0.
- **Operating system:** Windows 10, 64-bit.
- **Transport:** Streamable HTTP, served locally at `http://127.0.0.1:8000`.
- **Remote access:** a Cloudflare Quick Tunnel that gives the local server a temporary HTTPS address.
- **Authentication:** OAuth (a simplified demonstration implementation).
- **Process management:** PM2, which runs the server as the process `local-file-server`.
- **Test clients:** a Python MCP client, MCP Inspector (in earlier testing), and Claude Desktop.

## MCP Tools and Design Choices

The server exposes eight tools:

| Tool | Purpose |
|---|---|
| `list_files` | List files and folders in the workspace |
| `read_file` | Read a text file |
| `write_file` | Create or overwrite a text file |
| `str_replace` | Replace specific text inside a file |
| `delete_file` | Delete a file |
| `search_files` | Search for text inside files |
| `make_directory` | Create a folder |
| `git_status` | Show Git status of the workspace |

Design choices:

- **Small, single-purpose tools.** Each tool does one job, which makes behavior easier to predict and test.
- **`str_replace` alongside `write_file`.** A targeted edit avoids rewriting a whole file when only one passage changes.
- **Consistent argument names.** File tools take `relative_path`, so every path is interpreted relative to the workspace root.
- **`git_status` kept as-is.** It works, but the workspace is not a Git repository, so it reports "not a git repository." Git was deliberately not initialized, since that is a separate decision that needs approval.

## Workspace Sandboxing and Security

All file operations are confined to one workspace root. The path-validation approach is:

1. Take the requested relative path and join it to the workspace root.
2. **Resolve** the result to an absolute path, which collapses `..` segments and follows symbolic links.
3. Check that the resolved path is still **inside** the resolved workspace root.
4. If it is not, reject the request.

Resolving before checking is the key idea. A simple text check for `..` can be fooled, but comparing fully resolved paths checks where the path actually ends up.

In testing, a normal workspace path was accepted and a path traversal attempt (a path resolving outside the workspace) was rejected. This is a basic test. It does not prove protection against every possible filesystem edge case.

Because the server can write and delete files and is reachable through a public tunnel, it requires OAuth login. Credentials, tokens, and secrets are kept out of the handoff files and this report.

## HTTPS Tunnel and Process Management

**Cloudflare Quick Tunnel.** Claude Desktop needs an HTTPS address to reach the server, but the server only listens on localhost. A Cloudflare Quick Tunnel forwards a temporary public HTTPS URL to the local server. An early problem with this setup was HTTP 421 errors caused by hostname validation; updating the server's transport security configuration to accept the tunnel hostname fixed it.

**PM2.** PM2 is a process manager. It runs the Python server in the background, keeps track of its status, and can restart it. `pm2 list` showed `local-file-server` online, and a restart test succeeded: the process came back online with its restart count incremented.

**OAuth reauthorization after a restart.** The OAuth implementation keeps its authorization state in memory. When the server restarts, that state is lost, so Claude Desktop had to go through browser-based OAuth reauthorization. After reauthorizing, it successfully read `Hello.txt`. This is expected behavior for an in-memory design, not a bug in PM2.

**Why a Quick Tunnel is not a production deployment.** Quick Tunnel URLs are temporary and can change whenever the tunnel is restarted, so the connection address is not stable. It is intended for demonstrations and testing. A permanent deployment would use a stable, managed hostname and a tunnel or hosting setup that is itself monitored and restarted automatically. In this project, the tunnel runs separately and is not managed by PM2.

## Testing and Results

Verified results:

- The server starts on localhost port 8000 using Streamable HTTP.
- A Python MCP client connected and discovered all eight tools.
- Path validation accepted a normal workspace path and rejected a path traversal attempt.
- OAuth login and token exchange succeeded.
- Claude Desktop connected through the Cloudflare HTTPS Quick Tunnel, listed files, read files, and completed file write/read tests. The full tool sequence confirmed through Claude was: list, read `Hello.txt`, write a test file, check it exists, search its contents, create a folder, replace text, and delete the test file.
- `git_status` executed and reported that the workspace is not a Git repository.
- PM2 manages `local-file-server`; `pm2 list` showed it online.
- A PM2 restart test succeeded, with the process returning online and its restart count incremented.
- After the restart, Claude Desktop required browser-based OAuth reauthorization and then successfully read `Hello.txt`.
- **Multi-session handoff test.** In one Claude Desktop conversation, `SESSION_HANDOFF_TEST_2.txt` was created and read. In a fresh, separate conversation, that file and the four handoff documents (`PROJECT_STATE.md`, `PLAN_LOG.md`, `CHECKPOINTS.md`, `DECISIONS.md`) were read without tool errors.

Not tested: crash recovery, startup after a Windows reboot, and OAuth-protected resource metadata endpoints.

## Security Tradeoffs and Limitations

- **Demonstration-grade OAuth.** Authorization state is stored in memory, so it is lost on restart and the implementation is not production-ready authentication.
- **Public exposure.** The tunnel makes a server with write and delete tools reachable from the internet, so access control matters more than it would for a purely local server.
- **Tunnel not managed by PM2.** If the tunnel stops, remote access stops until it is restarted by hand, and the URL may change.
- **Unverified resilience.** Automatic recovery from an unexpected crash and automatic startup after a Windows reboot have not been verified.
- **Incomplete security review.** OAuth-protected resource metadata endpoint validation and broader security and error-handling reviews remain incomplete.
- **Path validation is basic.** It passed a traversal test but has not been tested against every filesystem edge case.
- **No Git repository.** `git_status` reports that the workspace is not a Git repository; Git was not initialized and should not be without approval.
- **Documentation may lag.** The workspace listing in the handoff documents may be outdated, since the handoff test files were created after earlier versions were written.

## Conclusion

The project met its main goals. It is a working Python MCP file server with eight tools, a sandboxed workspace, HTTPS access for Claude Desktop through a Cloudflare Quick Tunnel, OAuth login, and PM2 process management with a successful restart test. A two-conversation handoff test showed that a fresh Claude Desktop session can pick up the project state from the files alone. It is a solid demonstration, but not a production system: the OAuth implementation is simplified, the tunnel is temporary and unmanaged, crash and reboot recovery are unverified, and further security review is still needed.
