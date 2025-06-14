import logging
import os
import json # Make sure json is imported
from typing import Any, Iterable, Optional, TypedDict, List, Dict, Union

from openai import OpenAI, APIError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from strands.types.models import Model
from strands.types.content import Messages, Message, ContentBlock, TextContentBlock, ToolUseContentBlock, ToolResultContentBlock, Role
from strands.types.streaming import StreamEvent, MessageStartEvent, ContentBlockStartEvent, ContentBlockDeltaEvent, ContentBlockStopEvent, MessageStopEvent, MetadataEvent
from strands.types.tools import ToolSpec
from strands.types.exceptions import ContextWindowOverflowException, ModelProviderException, AuthenticationException, RateLimitException

logger = logging.getLogger(__name__)

class OpenRouterModel(Model):
    '''
    A custom Strands Model provider for OpenRouter.
    Leverages the OpenAI SDK due to OpenRouter's API compatibility.
    '''

    class ModelConfig(TypedDict, total=False):
        model_id: str
        api_key: str
        temperature: Optional[float]
        max_tokens: Optional[int]
        top_p: Optional[float]
        presence_penalty: Optional[float]
        frequency_penalty: Optional[float]
        http_referer: Optional[str]
        x_title: Optional[str]

    def __init__(self, **model_config: ModelConfig) -> None:
        if not model_config.get('model_id') or not model_config.get('api_key'):
            raise ValueError("Missing required 'model_id' or 'api_key' in OpenRouterModel configuration.")

        self.config = model_config
        logger.debug(f"OpenRouterModel config: {self.config}")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.config['api_key'],
            default_headers={
                "HTTP-Referer": self.config.get('http_referer', ''),
                "X-Title": self.config.get('x_title', '')
            } if self.config.get('http_referer') or self.config.get('x_title') else None
        )
        self._model_id = self.config['model_id']
        # For tracking open tool calls to emit ContentBlockStop correctly if needed by Strands
        self._open_tool_call_ids: List[str] = []

    def _convert_strands_messages_to_openai(self, messages: Messages) -> List[ChatCompletionMessageParam]:
        openai_messages: List[ChatCompletionMessageParam] = []
        for strands_message in messages:
            role = strands_message['role']

            if role == 'tool':
                tool_call_id_str = None
                tool_content_str = ""
                for block in strands_message['content']:
                    if block['type'] == 'tool_result':
                        tool_call_id_str = block['toolCallId']
                        if isinstance(block['content'], (dict, list)):
                            tool_content_str = json.dumps(block['content'])
                        elif isinstance(block['content'], str):
                            # Attempt to parse the string content as JSON if it's a tool result
                            # OpenAI expects the content of a tool result to be a JSON string.
                            # If Strands already provides a JSON string, no further dump is needed.
                            # If it's a plain string not meant to be JSON, this could be an issue.
                            # Strands ToolResultContentBlock.content is List[ContentBlock],
                            # so this path (content being a simple string) might be less common
                            # or indicate a misunderstanding of Strands spec.
                            # For now, assume if it's a string, it's pre-formatted JSON.
                            tool_content_str = block['content']
                        else:
                            tool_content_str = str(block['content']) # Fallback
                        break
                if tool_call_id_str:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id_str,
                        "content": tool_content_str
                    })
                else:
                    logger.warning(f"Strands message with role 'tool' is missing toolCallId or proper content structure: {strands_message}")

            elif role == 'assistant':
                assistant_content_parts = []
                assistant_tool_calls = []
                has_text_content = False
                for block in strands_message['content']:
                    if block['type'] == 'text':
                        assistant_content_parts.append(block['text'])
                        has_text_content = True
                    elif block['type'] == 'tool_use':
                        assistant_tool_calls.append({
                            "id": block['toolUseId'],
                            "type": "function",
                            "function": {
                                "name": block['name'],
                                "arguments": block['input']
                            }
                        })

                # OpenAI API requires 'content' to be null if 'tool_calls' is present and there's no text content.
                # If there is text content alongside tool_calls, it should be included.
                current_content = "\n".join(assistant_content_parts) if assistant_content_parts else None
                if assistant_tool_calls:
                    openai_messages.append({"role": "assistant", "tool_calls": assistant_tool_calls, "content": current_content})
                else: # No tool calls, just text content
                    openai_messages.append({"role": "assistant", "content": current_content if current_content is not None else ""})


            else: # User or System roles
                string_content_parts = []
                for block in strands_message['content']:
                    if block['type'] == 'text':
                        string_content_parts.append(block['text'])

                final_content = "\n".join(string_content_parts)
                if role == 'user':
                    openai_messages.append({"role": "user", "content": final_content})
                elif role == 'system':
                    openai_messages.append({"role": "system", "content": final_content})

        return openai_messages

    def _convert_strands_tools_to_openai(self, tool_specs: Optional[List[ToolSpec]]) -> Optional[List[ChatCompletionToolParam]]:
        if not tool_specs:
            return None
        openai_tools: List[ChatCompletionToolParam] = []
        for spec in tool_specs:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": spec['name'],
                    "description": spec['description'],
                    "parameters": spec['inputSchema']
                }
            })
        return openai_tools

    def format_request(
        self,
        messages: Messages,
        tool_specs: Optional[List[ToolSpec]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        openai_messages = self._convert_strands_messages_to_openai(messages)
        openai_tools = self._convert_strands_tools_to_openai(tool_specs)

        if system_prompt:
            # Check if the first message is already a system message with the same content
            first_message_is_system_prompt = False
            if openai_messages and openai_messages[0]['role'] == 'system':
                if openai_messages[0]['content'] == system_prompt:
                    first_message_is_system_prompt = True
                else: # First message is system, but content is different.
                    logger.warning("System prompt provided but the first message is already a system message with different content. Prepending new system prompt.")
                    openai_messages.insert(0, {"role": "system", "content": system_prompt})

            if not openai_messages or not first_message_is_system_prompt and (not openai_messages or openai_messages[0]['role'] != 'system'):
                 openai_messages.insert(0, {"role": "system", "content": system_prompt})


        request_params: Dict[str, Any] = {
            "model": self._model_id,
            "messages": openai_messages,
            "stream": True
        }

        if openai_tools:
            request_params["tools"] = openai_tools
            request_params["tool_choice"] = "auto"

        for key in ['temperature', 'max_tokens', 'top_p', 'presence_penalty', 'frequency_penalty']:
            if key in self.config and self.config[key] is not None:
                request_params[key] = self.config[key]

        logger.debug(f"OpenRouter formatted request: {json.dumps(request_params, indent=2)}")
        return request_params

    def stream(self, request: Dict[str, Any]) -> Iterable[ChatCompletionChunk]:
        try:
            stream_response = self.client.chat.completions.create(**request)
            for chunk in stream_response:
                yield chunk
        except APIError as e:
            # More robust check for context length exceeded, OpenAI error codes can be strings.
            is_context_overflow = "context_length_exceeded" in str(e).lower()
            if hasattr(e, 'code') and isinstance(e.code, str):
                is_context_overflow = is_context_overflow or "context_length_exceeded" == e.code.lower()

            if is_context_overflow:
                 raise ContextWindowOverflowException(f"OpenRouter context window overflow: {e}") from e
            elif e.status_code == 401: # Unauthorized
                raise AuthenticationException(f"OpenRouter authentication error (401): {e}") from e
            elif e.status_code == 429: # Rate limit
                raise RateLimitException(f"OpenRouter rate limit exceeded (429): {e}") from e
            else:
                raise ModelProviderException(f"OpenRouter API error (status {e.status_code}): {e}") from e
        except Exception as e: # Catch-all for other errors like network issues
            raise ModelProviderException(f"Unexpected error during OpenRouter stream: {e}") from e

    def format_chunk(self, chunk: ChatCompletionChunk) -> Iterable[StreamEvent]:
        # This method now yields events, so it's an Iterable[StreamEvent]

        # Handle usage data if present (often in the last chunk with finish_reason)
        if chunk.usage:
            yield MetadataEvent(metadata={"usage": chunk.usage.model_dump()}) # model_dump() is for Pydantic v2+
            # If only usage is in this chunk, no further processing needed for choice/delta.
            if not chunk.choices: return


        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            # If there are no choices, but also no usage, it might be an empty SSE comment or similar.
            # Log it if unexpected, but don't yield an event unless Strands has a specific one for this.
            logger.debug(f"Received chunk with no choices and no usage: {chunk.model_dump_json()}")
            return

        delta = choice.delta

        # Message Start (role indication)
        if delta and delta.role:
            # Role is 'assistant' typically.
            # Strands Role type might need mapping if delta.role differs from Strands' expected values.
            yield MessageStartEvent(messageStart={"role": delta.role})

        # Content Delta (text)
        if delta and delta.content:
            yield ContentBlockStartEvent(contentBlockStart={"start": {"type": "text"}}) # Implicit start for text
            yield ContentBlockDeltaEvent(contentBlockDelta={"delta": {"text": delta.content}})
            # We don't know if this is the end of the text block from a single delta,
            # so ContentBlockStop for text is usually inferred at MessageStop or start of new block type.

        # Tool Call Processing
        if delta and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                # tc_delta.index is important for multi-tool scenarios.
                # Strands might expect events per tool, indexed if necessary.

                # Tool Call Start
                if tc_delta.id and tc_delta.function and tc_delta.function.name:
                    # This indicates the start of a new tool call's definition by the LLM.
                    if tc_delta.id not in self._open_tool_call_ids:
                       self._open_tool_call_ids.append(tc_delta.id) # Track this tool call
                       yield ContentBlockStartEvent(
                           contentBlockStart={
                               "index": tc_delta.index, # Include index
                               "start": {
                                   "type": "tool_use", # Strands specific type
                                   "toolUseId": tc_delta.id,
                                   "name": tc_delta.function.name
                               }
                           }
                       )

                # Tool Call Arguments Delta
                if tc_delta.id and tc_delta.function and tc_delta.function.arguments:
                    # This is a chunk of arguments for the current tool call.
                    if tc_delta.id in self._open_tool_call_ids: # Ensure it's for a known open tool
                        yield ContentBlockDeltaEvent(
                            contentBlockDelta={
                                "index": tc_delta.index, # Include index
                                "delta": {
                                    "type": "tool_use", # Strands specific type
                                    "toolUse": { # Matches Strands' ToolUseDelta structure
                                        "input": tc_delta.function.arguments
                                    }
                                }
                            }
                        )

        # Finish Reason Processing (end of message or tool sequence)
        if choice and choice.finish_reason:
            finish_reason_str = choice.finish_reason

            # If the finish reason is 'tool_calls', it means the LLM has finished specifying all tool calls.
            # We should emit ContentBlockStop for each tool call that was started.
            if finish_reason_str == "tool_calls":
                for i, tool_id in enumerate(self._open_tool_call_ids):
                    # Strands ContentBlockStopEvent does not have a specific field for toolUseId in its definition.
                    # It just signals the end of the content block at a given index.
                    # The 'index' here should correspond to the index of the ContentBlock in the Message's 'content' list.
                    # This requires careful management of indices if Strands processes them this way.
                    # Assuming for now that the order of stopping matches the order of starting for simplicity.
                    # The OpenAI `tc_delta.index` would be the source of truth for the index.
                    # This part might need refinement based on how Strands Agent processes these stops.
                    # We need to know which ContentBlock (by index in the message) is stopping.
                    # Let's assume the indices of open tool calls map directly for now.
                    yield ContentBlockStopEvent(contentBlockStop={"index": i}) # This index mapping is a guess
                self._open_tool_call_ids.clear() # Clear tracked tool calls
            elif self._open_tool_call_ids: # If finished for other reason but tools were open (e.g. max_tokens)
                 for i, tool_id in enumerate(self._open_tool_call_ids):
                    yield ContentBlockStopEvent(contentBlockStop={"index": i})
                 self._open_tool_call_ids.clear()


            # If the finish reason implies the end of a text block that was implicitly started
            if finish_reason_str in ["stop", "length", "content_filter"] and delta and delta.content is None and not delta.tool_calls:
                 # This implies a text block might have just finished.
                 # The index for text block stop needs to be determined. Usually 0 if it's the first/only block.
                 # This is also an area that needs robust index management.
                 # For now, assuming index 0 for a simple text response.
                 yield ContentBlockStopEvent(contentBlockStop={"index": 0})


            # Map OpenAI finish reasons to Strands stop reasons
            strands_stop_reason_map = {
                "stop": "end_turn",          # Natural stop
                "length": "max_tokens",      # Max tokens reached
                "tool_calls": "tool_use",    # Model wants to use tools
                "content_filter": "content_filtered", # Content filtered by provider
                "function_call": "tool_use"  # Legacy, map to tool_use
            }
            strands_stop_reason = strands_stop_reason_map.get(finish_reason_str, "unknown")
            yield MessageStopEvent(messageStop={"stopReason": strands_stop_reason})


    def get_config(self) -> ModelConfig:
        return self.config

    def update_config(self, **model_config_update: ModelConfig) -> None:
        old_api_key = self.config.get('api_key')
        old_http_referer = self.config.get('http_referer')
        old_x_title = self.config.get('x_title')
        old_model_id = self.config.get('model_id') # Check model_id change

        self.config.update(model_config_update)

        new_api_key = self.config.get('api_key')
        new_http_referer = self.config.get('http_referer')
        new_x_title = self.config.get('x_title')
        new_model_id = self.config.get('model_id')

        # Re-initialize client if API key, base URL related headers, or model_id changes
        # Note: model_id itself doesn't require re-init of the client object, but it's a core part of requests.
        if (new_api_key != old_api_key or
            new_http_referer != old_http_referer or # Headers change
            new_x_title != old_x_title): # Headers change
            logger.info("Re-initializing OpenAI client due to config update (API key or headers).")
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=new_api_key,
                default_headers={
                    "HTTP-Referer": new_http_referer or '', # ensure not None
                    "X-Title": new_x_title or '' # ensure not None
                } if new_http_referer or new_x_title else None
            )

        if new_model_id != old_model_id:
            self._model_id = new_model_id # Update internal model_id
            logger.info(f"OpenRouterModel model_id updated to: {self._model_id}")

        logger.debug(f"OpenRouterModel config updated: {self.config}")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    # Configure logging more comprehensively for testing
    logging.basicConfig(
        level=logging.INFO, # Set to DEBUG for verbose output from the provider
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Silence OpenAI's own logger unless it's an error, to reduce noise during tests
    logging.getLogger("openai").setLevel(logging.WARNING)


    api_key_env = os.getenv("OPENROUTER_API_KEY")
    # Free model for basic text, good for testing availability
    model_id_env = os.getenv("OPENROUTER_MODEL_ID", "mistralai/mistral-7b-instruct-free")
    # Model known to be good with tool use for the tool test
    tool_model_id_env = os.getenv("OPENROUTER_TOOL_MODEL_ID", "openai/gpt-3.5-turbo")


    if not api_key_env:
        logger.error("Error: OPENROUTER_API_KEY not found in environment variables.")
    else:
        logger.info(f"--- Testing OpenRouterModel with default text model: {model_id_env} ---")
        try:
            # --- Test 1: Simple Text Generation ---
            logger.info("\n--- Test 1: Simple Text Generation ---")
            text_model = OpenRouterModel(
                model_id=model_id_env, api_key=api_key_env, temperature=0.7, max_tokens=60
            )
            text_messages: Messages = [Message(role='user', content=[TextContentBlock(text='Tell me a short, SFW (safe-for-work) joke.')])]
            text_request = text_model.format_request(messages=text_messages)

            logger.info(f"Formatted Text Request: {json.dumps(text_request, indent=2)}")

            full_response_text = ""
            print("Streaming response for joke: ", end='', flush=True)
            for event_chunk in text_model.stream(text_request):
                # logger.debug(f"Raw Chunk from OpenAI: {event_chunk.model_dump_json()}")
                for event in text_model.format_chunk(event_chunk):
                    # logger.debug(f"Strands Event: {event}")
                    if event.get('contentBlockDelta') and event['contentBlockDelta']['delta'].get('text'):
                        text = event['contentBlockDelta']['delta']['text']
                        print(text, end='', flush=True)
                        full_response_text += text
                    if event.get('messageStop'):
                        print(f"\nStream finished. Reason: {event['messageStop']['stopReason']}")
            logger.info(f"\nFull response collected for joke: {full_response_text}")

            # --- Test 2: Tool Call Simulation ---
            logger.info("\n\n--- Test 2: Tool Call Simulation ---")
            logger.info(f"Using tool test model: {tool_model_id_env} (set OPENROUTER_TOOL_MODEL_ID to change)")

            tool_model = OpenRouterModel(
                model_id=tool_model_id_env, api_key=api_key_env, temperature=0.1
            )
            tool_specs: List[ToolSpec] = [
                ToolSpec(
                    name="get_current_weather",
                    description="Get the current weather in a given location",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"},
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                        },
                        "required": ["location"]
                    }
                )
            ]
            tool_messages: Messages = [
                Message(role='user', content=[TextContentBlock(text='What is the weather like in Boston, MA?')])
            ]
            # Add system prompt for better tool use behavior if needed by model
            # system_prompt_tool = "You are a helpful assistant that uses tools to answer questions."
            # tool_request = tool_model.format_request(messages=tool_messages, tool_specs=tool_specs, system_prompt=system_prompt_tool)
            tool_request = tool_model.format_request(messages=tool_messages, tool_specs=tool_specs)

            logger.info(f"Simulating agent interaction for tool call. Initial request to LLM: {json.dumps(tool_request, indent=2)}")

            # Store the state of the conversation for multi-turn
            current_conversation_messages: Messages = list(tool_messages)

            # Store tool calls requested by the LLM in this turn
            tool_calls_requested_this_turn: List[Dict[str, Any]] = []

            print("Streaming response for tool call: ", end='', flush=True)
            for event_chunk in tool_model.stream(tool_request):
                # logger.debug(f"Raw Chunk (Tool): {event_chunk.model_dump_json()}")
                for event in tool_model.format_chunk(event_chunk):
                    # logger.debug(f"Strands Event (Tool): {event}")
                    if event.get('messageStart'):
                        # This is where you'd initialize the assistant's message structure if building it up incrementally
                        logger.info(f"Assistant message started by LLM: {event['messageStart']}")

                    if event.get('contentBlockStart'):
                        start_block = event['contentBlockStart']['start']
                        block_index = event['contentBlockStart']['index']
                        if start_block.get('type') == 'tool_use':
                            tool_use_id = start_block['toolUseId']
                            tool_name = start_block['name']
                            logger.info(f"LLM started tool use block (Index: {block_index}): ID={tool_use_id}, Name={tool_name}")
                            # Prepare to collect arguments for this tool call
                            tool_calls_requested_this_turn.append({
                                "id": tool_use_id, "name": tool_name, "arguments_str": "", "index": block_index
                            })
                        elif start_block.get('type') == 'text':
                             logger.info(f"LLM started text block (Index: {block_index})")
                             print("\nAssistant text: ", end='')


                    if event.get('contentBlockDelta'):
                        delta_block = event['contentBlockDelta']['delta']
                        block_index = event['contentBlockDelta']['index']
                        if delta_block.get('text'):
                            text = delta_block['text']
                            print(text, end='', flush=True)
                        elif delta_block.get('toolUse'):
                            args_delta = delta_block['toolUse']['input']
                            # Find the corresponding tool call by index to append arguments
                            for tc in tool_calls_requested_this_turn:
                                if tc["index"] == block_index: # tc_delta.index should map to this
                                    tc["arguments_str"] += args_delta
                                    print(f"[Tool Arg Chunk for ID {tc['id']}: {args_delta}]", end='', flush=True)
                                    break

                    if event.get('contentBlockStop'):
                        block_index = event['contentBlockStop']['index']
                        logger.info(f"LLM stopped content block (Index: {block_index}).")

                    if event.get('messageStop'):
                        logger.info(f"\nLLM turn finished. Reason: {event['messageStop']['stopReason']}")

                        # Construct the assistant's message from this turn
                        assistant_message_content: List[ContentBlock] = []
                        # First, add any text parts (if your model mixes text and tool calls)
                        # (This example assumes tool calls are primary if reason is tool_use)

                        # Add collected tool calls to assistant's message
                        for tc_req in tool_calls_requested_this_turn:
                            logger.info(f"  Finalized Tool Call Request: ID={tc_req['id']}, Name={tc_req['name']}, Args='{tc_req['arguments_str']}'")
                            try:
                                # Validate that arguments string is valid JSON
                                json.loads(tc_req['arguments_str'])
                                assistant_message_content.append(
                                    ToolUseContentBlock(toolUseId=tc_req['id'], name=tc_req['name'], input=tc_req['arguments_str'])
                                )
                            except json.JSONDecodeError as json_err:
                                logger.error(f"Error decoding JSON arguments for tool {tc_req['name']}: {json_err}. Args: '{tc_req['arguments_str']}'")
                                # Potentially handle this by sending an error back to the LLM or skipping this tool call

                        if assistant_message_content: # Only add assistant message if it has content
                            current_conversation_messages.append(
                                Message(role='assistant', content=assistant_message_content)
                            )

                        if event['messageStop']['stopReason'] == 'tool_use':
                            logger.info("LLM requested tool use. Simulating tool execution by the agent...")

                            # Simulate executing tools and adding results for the next turn
                            for tc_req in tool_calls_requested_this_turn:
                                # Simulate a result for each tool call
                                simulated_tool_result = {"temperature": "22C", "condition": "Sunny with a chance of LLMs"}
                                if tc_req['name'] == "get_current_weather":
                                    try:
                                        args = json.loads(tc_req['arguments_str'])
                                        simulated_tool_result["location_queried"] = args.get("location")
                                    except json.JSONDecodeError:
                                        pass # Already logged

                                logger.info(f"  Simulating execution of {tc_req['name']} with ID {tc_req['id']}. Result: {simulated_tool_result}")
                                current_conversation_messages.append(
                                    Message(role='tool', content=[
                                        ToolResultContentBlock(
                                            toolCallId=tc_req['id'],
                                            content=json.dumps(simulated_tool_result) # Content for ToolResult should be string for OpenAI
                                        )
                                    ])
                                )

                            logger.info(f"\n--- Preparing for next LLM call with tool results ---")
                            # Convert current_conversation_messages to OpenAI format for inspection
                            next_openai_messages = tool_model._convert_strands_messages_to_openai(current_conversation_messages)
                            logger.info(f"OpenAI messages for next turn: {json.dumps(next_openai_messages, indent=2)}")

                            # Optional: Make the actual next call to see the LLM's response to tool results
                            # next_request = tool_model.format_request(messages=current_conversation_messages, tool_specs=tool_specs)
                            # ... (stream and format chunk for the response) ...
                        break

            logger.info("\n\n--- End of All Tests ---")

        except ValueError as ve: # For config errors
            logger.error(f"Configuration Error: {ve}", exc_info=True)
        except ModelProviderException as e: # For API or model related errors
            logger.error(f"Model Provider Error: {e}", exc_info=True)
        except Exception as e: # For any other unexpected errors during tests
            logger.error(f"An unexpected error occurred during testing: {e}", exc_info=True)
