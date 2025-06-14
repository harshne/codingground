import logging
import os
import sys
import json # Ensure json is imported for tool argument parsing and result formatting

from dotenv import load_dotenv

from strands import Agent
from strands.types.content import Message, Messages, TextContentBlock, ToolUseContentBlock, ToolResultContentBlock

# Add src directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from custom_model_provider.openrouter_provider import OpenRouterModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_agent() -> Agent | None:
    '''Initializes and returns the Strands Agent, or None if initialization fails.'''
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

    api_key = os.getenv("OPENROUTER_API_KEY")
    model_id = os.getenv("OPENROUTER_MODEL_ID", "mistralai/mistral-7b-instruct-free")
    temperature = float(os.getenv("OPENROUTER_TEMPERATURE", 0.7))
    max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", 1024)) # Increased default
    http_referer = os.getenv("HTTP_REFERER", "http://localhost/strands-cli")
    x_title = os.getenv("X_TITLE", "Strands OpenRouter CLI Agent")

    if not api_key:
        logger.error("CRITICAL: OPENROUTER_API_KEY not found. Please set it in your .env file.")
        return None

    logger.info(f"Initializing OpenRouterModel with model_id: {model_id}")
    try:
        openrouter_custom_model = OpenRouterModel(
            model_id=model_id,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            http_referer=http_referer,
            x_title=x_title
        )
    except ValueError as ve:
        logger.error(f"Configuration error for OpenRouterModel: {ve}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize OpenRouterModel: {e}", exc_info=True)
        return None

    system_prompt = "You are a helpful AI assistant. If you need to use a tool, clearly state the tool and its arguments. After the user provides the tool's result, use it to answer the original request."

    logger.info("Initializing Strands Agent...")
    try:
        agent = Agent(model=openrouter_custom_model, system_prompt=system_prompt)
        logger.info(f"Strands Agent '{agent.id}' initialized successfully.")
        return agent
    except Exception as e:
        logger.error(f"Failed to initialize Strands Agent: {e}", exc_info=True)
        return None

def run_cli():
    agent = initialize_agent()
    if not agent:
        print("Failed to initialize the agent. Exiting.")
        return

    print(f"Strands OpenRouter Agent CLI. Model: {agent.model.config.get('model_id')}") #type: ignore
    print("Type 'exit' or 'quit' to end the chat.")
    print("If the agent requests a tool, you will be prompted to provide a JSON result for it.")

    # Maintain conversation history using Strands Messages type
    conversation_history: Messages = []

    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Exiting chat.")
                break
            if not user_input.strip():
                continue

            current_user_message = Message(role="user", content=[TextContentBlock(text=user_input)])
            # Add user's message to local history *before* calling the agent for this turn
            turn_history = list(conversation_history) # Copy history for this turn
            turn_history.append(current_user_message)

            print("Agent: ", end="", flush=True)

            assistant_response_text_parts = [] # For simple text accumulation this turn
            requested_tool_calls_for_turn: List[ToolUseContentBlock] = []

            # Temporary tracking for a single tool call's streaming parts
            streaming_tool_call_id: Optional[str] = None
            streaming_tool_name: Optional[str] = None
            streaming_tool_args_str: str = ""

            for event in agent(messages=turn_history): # Pass history for context
                # logger.debug(f"CLI Agent Event: {event}")

                if event.get('messageStart'):
                    pass

                elif event.get('contentBlockStart'):
                    start_block = event['contentBlockStart']['start']
                    # Check if it's a tool_use block starting
                    if start_block.get('type') == 'tool_use' and start_block.get('toolUseId') and start_block.get('name'):
                        streaming_tool_call_id = start_block['toolUseId']
                        streaming_tool_name = start_block['name']
                        streaming_tool_args_str = "" # Reset for new tool
                        print(f"[Tool Call Start: ID={streaming_tool_call_id}, Name={streaming_tool_name}, Args: ", end="", flush=True)
                    elif start_block.get('type') == 'text':
                        pass # Text block started, delta will follow

                elif event.get('contentBlockDelta'):
                    delta = event['contentBlockDelta']['delta']
                    if delta.get('text'):
                        text_delta = delta['text']
                        print(text_delta, end="", flush=True)
                        assistant_response_text_parts.append(text_delta)

                    elif delta.get('toolUse') and streaming_tool_name: # Streaming tool arguments
                        args_delta = delta['toolUse']['input']
                        print(args_delta, end="", flush=True)
                        streaming_tool_args_str += args_delta

                elif event.get('contentBlockStop'):
                    # If we were streaming a tool call and its block stops, finalize it
                    if streaming_tool_call_id and event['contentBlockStop'].get('index') is not None: # Assuming index is present
                        # Check if this stop event corresponds to the tool call we are tracking.
                        # This needs robust mapping of index to tool call if multiple tools are possible.
                        # For now, assume one tool call is focused at a time in this CLI handling.
                        print("]", flush=True) # Close the bracket for args
                        requested_tool_calls_for_turn.append(
                            ToolUseContentBlock(
                                toolUseId=streaming_tool_call_id,
                                name=streaming_tool_name, # type: ignore
                                input=streaming_tool_args_str
                            )
                        )
                        # Reset current tool tracking for this event loop
                        streaming_tool_call_id = None
                        streaming_tool_name = None
                        streaming_tool_args_str = ""

                elif event.get('messageStop'):
                    print(f" (Turn ended. Reason: {event['messageStop']['stopReason']})", flush=True)

                    # Construct assistant's message for history based on what was collected
                    assistant_content_for_history: List[ContentBlock] = []
                    final_text = "".join(assistant_response_text_parts)
                    if final_text:
                        assistant_content_for_history.append(TextContentBlock(text=final_text))
                    if requested_tool_calls_for_turn:
                        assistant_content_for_history.extend(requested_tool_calls_for_turn) # type: ignore

                    # Add user message and assistant's full response to main conversation history
                    conversation_history.append(current_user_message)
                    if assistant_content_for_history:
                        conversation_history.append(Message(role="assistant", content=assistant_content_for_history))
                    else: # If assistant said nothing (e.g. error or filter)
                         conversation_history.append(Message(role="assistant", content=[]))


                    if event['messageStop']['stopReason'] == 'tool_use':
                        if not requested_tool_calls_for_turn:
                            logger.warning("MessageStop reason was 'tool_use', but no tool calls were fully parsed/requested by the CLI.")
                        else:
                            # The agent wants to use tools. Prompt user for results.
                            tool_results_content_blocks: List[ToolResultContentBlock] = []
                            for tool_call_request in requested_tool_calls_for_turn:
                                print(f"\n[Agent wants to call tool '{tool_call_request['name']}' with ID '{tool_call_request['toolUseId']}']")
                                print(f"  Arguments: {tool_call_request['input']}")

                                while True: # Loop for user to input valid JSON for tool result
                                    try:
                                        tool_result_json_str = input(f"  Enter JSON result for tool '{tool_call_request['name']} (ID: {tool_call_request['toolUseId']})': ")
                                        parsed_json_content = json.loads(tool_result_json_str)
                                        tool_results_content_blocks.append(
                                            ToolResultContentBlock(toolCallId=tool_call_request['toolUseId'], content=parsed_json_content, status="success") # type: ignore
                                        )
                                        break
                                    except json.JSONDecodeError:
                                        print("Invalid JSON string. Please try again or ensure quotes are correct.")
                                    except Exception as e:
                                        print(f"Error processing tool result: {e}. Skipping this tool.")
                                        break

                            if tool_results_content_blocks:
                                # Add tool results message to conversation history
                                tool_results_message = Message(role="tool", content=tool_results_content_blocks) # type: ignore
                                conversation_history.append(tool_results_message)

                                # --- Make the subsequent call to the agent with tool results ---
                                print("\nAgent (processing tool results): ", end="", flush=True)

                                # Clear parts for the new response
                                assistant_response_text_parts = []
                                final_assistant_response_after_tool: List[ContentBlock] = []

                                for event_after_tool in agent(messages=conversation_history): # Pass full history
                                    # logger.debug(f"CLI Agent Event (after tool): {event_after_tool}")
                                    if event_after_tool.get('contentBlockDelta') and event_after_tool['contentBlockDelta']['delta'].get('text'):
                                        text_delta = event_after_tool['contentBlockDelta']['delta']['text']
                                        print(text_delta, end="", flush=True)
                                        assistant_response_text_parts.append(text_delta)
                                    elif event_after_tool.get('messageStop'):
                                        print(f" (Turn ended. Reason: {event_after_tool['messageStop']['stopReason']})", flush=True)
                                        break

                                final_text_after_tool = "".join(assistant_response_text_parts)
                                if final_text_after_tool:
                                    final_assistant_response_after_tool.append(TextContentBlock(text=final_text_after_tool))

                                if final_assistant_response_after_tool: # Add final assistant response to history
                                    conversation_history.append(Message(role="assistant", content=final_assistant_response_after_tool))
                                else: # Assistant said nothing after tool results
                                    conversation_history.append(Message(role="assistant", content=[]))

                    # End of this user-agent turn processing
                    break # Break from event loop for this user input, proceed to next user input

            # Simple context window management for CLI
            if len(conversation_history) > 20:
                logger.info("Trimming conversation history (keeping last 10 messages).")
                conversation_history = conversation_history[-10:]

        except KeyboardInterrupt:
            print("\nExiting chat (KeyboardInterrupt).")
            break
        except Exception as e:
            logger.error(f"An error occurred in the CLI loop: {e}", exc_info=True)
            # break # Uncomment to exit on any error

if __name__ == "__main__":
    run_cli()
    logger.info("CLI finished.")
