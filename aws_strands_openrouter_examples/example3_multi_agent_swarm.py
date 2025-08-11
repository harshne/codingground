import os
import logging
from strands import Agent, tool
from strands.models.litellm import LiteLLMModel
from strands.multiagent import Swarm

# --- Setup Logging ---
# Optional: Enable Strands debug logs to see the agent interactions.
logging.getLogger("strands.multiagent").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# --- Tool Definitions ---
@tool
def web_search(query: str) -> str:
    """
    A mock web search tool. In a real application, this would use a search API.
    """
    print(f"--- TOOL: Searching the web for '{query}' ---")
    if "python" in query.lower() and "history" in query.lower():
        return "Python was conceived in the late 1980s by Guido van Rossum at Centrum Wiskunde & Informatica (CWI) in the Netherlands. Its implementation began in December 1989. Van Rossum shouldered sole responsibility for the project, as the lead developer, until 12 July 2018, when he announced his 'permanent vacation' from his responsibilities as Python's Benevolent Dictator For Life."
    return "No information found for this query."

@tool
def file_writer(filename: str, content: str) -> str:
    """
    Writes content to a file.
    """
    print(f"--- TOOL: Writing to file '{filename}' ---")
    try:
        with open(filename, "w") as f:
            f.write(content)
        return f"Successfully wrote content to {filename}"
    except Exception as e:
        return f"Error writing to file: {e}"

# --- Model Configuration ---
# Configure the LiteLLM model provider to use OpenRouter.
# This single model configuration will be shared by all agents in the swarm.
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

# --- Agent Definitions ---
# Define specialized agents. Each has a specific role and set of tools.
researcher_agent = Agent(
    name="Researcher",
    system_prompt="You are a research specialist. Your job is to find information using the tools provided.",
    model=openrouter_model,
    tools=[web_search]
)

writer_agent = Agent(
    name="Writer",
    system_prompt="You are a technical writer. Your job is to compose clear and concise summaries from the given information and save them to a file.",
    model=openrouter_model,
    tools=[file_writer]
)

# --- Swarm Creation ---
# A Swarm allows agents to collaborate to solve a problem.
# The swarm will automatically coordinate the agents.
research_and_write_team = Swarm([researcher_agent, writer_agent])

# --- Task Execution ---
user_task = "Research the history of the Python programming language and write a short summary to a file named 'python_history.txt'."

print(f"User Task: {user_task}\n")

# Run the swarm to perform the task
response = research_and_write_team(user_task)

print("\nSwarm Final Response:")
print(response)

# Verify that the file was created
if os.path.exists("python_history.txt"):
    print("\n--- Verification ---")
    print("File 'python_history.txt' created successfully. Contents:")
    with open("python_history.txt", "r") as f:
        print(f.read())
