
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    url = "http://127.0.0.1:8000/mcp"

    async with streamable_http_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Create a test file
            created = await session.call_tool(
                "write_file",
                {
                    "relative_path": "mcp_test.txt",
                    "content": "MCP file operation test successful!"
                }
            )
            print("WRITE RESULT:")
            print(created)

            # Read the test file
            read = await session.call_tool(
                "read_file",
                {"relative_path": "mcp_test.txt"}
            )
            print("\nREAD RESULT:")
            print(read)


if __name__ == "__main__":
    asyncio.run(main())
