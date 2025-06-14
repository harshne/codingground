# Strands Agent with OpenRouter, Chainlit UI, and SQLite Database

## Overview

This project demonstrates a Python application featuring an AI agent built with the Strands Agents SDK. The agent utilizes language models via OpenRouter.ai and interacts with a SQLite database to manage data about children. The user interface is provided by Chainlit, offering an interactive chat experience.

The agent is equipped with tools to perform CRUD-like operations on a `children` database, allowing users to query, add, and update records through natural language conversation.

## Features

-   **Conversational AI Agent:** Powered by Strands SDK and OpenRouter models.
-   **Chainlit Web UI:** Modern, interactive chat interface.
-   **SQLite Database:** Manages data for children (name, payments, status, etc.).
-   **Database Management Tools:** Agent can:
    -   Add new child records.
    -   Retrieve details for specific children.
    -   Update payment information.
    -   Set a child's active status.
    -   List children by parent.
    -   List all active children.
-   **Custom Model Provider:** Uses a custom Strands `Model` class (`OpenRouterModel`) to integrate with OpenRouter.ai, compatible with OpenAI API standards.
-   **Configuration via `.env`:** Securely manage API keys and model settings.

## Directory Structure

```
strands_openrouter_app/
├── app.py                  # Main Chainlit application file
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment variables file
├── .gitignore              # Git ignore file
├── children.db             # SQLite database file (created on first run)
├── src/
│   ├── __init__.py
│   ├── agent_tools.py      # Agent's database interaction tools
│   ├── custom_model_provider/
│   │   ├── __init__.py
│   │   └── openrouter_provider.py # Custom Strands Model for OpenRouter
│   └── database/
│       ├── __init__.py
│       ├── models.py       # SQLAlchemy database models (Child table)
│       └── setup.py        # Database initialization and test data
└── main.py                 # Original CLI application (can be used for testing)
```

## Setup Instructions

### 1. Prerequisites

-   Python 3.10+

### 2. Clone the Repository (if applicable)

If you've obtained this as a set of files, ensure they are within a single project directory (e.g., `strands_openrouter_app`).

### 3. Create a Virtual Environment

It's highly recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies

Navigate to the project root directory (`strands_openrouter_app`) and install the required packages:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

-   Copy the example `.env.example` file to a new file named `.env` in the project root:
    ```bash
    cp .env.example .env
    ```
-   Edit the `.env` file and add your `OPENROUTER_API_KEY`:
    ```env
    OPENROUTER_API_KEY="your_openrouter_api_key_here"

    # Optional: Specify a preferred OpenRouter model
    # See https://openrouter.ai/models for available models
    OPENROUTER_MODEL_ID="mistralai/mistral-7b-instruct-free"
    # OPENROUTER_MODEL_ID="openai/gpt-3.5-turbo" # Example for a more capable model

    # Optional: For testing tools that require more capable models
    # OPENROUTER_TOOL_MODEL_ID="openai/gpt-3.5-turbo"

    # Optional: Other model parameters
    # OPENROUTER_TEMPERATURE=0.7
    # OPENROUTER_MAX_TOKENS=1500

    # Optional: For OpenRouter leaderboard/identification (replace with your actual info if desired)
    # HTTP_REFERER="https://your-app-url.com"
    # X_TITLE="My Strands Agent App"
    ```

## Database Initialization

The SQLite database (`children.db`) and its tables will be automatically created (if they don't exist) when you first run the Chainlit application. Test data will also be added if the database is new.

Alternatively, you can initialize the database and add test data manually by running:
```bash
python src/database/setup.py
```
(Ensure your virtual environment is active and you are in the `strands_openrouter_app` directory, or adjust the Python path accordingly if running from elsewhere).

## Running the Application

To start the Chainlit web application:

1.  Ensure your virtual environment is active.
2.  Navigate to the project root directory (`strands_openrouter_app`).
3.  Run the following command:
    ```bash
    chainlit run app.py -w
    ```
    The `-w` flag enables auto-reloading, so the app will restart if you make code changes.

4.  Open your web browser and go to the address shown in the terminal (usually `http://localhost:8000`).

## Usage

Once the application is running, you can interact with the agent through the chat interface:

-   **General Conversation:** Ask general questions. The agent will use its underlying OpenRouter model.
-   **Data Management:** Ask questions or give commands related to children's data. Examples:
    -   "What are the details for Alice Smith?"
    -   "Can you add a new child named 'Leo Miller' with parent 'Sarah Miller', monthly payment 120, last payment date '01-18-2024', batch 'B5', and status active?"
    -   "Update the payment for Bob Johnson to $160 and the last payment date to 01-22-2024."
    -   "Is Diana Prince active?"
    -   "Set Charlie Brown to be active."
    -   "List all children whose parent is John Smith."
    -   "Show me all active children."

The agent will use its tools to interact with the database. You should see visual indicators (Steps) in the Chainlit UI when a tool is being used.

## Agent Tools

The agent is equipped with the following tools to manage the `children` database:

-   `add_child`: Adds a new child record.
-   `get_child_details`: Retrieves details for a specific child.
-   `update_child_payment`: Updates a child's monthly payment and last payment date.
-   `set_child_active_status`: Sets a child's active status (active/inactive).
-   `list_children_by_parent`: Lists all children for a given parent.
-   `list_active_children`: Lists all children currently marked as active.

## Custom Model Provider

This application uses a custom Strands `Model` implementation called `OpenRouterModel` (located in `src/custom_model_provider/openrouter_provider.py`). This class adapts the Strands agent framework to use any OpenAI-compatible model available through OpenRouter.ai.

---

Happy Chatting!
