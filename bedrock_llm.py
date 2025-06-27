import json
import boto3
from typing import Any, List, Dict

# Assume a base class structure or required methods for browser-use.
# If browser-use has a specific BaseLLM, this class should inherit from it.
# For now, we'll create a standalone class that implements a plausible interface.

class ChatBedrock:
    """
    A custom LLM wrapper for AWS Bedrock models, compatible with browser-use Agent.
    This example focuses on Anthropic Claude models available via Bedrock.
    """
    def __init__(self, model_id: str = "anthropic.claude-v2:1", region_name: str = None, **kwargs):
        """
        Initializes the Bedrock LLM wrapper.

        Args:
            model_id (str): The Bedrock model ID (e.g., "anthropic.claude-v2:1", "amazon.titan-text-express-v1").
            region_name (str, optional): AWS region for Bedrock. If None, uses default from AWS config.
            **kwargs: Additional keyword arguments (currently unused but good for future extensibility).
        """
        self.model_id = model_id
        self.region_name = region_name
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region_name
        )
        self._provider = self._get_provider_from_model_id(model_id)

    def _get_provider_from_model_id(self, model_id: str) -> str:
        """Infers the provider from the model ID."""
        if model_id.startswith("anthropic."):
            return "anthropic"
        elif model_id.startswith("amazon."):
            return "amazon"
        elif model_id.startswith("ai21."):
            return "ai21"
        elif model_id.startswith("cohere."):
            return "cohere"
        # Add other providers as needed
        else:
            # Defaulting to anthropic for unknown, but this might need adjustment
            print(f"Warning: Unknown provider for model_id '{model_id}'. Defaulting to 'anthropic' request format. This may fail.")
            return "anthropic"


    async def __call__(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """
        Makes a call to the Bedrock model.
        Assumes 'messages' is a list of dictionaries, e.g., [{"role": "user", "content": "Hello"}],
        similar to OpenAI's chat completion API.

        Args:
            messages (List[Dict[str, str]]): A list of message objects.
            **kwargs: Additional keyword arguments for the Bedrock API call (e.g., temperature).

        Returns:
            str: The text response from the Bedrock model.

        Raises:
            ValueError: If the messages format is not as expected or provider is not supported.
            Exception: For Bedrock API errors.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty.")

        # Convert messages to the format expected by the chosen Bedrock model provider
        # This is a simplified conversion. Real-world usage might need more sophisticated mapping,
        # especially for multi-turn conversations and different roles.

        # For Anthropic Claude, the prompt should be a single string.
        # We'll concatenate user messages. System messages might need special handling.
        prompt_parts = []
        system_prompt = None # For models that support a separate system prompt

        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content # Capture system prompt
            elif role == "user":
                prompt_parts.append(f"\n\nHuman: {content}")
            elif role == "assistant": # or "ai"
                prompt_parts.append(f"\n\nAssistant: {content}")

        if not prompt_parts:
             raise ValueError("No user prompts found in messages.")

        # Construct the final prompt. For Claude, it needs to end with "Assistant:"
        # For some models, the last message should be from "user" or "Human"
        final_prompt = "".join(prompt_parts) + "\n\nAssistant:"

        request_body = {}
        # Default parameters - can be overridden by kwargs
        max_tokens = kwargs.get("max_tokens_to_sample", 2000) # Claude specific
        temperature = kwargs.get("temperature", 0.7)
        top_p = kwargs.get("top_p", 0.9)

        if self._provider == "anthropic":
            body_params = {
                "prompt": final_prompt,
                "max_tokens_to_sample": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
            }
            if system_prompt: # Anthropic specific system prompt
                body_params["system"] = system_prompt
            request_body = json.dumps(body_params)
            accept = 'application/json'
            contentType = 'application/json'

        elif self._provider == "amazon": # Example for Amazon Titan
            # Titan expects: {"inputText": "...", "textGenerationConfig": {...}}
            request_body = json.dumps({
                "inputText": final_prompt.replace("\n\nHuman:", "\nUser:").replace("\n\nAssistant:", "\nBot:"), # Adjust roles if needed
                "textGenerationConfig": {
                    "maxTokenCount": kwargs.get("maxTokenCount", max_tokens),
                    "temperature": temperature,
                    "topP": top_p,
                    # "stopSequences": [] # Optional
                }
            })
            accept = 'application/json'
            contentType = 'application/json'

        # Add other providers (Cohere, AI21, etc.) here with their specific request formats
        # For example, Cohere:
        # elif self._provider == "cohere":
        #     request_body = json.dumps({
        #         "prompt": final_prompt,
        #         "max_tokens": max_tokens,
        #         "temperature": temperature,
        #         # ... other Cohere params
        #     })

        else:
            raise ValueError(f"Unsupported provider '{self._provider}' for model '{self.model_id}'. Request body format not defined.")

        try:
            response = self.bedrock_runtime.invoke_model(
                body=request_body,
                modelId=self.model_id,
                accept=accept,
                contentType=contentType
            )
            response_body_str = response.get('body').read().decode('utf-8')
            response_body = json.loads(response_body_str)

            # Parse response based on provider
            if self._provider == "anthropic":
                # Claude returns: {"completion": "...", "stop_reason": "..."}
                return response_body.get("completion", "")
            elif self._provider == "amazon":
                # Titan returns: {"inputTextTokenCount": ..., "results": [{"tokenCount": ..., "outputText": "...", "completionReason": ...}]}
                if response_body.get("results") and len(response_body["results"]) > 0:
                    return response_body["results"][0].get("outputText", "")
                return "" # Or raise error
            # Add other provider response parsing here
            # elif self._provider == "cohere":
            #     # Cohere returns: {"generations": [{"text": "...", ...}], ...}
            #     if response_body.get("generations") and len(response_body["generations"]) > 0:
            #         return response_body["generations"][0].get("text", "")
            #     return ""

            else:
                raise ValueError(f"Unsupported provider '{self._provider}'. Response parsing not defined.")


        except Exception as e:
            print(f"Error invoking Bedrock model {self.model_id}: {e}")
            # Depending on browser-use's error handling, you might want to raise e or return an error message.
            raise

    # This is a synchronous version that might be needed if browser-use doesn't call an async method directly.
    # However, the example `agent.run()` is async, so `__call__` being async is probably correct.
    # def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
    #     import asyncio
    #     return asyncio.run(self.__call__(messages, **kwargs))

# Example usage (for testing this class directly, not via browser-use)
if __name__ == '__main__':
    import asyncio
    # Ensure your AWS credentials and region are configured (e.g., via AWS CLI, env vars)
    # For example, set AWS_PROFILE or AWS_DEFAULT_REGION environment variables.

    # Example for Anthropic Claude Sonnet 3.5
    # bedrock_llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", region_name="us-east-1")

    # Example for Anthropic Claude v2.1
    bedrock_llm = ChatBedrock(model_id="anthropic.claude-v2:1", region_name="us-east-1") # or your preferred region

    # Example for Amazon Titan Text Lite
    # bedrock_llm = ChatBedrock(model_id="amazon.titan-text-lite-v1", region_name="us-east-1")


    async def test_bedrock_llm():
        test_messages_claude = [
            {"role": "user", "content": "Hello, what is your name and capabilities?"}
        ]
        # For Claude with system prompt:
        # test_messages_claude_system = [
        #     {"role": "system", "content": "You are a helpful AI assistant."},
        #     {"role": "user", "content": "Hello, what is your name?"}
        # ]

        try:
            print(f"Testing with model: {bedrock_llm.model_id}")
            response = await bedrock_llm(test_messages_claude, max_tokens_to_sample=150)
            # If using claude with system prompt:
            # response = await bedrock_llm(test_messages_claude_system, max_tokens_to_sample=150)
            print("\nBedrock LLM Response:")
            print(response)
        except Exception as e:
            print(f"Error during test: {e}")

    asyncio.run(test_bedrock_llm())

    # Example for Amazon Titan
    # bedrock_llm_titan = ChatBedrock(model_id="amazon.titan-text-express-v1", region_name="us-east-1")
    # async def test_bedrock_llm_titan():
    #     test_messages_titan = [
    #         {"role": "user", "content": "Write a short story about a robot learning to paint."}
    #     ]
    #     try:
    #         print(f"\nTesting with model: {bedrock_llm_titan.model_id}")
    #         response = await bedrock_llm_titan(test_messages_titan, maxTokenCount=200) # Titan uses maxTokenCount
    #         print("\nBedrock LLM Response (Titan):")
    #         print(response)
    #     except Exception as e:
    #         print(f"Error during Titan test: {e}")
    # asyncio.run(test_bedrock_llm_titan())
