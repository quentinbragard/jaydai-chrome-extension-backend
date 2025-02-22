from openai import OpenAI
from utils import read_text_file

def create_agent():
    client = OpenAI()
    assistant = client.beta.assistants.create(
        name="Grading Assistant",
        instructions=read_text_file("analyzer_agent/prompts/explain_grade_instructions.txt"),
        model="gpt-4o-mini",
        tools=[{"type": "file_search"}],
    )
    vector_store = client.beta.vector_stores.create(name="Assistant Documentation")

    # Upload files once
    file_paths = ["analyzer_agent/prompts/explain_grade_instructions.txt"]  # Update with actual file paths
    file_streams = [open(path, "rb") for path in file_paths]
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )
    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    return client, assistant 