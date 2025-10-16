# Dockge MCP Server

Dockge MCP is a lightweight, powerful server that provides a tool-based API for remotely managing a [Dockge](https://github.com/louislam/dockge) instance. It acts as a bridge, exposing Dockge's real-time, Socket.IO-based API as a set of simple, callable tools via the [FastMCP](https://khulnasoft.com/fastmcp) framework. This enables AI agents, such as [WonderChat](https://apps.apple.com/us/app/wonderchat-ai-vibe-code-app/id6752497385), to directly **call tools** for intelligent orchestration, autonomous operations, and to "vibe manage" your Docker Compose deployments on your couch with your phone.

**⚠️ WARNING: AI Hallucination Risk - Vibe with Care! ⚠️**

AI agents can make mistakes. Incorrect commands or actions due to AI hallucination can lead to unintended consequences, including data loss or service disruption. Always implement robust safeguards and validate AI-generated actions, especially in production environments.

## Why Dockge?

-   Stacks are funner than single container.
-   Has exec shell.
-   Multi-cluster and easy remote integration.

## Features

- **AI-Driven Docker Compose Management**: Empower AI agents to "vibe manage" your Docker Compose stacks.
- **Full Stack Lifecycle Control**: Deploy, start, stop, restart, update, and delete stacks.
- **Real-time Operational Insight**: Get logs and monitor service status.
- **Interactive Debugging**: Open and interact with remote Docker container terminals.
- **Multi-Agent Support**: Manage stacks across multiple Dockge agents/endpoints.

## Demo
LLM running commands in a exec shell:

https://github.com/user-attachments/assets/4482c7e3-cc97-4d2b-9d26-e7126b134435

Deploying a Wordpress stack:

https://github.com/user-attachments/assets/dde4c5b4-d343-42bd-9852-7cfe286ece88


## Getting Started

### Prerequisites

- Python 3.10+
- Access to a running Dockge instance (v1.x)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/wonderchatai/dockge-mcp.git
    cd dockge-mcp
    ```

2.  **Install dependencies:**
    This project uses `uv` for package management.
    ```bash
    uv sync
    ```

### Configuration

Configuration is managed via a `.env` file. Copy the example file and edit it with your Dockge instance details.

1.  **Create the `.env` file:**
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`:**
    ```dotenv
    # URL for the Dockge Socket.IO server
    DOCKGE_URL="http://localhost:5001"

    # Credentials for Dockge
    DOCKGE_USERNAME="admin"
    DOCKGE_PASSWORD="your-dockge-password"
    ```

### Running the Server

Once configured, you can start the MCP server:

```bash
uv run dockge-server
```

The FastMCP server will start, typically on `http://0.0.0.0:8000`. You can now send requests to its tool endpoints.

### Docker

You can also run Dockge MCP using Docker Compose.

1.  **Create the `.env` file:**
    ```bash
    cp .env.example .env
    ```
    Edit `.env` with your Dockge instance details.

2.  **Run with Docker Compose:**
    ```bash
    docker compose up -d
    ```
    This will pull the `dockge-mcp` image and start the container in detached mode.

### MCP Server URL

Your MCP server will be accessible at the following URL:
```
http://<your-server-ip>:8000/mcp
```
Replace `<your-server-ip>` with the actual IP address or hostname where the Dockge MCP server is running.

## API Reference (Tools)

All tools are exposed via the FastMCP server. The `endpoint` parameter in each tool corresponds to the Dockge agent name. An empty string (`""`) targets the primary, local Dockge instance.

---

- `deploy_stack`
- `save_stack`
- `delete_stack`
- `start_stack`
- `stop_stack`
- `restart_stack`
- `update_stack`
- `list_stacks`
- `get_stack`
- `get_stack_service_status`
- `get_docker_network_list`
- `get_terminal_logs`
- `start_remote_terminal`
- `send_remote_command`


## How It Works

### Connection and Authentication
The `DockgeClient` establishes a persistent Socket.IO connection to the Dockge server. On the first API call, it authenticates using the provided username and password. The server returns a JWT, which is cached by the client. For subsequent calls, the cached JWT is used for authentication, bypassing the need for a full login until the token expires.

### Asynchronous Operations and Log Handling
Many Docker operations take time (e.g., pulling images, building containers). Dockge handles this by streaming terminal output over Socket.IO.

Dockge MCP mirrors this behavior:
1.  When you call an asynchronous tool like `deploy_stack`, the MCP server tells Dockge to start the process.
2.  Dockge creates a unique terminal session for this action.
3.  The MCP server immediately returns the `terminal_name` for that session.
4.  The MCP client simultaneously starts listening for log events associated with that `terminal_name`, storing them in an in-memory buffer (`deque`).
5.  Your application can then call `get_terminal_logs(terminal_name=...)` repeatedly to fetch the latest output and monitor the progress or see the final result of the operation.

This design prevents long-running HTTP requests and provides a responsive, real-time experience, even over a stateless protocol like HTTP.

## WonderChat

Manage your Dockge instance from anywhere with [WonderChat](https://wonderchat.dev).

<a href="https://apps.apple.com/us/app/wonderchat-ai/id6752497385" target="_blank">
  <img src="https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg" alt="Download on the App Store" height="50">
</a>
