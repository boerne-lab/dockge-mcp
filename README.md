# Dockge MCP Server

Dockge MCP is a lightweight, powerful server that provides a tool-based API for remotely managing a [Dockge](https://github.com/louislam/dockge) instance. It acts as a bridge, exposing Dockge's real-time, Socket.IO-based API as a set of simple, callable tools via the [FastMCP](https://khulnasoft.com/fastmcp) framework. This enables AI agents, such as [WonderChat](https://apps.apple.com/us/app/wonderchat-ai-vibe-code-app/id6752497385), to directly **call tools** for intelligent orchestration, autonomous operations, and to "vibe manage" your Docker Compose deployments on your couch with your phone.

**⚠️ WARNING: AI Hallucination Risk - Vibe with Care! ⚠️**

AI agents can make mistakes. Incorrect commands or actions due to AI hallucination can lead to unintended consequences, including data loss or service disruption. Always implement robust safeguards and validate AI-generated actions, especially in production environments.

## Features

- **AI-Driven Docker Compose Management**: Empower AI agents to "vibe manage" your Docker Compose stacks.
- **Full Stack Lifecycle Control**: Deploy, start, stop, restart, update, and delete stacks.
- **Real-time Operational Insight**: Get logs and monitor service status.
- **Interactive Debugging**: Open and interact with remote Docker container terminals.
- **Multi-Agent Support**: Manage stacks across multiple Dockge agents/endpoints.
- **Efficient & Persistent**: Intelligent authentication and connection management.

## Architecture

The system consists of three main components:

1.  **Dockge Server**: The target Dockge instance you want to control.
2.  **Dockge MCP (This Project)**: A Python server that connects to Dockge via a persistent Socket.IO client and exposes its functionality.
3.  **MCP Client**: Any application (e.g., a Python script, a command-line tool, a web UI) that makes requests to the Dockge MCP server to perform actions.

```
+--------------+       +--------------------------------+      +-------------------------+
|              |       |                                |      |                         |
|  MCP Client  |------>|           Dockge MCP           |------>|      Dockge Server      |
| (Your Script,|       |                                |      | (Socket.IO Backend)     |
|   Tool, UI)  |       | [FastMCP Server + DockgeClient] |      |                         |
|              |       |                                |      |                         |
+--------------+       +--------------------------------+      +-------------------------+
```

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

### MCP Server URL

Your MCP server will be accessible at the following URL:
```
http://<your-server-ip>:8000/mcp
```
Replace `<your-server-ip>` with the actual IP address or hostname where the Dockge MCP server is running.

## API Reference (Tools)

All tools are exposed via the FastMCP server. The `endpoint` parameter in each tool corresponds to the Dockge agent name. An empty string (`""`) targets the primary, local Dockge instance.

---

### Stack Management

#### `deploy_stack(name: str, composeYAML: str, composeENV: str, isAdd: bool, endpoint: str = "")`
Deploys a Docker Compose stack. This is an asynchronous operation.
- **Returns**: A dictionary with a `terminal_name` to track the deployment log using `get_terminal_logs`.

#### `save_stack(name: str, composeYAML: str, composeENV: str, isAdd: bool, endpoint: str = "")`
Saves the `compose.yaml` and `.env` files for a stack without starting it.
- **Returns**: A confirmation dictionary.

#### `delete_stack(name: str, endpoint: str = "")`
Stops and permanently deletes a stack and its associated files. This is an asynchronous operation.
- **Returns**: A dictionary with a `terminal_name` to track the deletion log.

#### `start_stack(stackName: str, endpoint: str = "")`
Starts a previously stopped stack.
- **Returns**: A `terminal_name` for log tracking.

#### `stop_stack(stackName: str, endpoint: str = "")`
Stops a running stack.
- **Returns**: A `terminal_name` for log tracking.

#### `restart_stack(stackName: str, endpoint: str = "")`
Restarts a stack.
- **Returns**: A `terminal_name` for log tracking.

#### `update_stack(stackName: str, endpoint: str = "")`
Pulls the latest images and redeploys the stack (equivalent to `docker compose pull && docker compose up -d`).
- **Returns**: A `terminal_name` for log tracking.

---

### Information Retrieval

#### `list_stacks()`
Retrieves a list of all stacks from all connected Dockge agents.
- **Returns**: A dictionary where keys are endpoint names and values are the list of stacks for that endpoint.

#### `get_stack(stackName: str, endpoint: str = "")`
Retrierives the detailed configuration (`compose.yaml`, `.env`) for a single stack.
- **Returns**: A dictionary containing the stack's data.

#### `get_stack_service_status(stackName: str, endpoint: str = "")`
Fetches the real-time running status of all services within a stack.
- **Returns**: A dictionary with service status details.

#### `get_docker_network_list()`
Retrieves a list of all Docker networks known to the target agent.
- **Returns**: A list of Docker networks.

---

### Interactive Terminals & Logs

#### `get_terminal_logs(terminal_name: str, last_x_lines: int = 50)`
Fetches the most recent log lines from a terminal session. This is the primary way to check the status of asynchronous operations.
- **`terminal_name`**: The identifier returned by async tools (`deploy_stack`, `start_remote_terminal`, etc.).
- **Returns**: A list of strings, where each string is a line from the terminal buffer.

#### `start_remote_terminal(stack_name: str, service_name: str, endpoint: str = "", shell: str = "bash")`
Starts an interactive shell session inside a running service container.
- **Returns**: A dictionary with a `terminal_name` to be used with `send_remote_command` and `get_terminal_logs`.

#### `send_remote_command(terminal_name: str, command: str, endpoint: str = "")`
Sends a command string to an active interactive terminal.
- **Note**: The command should end with a carriage return (``) for execution, which the client handles automatically.
- **Returns**: A confirmation dictionary. Output from the command must be retrieved using `get_terminal_logs`.

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