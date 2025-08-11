import os
from strands import Agent
from strands.models.litellm import LiteLLMModel

# It's recommended to set the API key as an environment variable for security.
# You can also pass it directly to the LiteLLMModel constructor.
# export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"

# 1. Configure the LiteLLM model provider to use OpenRouter
# The `model_id` is prefixed with `openrouter/` which tells LiteLLM to use the OpenRouter provider.
# The `api_key` and `base_url` are passed in the `client_args`.
openrouter_model = LiteLLMModel(
    model_id="openrouter/moonshotai/kimi-k2:free",
    client_args={
        # Replace with your OpenRouter API key or set the OPENROUTER_API_KEY environment variable
        "api_key": os.environ.get("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY"),
        "base_url": "https://openrouter.ai/api/v1"
    },
    params={
        "max_tokens": 1024,
        "temperature": 0.7,
    }
)

# 2. Create a Strands Agent with the configured model
agent = Agent(model=openrouter_model)

# 3. Define the user's task for the agent
user_task = "Explain the significance of the Turing Test in artificial intelligence."

print(f"User Task: {user_task}\n")

# 4. Run the agent to perform the task
response = agent(user_task)

print("Agent Response:")
print(response)
