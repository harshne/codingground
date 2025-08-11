# AWS Strands Agents with OpenRouter Examples

This directory contains examples of how to use the AWS Strands Agents SDK with OpenRouter as the model provider. The examples use the `moonshotai/kimi-k2:free` model.

## Setup

1.  **Install Dependencies:**
    Install the necessary Python packages using the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Your API Key:**
    These examples require an OpenRouter API key. You can set it as an environment variable, which is the recommended approach for security.

    **On macOS/Linux:**
    ```bash
    export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
    ```

    **On Windows:**
    ```bash
    set OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
    ```

    Replace `"YOUR_OPENROUTER_API_KEY"` with your actual key. Alternatively, you can hardcode the key in the Python scripts, but this is not recommended for production code.

## Examples

### Example 1: Basic Agent

*   **File:** `example1_basic_agent.py`
*   **Description:** This example demonstrates how to create a simple Strands agent that uses the `moonshotai/kimi-k2:free` model on OpenRouter to answer a question.
*   **To Run:**
    ```bash
    python example1_basic_agent.py
    ```

### Example 2: Agent with a Tool

*   **File:** `example2_agent_with_tool.py`
*   **Description:** This example shows how to equip a Strands agent with a tool (a simple calculator). The agent uses the tool for calculations and the OpenRouter model for reasoning.
*   **To Run:**
    ```bash
    python example2_agent_with_tool.py
    ```

### Example 3: Multi-Agent Swarm

*   **File:** `example3_multi_agent_swarm.py`
*   **Description:** This is a more advanced example that demonstrates a multi-agent swarm. It features a "Researcher" agent and a "Writer" agent that collaborate to perform a task. Both agents use the same OpenRouter model configuration. The swarm will create a file named `python_history.txt` in the same directory.
*   **To Run:**
    ```bash
    python example3_multi_agent_swarm.py
    ```
