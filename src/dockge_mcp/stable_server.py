"""Stable entry point which does not make MCP startup depend on Dockge."""

import asyncio

from .client import dockge_client
from .server import mcp


async def main() -> None:
    try:
        await mcp.run_async(transport="http", host="0.0.0.0", port=8000)
    finally:
        await dockge_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
