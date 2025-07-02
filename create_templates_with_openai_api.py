import time
from openai import OpenAI
import json
import os
import pandas as pd
import argparse

# Set up your OpenAI API key
# Make sure to set the OPENAI_API_KEY environment variable.
# For example, on Linux/macOS: export OPENAI_API_KEY='your_api_key'
# On Windows: set OPENAI_API_KEY='your_api_key'
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Your assistant ID
assistant_id = "asst_1ZMYZIZlCXTPV5I3slc33VNt"

def call_assistant_and_get_response(assistant_id, user_prompt):
    """
    Creates a thread, sends a message to the assistant, runs the assistant,
    and retrieves the assistant's response. It polls the run status with a delay to avoid rate limiting.
    """
    try:
        # Create a new thread for each prompt
        thread = client.beta.threads.create()
        thread_id = thread.id

        # Add the user's message to the thread
        print("-> Creating message in thread...")
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_prompt,
        )

        # Create a run for the assistant to process the message
        print("-> Running assistant...")
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        # Poll for the run's completion
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            print(f"-> Run status: {run.status}")
            if run.status in ["failed", "cancelled", "expired"]:
                print(f"Error: Run failed with status {run.status}. Reason: {run.last_error}")
                # You can check run.last_error for specific error messages (e.g., token limits)
                return f"Error: Run failed with status {run.status}."
            time.sleep(10)  # Increased delay to 10 seconds to reduce API calls and avoid rate limits.

        # Once the run is completed, retrieve the messages from the thread
        messages = client.beta.threads.messages.list(thread_id=thread_id)

        # Get the assistant's response (the last message in the thread from the assistant)
        assistant_response = ""
        # The list is in reverse chronological order, so the assistant's response is the first message
        for msg in messages.data:
            if msg.role == "assistant":
                for content_block in msg.content:
                    if content_block.type == "text":
                        assistant_response += content_block.text.value
                break # Exit loop after getting the first assistant message

        # Clean up the thread to avoid clutter and associated costs
        # Note: The API does not have a direct delete thread method from the Python library at the time of this writing.
        # Threads expire after 7 days, so manual deletion isn't strictly necessary for cleanup, but it's good practice.
        # If you need to manage threads, you'd do it manually or with a specific API call if available.

        return assistant_response.strip()

    except Exception as e:
        # Catch any exceptions, including API errors (e.g., rate limits, invalid requests)
        print(f"An unexpected error occurred: {e}")
        # Check if the error is due to tokens and give a specific warning
        if "maximum context length" in str(e):
            return "Warning: Prompt too long. The API's token limit has been exceeded. Please reduce the prompt size."
        return f"An error occurred: {e}"

def main():
    """
    Reads prompts and titles from a CSV, calls the assistant, and saves the output.
    """
    parser = argparse.ArgumentParser(description="Process prompts with OpenAI Assistant and save responses.")
    parser.add_argument("source_filename", type=str, help="CSV file with columns 'title' and 'prompt'")
    parser.add_argument("output_filename", type=str, help="CSV file to save the assistant responses")
    args = parser.parse_args()

    source_filename = args.source_filename
    output_filename = args.output_filename

    print(f"Reading prompts from '{source_filename}'.")
    df_source = pd.read_csv(source_filename)
    print(f"Found {len(df_source)} prompts in the source file.")
    print(f"Results will be saved to '{output_filename}'.")

    results = []
    for i, row in df_source.iterrows():
        title = row["title"]
        prompt = row["content"]
        print(f"-> Processing prompt {i+1}/{len(df_source)}: {title}")

        response_content = call_assistant_and_get_response(assistant_id, prompt)
        results.append({"content": response_content, "title": title})
        print(f"-> Result for '{title}' saved to results list.")

    df = pd.DataFrame(results)
    df.to_csv(output_filename, index=False)
    print("\n" + "="*80)
    print(f"All prompts processed. Final output saved to '{output_filename}'.")
    print("="*80)

if __name__ == "__main__":
    main()