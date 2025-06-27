import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
# This is where AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional),
# and AWS_DEFAULT_REGION or AWS_REGION might be set if not configured globally.
# Boto3 will automatically look for credentials in standard locations:
# 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.)
# 2. Shared credential file (~/.aws/credentials)
# 3. AWS config file (~/.aws/config)
# 4. IAM roles for EC2 instances or ECS tasks
load_dotenv()

from browser_use import Agent
# Import the custom Bedrock LLM wrapper
from bedrock_llm import ChatBedrock

async def main():
    """
    Demonstrates using the browser-use Agent with a custom AWS Bedrock LLM.
    """
    print("Initializing Bedrock LLM for the agent...")

    # Configure the Bedrock LLM
    # Replace with your desired Bedrock model ID and AWS region if needed.
    # Common model IDs:
    # - Anthropic Claude: "anthropic.claude-v2:1", "anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0"
    # - Amazon Titan: "amazon.titan-text-express-v1", "amazon.titan-text-lite-v1"
    # - AI21 Labs Jurassic: "ai21.j2-mid-v1", "ai21.j2-ultra-v1"
    # - Cohere Command: "cohere.command-text-v14"
    # Ensure the chosen model is enabled for your AWS account in the specified region.
    bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0" # Example: Claude Haiku
    aws_region = None # Or specify e.g., "us-east-1". If None, boto3 uses default.

    try:
        chat_bedrock_llm = ChatBedrock(
            model_id=bedrock_model_id,
            region_name=aws_region
        )
        print(f"Using Bedrock model: {bedrock_model_id} in region: {chat_bedrock_llm.bedrock_runtime.meta.region_name}")

        # Define the task for the agent
        # The task from your example: "Compare the price of gpt-4o and DeepSeek-V3"
        # This task might be challenging for an LLM if it requires very up-to-date, specific pricing
        # not commonly found in its training data or easily searchable in a general way.
        # For a better demonstration, a more general web research task might be more suitable.
        # task = "Find the current CEO of NVIDIA and the company's latest stock price."
        task = "Compare the price of gpt-4o and DeepSeek-V3. Summarize your findings."

        print(f"\nInitializing Agent with task: '{task}'")
        agent = Agent(
            task=task,
            llm=chat_bedrock_llm,
            # You can pass additional parameters to the LLM via agent's llm_kwargs
            # These will be passed to the ChatBedrock.__call__ method's **kwargs
            llm_kwargs={
                "temperature": 0.5,
                # For Claude models:
                "max_tokens_to_sample": 500,
                # "top_p": 0.9,
                # For Titan models:
                # "maxTokenCount": 500,
            }
        )

        print("Running agent...")
        # The agent.run() method will internally call chat_bedrock_llm(messages=...)
        await agent.run()
        print("\nAgent run finished.")

    except Exception as e:
        print(f"An error occurred in the main execution: {e}")
        print("Please ensure:")
        print("1. Your AWS credentials are correctly configured (e.g., via environment variables, ~/.aws/credentials, or IAM role).")
        print("2. The Bedrock model ID is correct and you have access to it in the specified AWS region.")
        print("3. `boto3` and `browser-use` are installed.")
        print("4. You have run `playwright install chromium --with-deps`.")

if __name__ == "__main__":
    asyncio.run(main())
