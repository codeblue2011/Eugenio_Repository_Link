
from server import ROOT_FOLDER, get_safe_path

print("Authorized workspace:", ROOT_FOLDER)

# Test 1: A normal relative path should be allowed
try:
    result = get_safe_path("mcp_test.txt")
    print("NORMAL PATH: ALLOWED")
    print("Resolved path:", result)
except ValueError as error:
    print("NORMAL PATH: UNEXPECTEDLY BLOCKED", error)

# Test 2: A path that tries to leave the workspace should be blocked
try:
    result = get_safe_path("../mcp-file-server-project/server.py")
    print("SECURITY TEST FAILED: ESCAPE WAS ALLOWED")
    print("Resolved path:", result)
except ValueError as error:
    print("SECURITY TEST PASSED: ESCAPE BLOCKED")
    print(error)
