# Technical Decisions

Last updated: 2026-10-16 (finalization pass)

## 1. Programming Language
Decision: Python
Reason: Python supports the MCP SDK (version 2.3.0, Python 3.13 on Windows 10) and is suitable for implementing filesystem tools.

## 2. Workspace Isolation
Decision: Use a dedicated workspace root at C:\Users\Dana Anika\MCP-File-Server.
Reason: Filesystem operations should be limited to a specific authorized directory.

## 3. Path Validation
Decision: Resolve requested paths and verify they remain inside the resolved workspace root; reject anything outside it.
Reason: This helps block path traversal attempts. Basic tests passed (a path traversal attempt was rejected), but additional filesystem edge cases still require review.

## 4. MCP Transport
Decision: Streamable HTTP, served locally on port 8000.
Reason: This provides an HTTP endpoint for local MCP client testing and for tunneling to remote clients.

## 5. Tool Scope
Decision: Provide eight tools covering listing, reading, writing, replacement, deletion, searching, directory creation, and Git status.
Reason: These cover the assignment's basic file-management and search/Git-lite requirements.

## 6. Remote Access
Decision: Expose the server remotely only behind authentication. Remote access uses a Cloudflare HTTPS Quick Tunnel, and Claude Desktop connects through the current project URL.
Reason: The server can modify files, so an unprotected public endpoint would create unnecessary risk. Quick Tunnel URLs can change on restart, so the URL is not recorded in these files. A Quick Tunnel is temporary and suited to demonstration, not a permanent production deployment.

## 7. Secret Handling
Decision: Keep authentication tokens, passwords, and client secrets private and out of source code, reports, handoff files, and Git commits.
Reason: Anyone who obtains a valid credential may gain access to protected functionality.

## 8. Validation
Decision: Use a real Python MCP client and Claude Desktop for integration tests, and record results in the handoff files.
Reason: Client-based testing verifies more than simply starting the server.

## 9. Authentication Method
Decision: Use OAuth for authentication.
Reason: The server is reachable through a public tunnel and has write and delete tools. OAuth login and token exchange succeeded during testing. The implementation is a simplified demonstration that stores authorization state in memory; it is not production-ready. Validation of OAuth-protected resource metadata endpoints is still pending.

## 10. Transport Security and Hostname Validation
Decision: Update the server's transport security configuration to accept the tunnel hostname.
Reason: A hostname-validation issue caused HTTP 421 errors. After the update, Claude completed real tool calls.

## 11. Git Status Behavior
Decision: Keep git_status as one of the eight tools. It currently returns "not a git repository" because the workspace has not been initialized as a Git repository.
Reason: The tool itself works. Whether to initialize a repository is still undecided; Git must not be initialized without explicit approval.

## 12. Test Artifacts
Decision: Keep mcp_test_folder in the workspace intentionally. mcp_write_test.txt was deleted after testing. SESSION_HANDOFF_TEST.txt and SESSION_HANDOFF_TEST_2.txt are kept as handoff-test evidence and must not be overwritten.
Reason: The folder remains as evidence of directory creation testing; the temporary test file was removed; the handoff test files document the multi-session test.

## 13. Process Management with PM2 (added in finalization pass)
Decision: Use PM2 to run the Python server as the process `local-file-server`.
Reason: PM2 keeps the server running in the background and can restart it. `pm2 list` showed the process online, and a restart test succeeded (process returned online, restart count incremented). Limits: the Cloudflare tunnel is not managed by PM2; automatic recovery from an unexpected crash and startup after a Windows reboot have not been verified.

## 14. OAuth Reauthorization After Restart (added in finalization pass)
Decision: Accept that a server restart requires browser-based OAuth reauthorization in Claude Desktop.
Reason: Authorization state is held in memory, so a restart discards it. After reauthorizing, Claude Desktop successfully read Hello.txt. Persistent storage of authorization state would be required to avoid this and is out of scope for the demonstration.

## 15. Multi-Session Handoff Method (added in finalization pass)
Decision: Use the handoff documents plus a small test file for continuity across separate Claude Desktop conversations.
Reason: A fresh conversation has no prior context. The first conversation created and read SESSION_HANDOFF_TEST_2.txt; a fresh conversation then read that file and the four handoff documents without tool errors.
