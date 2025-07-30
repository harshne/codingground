# FastMCP Server

This project is a FastAPI server that acts as a "Model Context Protocol" (MCP) server for interacting with the `nova-act` library. It allows you to start, control, and stop `nova-act` browser sessions through a simple REST API.

## Prerequisites

- Python 3.10 or higher
- Access to the `nova-act` library and a valid `NOVA_ACT_API_KEY`.

## Setup

1.  **Clone the repository or download the source code.**

2.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Set the `NOVA_ACT_API_KEY` environment variable:**

    Before running the server, you must set your `nova-act` API key as an environment variable.

    On macOS and Linux:
    ```bash
    export NOVA_ACT_API_KEY="your_api_key"
    ```

    On Windows:
    ```bash
    set NOVA_ACT_API_KEY="your_api_key"
    ```

## Running the Server

To run the server, use `uvicorn`:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`.

## API Documentation

The server provides a Swagger UI for interactive API documentation. Once the server is running, you can access it at `http://localhost:8000/docs`.

### API Endpoints

#### `POST /session/start`

Starts a new `nova-act` session.

-   **Request Body:**
    ```json
    {
      "start_url": "https://www.example.com"
    }
    ```
-   **Response:**
    ```json
    {
      "session_id": "a_unique_session_id"
    }
    ```

#### `POST /session/{session_id}/act`

Performs a natural language action in an active session.

-   **Request Body:**
    ```json
    {
      "command": "click the login button"
    }
    ```
-   **Response:**
    ```json
    {
      "response": "The response from nova-act"
    }
    ```

#### `GET /session/{session_id}/screenshot`

Takes a screenshot of the current page in the session.

-   **Response:**
    ```json
    {
      "screenshot": "a_hex_encoded_string_of_the_screenshot_bytes"
    }
    ```

#### `POST /session/{session_id}/stop`

Stops a `nova-act` session.

-   **Response:**
    ```json
    {
      "message": "Session stopped successfully"
    }
    ```
