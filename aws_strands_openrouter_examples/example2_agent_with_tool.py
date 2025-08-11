import os
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

# It's recommended to set the API key as an environment variable for security.
# export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"

# --- Tool Definition ---
@tool
def calculator(a: int, b: int, operation: str) -> float:
    """
    A simple calculator tool.
    :param a: The first number.
    :param b: The second number.
    :param operation: The operation to perform. Can be 'add', 'subtract', 'multiply', or 'divide'.
    """
    if operation == 'add':
        return float(a + b)
    elif operation == 'subtract':
        return float(a - b)
    elif operation == 'multiply':
        return float(a * b)
    elif operation == 'divide':
        return float(a / b)
    else:
        return "Invalid operation. Please use 'add', 'subtract', 'multiply', or 'divide'."

# --- Model Configuration ---
# Configure the LiteLLM model provider to use OpenRouter
openrouter_model = LiteLLMModel(
    model_id="openrouter/moonshotai/kimi-k2:free",
    client_args={
        "api_key": os.environ.get("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY"),
        "base_url": "https://openrouter.ai/api/v1"
    },
    params={
        "max_tokens": 1024,
        "temperature": 0.7,
    }
)

# --- Agent Creation ---
# Create a Strands Agent with the configured model and the calculator tool
agent = Agent(
    model=openrouter_model,
    tools=[calculator]
)

# --- Task Execution ---
# Define a task that requires both calculation and reasoning
user_task = "What is 25 multiplied by 8? And what is the significance of the result in computing?"

print(f"User Task: {user_task}\n")

# Run the agent to perform the task
# The agent will first use the calculator tool and then use the LLM to answer the second part.
response = agent(user_task)

print("Agent Response:")
print(response)
