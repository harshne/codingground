import chainlit as cl
import os
import logging
import sys
import json # For parsing event_str from agent.stream_events_async

from dotenv import load_dotenv

from strands import Agent
# Make sure src is discoverable for custom_model_provider and other src modules
# This line should be at the very top if possible, or before local src imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))) # Adds project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))) # Adds src to path


from custom_model_provider.openrouter_provider import OpenRouterModel
from database.setup import init_db, add_test_data, get_db_session # Import add_test_data and get_db_session
from agent_tools import get_tools # This function should return the list of DB tools

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file in the root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

@cl.on_chat_start
async def start_chat():
    logger.info("Chat started. Initializing database and agent...")

    try:
        # Initialize database and add test data if the DB is new/empty
        init_db()
        with get_db_session() as session: # Use context manager for session
            add_test_data(session) # Populate with test data if needed
        logger.info("Database initialized and checked for test data.")
    except Exception as e:
        await cl.Message(content=f"Error initializing database: {e}").send()
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        return

    api_key = os.getenv("OPENROUTER_API_KEY")
    model_id = os.getenv("OPENROUTER_MODEL_ID", "mistralai/mistral-7b-instruct-free")
    temperature = float(os.getenv("OPENROUTER_TEMPERATURE", 0.7))
    max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", 1500)) # Increased max_tokens for potentially longer tool outputs + reasoning
    http_referer = os.getenv("HTTP_REFERER", "http://localhost/chainlit-strands-app")
    x_title = os.getenv("X_TITLE", "Chainlit Strands OpenRouter Agent")

    if not api_key:
        await cl.Message(content="Configuration Error: OPENROUTER_API_KEY not found. Please set it in your .env file.").send()
        logger.error("CRITICAL: OPENROUTER_API_KEY not found.")
        return

    try:
        openrouter_model = OpenRouterModel(
            model_id=model_id,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            http_referer=http_referer,
            x_title=x_title
        )
        logger.info(f"OpenRouterModel initialized with model: {model_id}")
    except Exception as e:
        await cl.Message(content=f"Error initializing OpenRouter Model: {e}").send()
        logger.error(f"Failed to initialize OpenRouterModel: {e}", exc_info=True)
        return

    # Get the database tools
    try:
        agent_db_tools = get_tools()
        tool_names = [t.spec['name'] for t in agent_db_tools] # Assumes tools are Strands @tool wrapped objects with a .spec
        logger.info(f"Loaded agent tools: {tool_names}")
    except Exception as e:
        await cl.Message(content=f"Error loading agent tools: {e}").send()
        logger.error(f"Failed to load agent tools: {e}", exc_info=True)
        return

    system_prompt = (
        "You are an AI assistant expert at managing data about children. "
        "You have tools to add new children, retrieve their details, update their payment information, "
        "change their active status, list children by parent, and list all active children. "
        "When a user asks a question or makes a request related to this data, identify and use the appropriate tool. "
        "Provide clear, concise answers based on the information from the tools or your general knowledge if appropriate. "
        "If a tool provides specific data, present that data clearly to the user. "
        "If an operation is successful, confirm it. If an error occurs with a tool, inform the user gracefully. "
        "Always ask for clarification if a request is ambiguous for tool use."
    )

    try:
        agent = Agent(
            model=openrouter_model,
            tools=agent_db_tools,
            system_prompt=system_prompt
        )
        cl.user_session.set("agent", agent)
        logger.info(f"Strands Agent '{agent.id}' initialized with tools and set in user session.")
        await cl.Message(content=f"Agent ready! Using model: {model_id}. I can help manage children's data. How can I assist you?").send()
    except Exception as e:
        await cl.Message(content=f"Error initializing Strands Agent: {e}").send()
        logger.error(f"Failed to initialize Strands Agent: {e}", exc_info=True)


@cl.on_message
async def on_message(message: cl.Message):
    agent = cl.user_session.get("agent")
    if not agent:
        await cl.ErrorMessage(content="Agent not initialized. Please restart the chat.").send()
        return

    logger.info(f"Received message from user: '{message.content}'")

    ui_response_msg = cl.Message(content="", author="Agent") # Author can be customized
    # It's better to send the empty message once content starts streaming or if a step is created.
    # await ui_response_msg.send() # Avoid sending if agent does nothing.

    final_response_text = ""
    current_step = None # To manage Chainlit steps for tool calls
    msg_sent = False # Track if ui_response_msg has been sent

    try:
        async for event_str in agent.stream_events_async(message.content):
            event = json.loads(event_str)
            # logger.debug(f"Agent event: {json.dumps(event, indent=2)}")

            if event.get("type") == "contentBlockDelta" and event.get("delta", {}).get("type") == "text_delta":
                if not msg_sent: # Send the empty message shell before streaming first token
                    await ui_response_msg.send()
                    msg_sent = True
                text_delta = event["delta"]["text"]
                final_response_text += text_delta
                await ui_response_msg.stream_token(text_delta)

            elif event.get("type") == "contentBlockStart":
                content_block = event.get("contentBlock", {})
                if content_block.get("type") == "tool_use":
                    if not msg_sent: # If agent goes straight to tool use, send the main message shell
                        await ui_response_msg.send()
                        msg_sent = True
                    tool_name = content_block["name"]
                    tool_input = content_block.get("input", {})
                    current_step = cl.Step(name=f"Tool: {tool_name}", type="tool", show_input=True)
                    current_step.input = json.dumps(tool_input, indent=2) if isinstance(tool_input, dict) else str(tool_input)
                    await current_step.send()
                    cl.user_session.set(f"tool_step_{content_block['toolUseId']}", current_step)

            elif event.get("type") == "contentBlockStop":
                content_block = event.get("contentBlock", {})
                if content_block.get("type") == "tool_use":
                    tool_use_id = content_block["toolUseId"]
                    tool_step = cl.user_session.get(f"tool_step_{tool_use_id}") # type: cl.Step | None
                    if tool_step:
                        tool_step.output = "Tool execution completed by agent."
                        await tool_step.update()
                        cl.user_session.set(f"tool_step_{tool_use_id}", None)
                    current_step = None # Clear current_step as this specific one is done

            elif event.get("type") == "messageStop":
                stop_reason = event.get("message", {}).get("stopReason", "unknown")
                logger.info(f"Agent turn finished. Reason: {stop_reason}")
                if current_step:
                    current_step.output = f"Agent processing finished with reason: {stop_reason}"
                    await current_step.update()
                    cl.user_session.set(f"tool_step_{current_step.id}", None) # Use step ID if available, or manage via toolUseId
                    current_step = None

                if not final_response_text and not msg_sent and stop_reason == "tool_use":
                    # Agent only used tool, no text response yet
                    ui_response_msg.content = "(Tool processing complete. The agent will now formulate a response based on the tool's output if any.)"
                    await ui_response_msg.send()
                    msg_sent = True
                elif not final_response_text and not msg_sent:
                     ui_response_msg.content = "(No textual response from agent for this turn.)"
                     await ui_response_msg.send()
                     msg_sent = True

    except Exception as e:
        logger.error(f"Error during agent interaction: {e}", exc_info=True)
        if current_step: # type: ignore
            current_step.is_error = True # type: ignore
            current_step.output = f"Error: {e}" # type: ignore
            await current_step.update() # type: ignore

        if not msg_sent:
            ui_response_msg.content = f"An error occurred: {e}"
            await ui_response_msg.send()
            msg_sent = True
        else: # Message already sent, stream error token
            await ui_response_msg.stream_token(f"\nAn error occurred: {e}")

    # Finalize the message content if it was only streamed
    if msg_sent and not ui_response_msg.content and final_response_text:
         ui_response_msg.content = final_response_text

    if msg_sent: # Only update if it was sent
        await ui_response_msg.update()
    elif final_response_text: # Not sent, but has content
        ui_response_msg.content = final_response_text
        await ui_response_msg.send()
    # If not msg_sent and no final_response_text, nothing is sent (e.g. initial error before msg send)

if __name__ == "__main__":
    print("This application is designed to be run with Chainlit.")
    print("Try: chainlit run app.py -w")
