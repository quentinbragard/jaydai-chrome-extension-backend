from openai import OpenAI
from utils import read_text_file

def process_thinking_workflows(df, workflows):
    client = OpenAI()
    for workflow_name, steps in workflows.items():
        for step in steps:
            print(f"Step: {step}\n'n")
            if step['source'] == 'messages':
                df[f"{workflow_name}_output"] = None  # Initialize the column
                for index, row in df.iterrows():
                    previous_output = None
                    print(f"Previous output: {previous_output}\n")
                    for chain in step['prompt_chains']:
                        print(f"Chain: {chain}\n")
                        prompt = chain['prompt'].format(source=row, previous_output=previous_output)
                        previous_output = execute_prompt_chain(client, chain, prompt, previous_output)

                    print(f"--> Next output output: {previous_output}\n")
                    df.at[index, f"{workflow_name}_output"] = previous_output
    return df

def execute_prompt_chain(client, chain, prompt, previous_output):
    #try:
    print(f"Executing prompt chain with instructions: {read_text_file(chain['instructions_file'])}\n")
    print(f"Executing prompt chain with prompt: {prompt}\n")    
    print(f"Executing prompt chain with previous_output: {previous_output}\n")
    if 'tools' in chain:
       for tool in chain['tools']:
           assistant = client.beta.assistants.create(
               name="Financial Analyst Assistant",
                instructions=read_text_file(chain['instructions_file']),
                model=chain['model'],
                tools=chain['tools'],
)
           if tool['type'] == 'file_search':
               # Create a vector store caled "Financial Statements"
                vector_store = client.beta.vector_stores.create(name="Assistant Documentation")

                # Ready the files for upload to OpenAI
                file_paths = chain['docs']
                print(f"File paths: {file_paths}\n")
                file_streams = [open(path, "rb") for path in file_paths]

                # Use the upload and poll SDK helper to upload the files, add them to the vector store,
                # and poll the status of the file batch for completion.
                file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id, files=file_streams
                )

                # You can print the status and the file counts of the batch to see the result of this operation.
                print(file_batch.status)
                print(file_batch.file_counts)
                assistant = client.beta.assistants.update(
                    assistant_id=assistant.id,
                    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
                )

                # Create a thread and attach the file to the message
                print("creating thread")
                thread = client.beta.threads.create(
                messages=[
                    {
                    "role": "user",
                    "content": prompt,
                    }
                ]
                )
                print("thread created")
                # The thread now has a vector store with that file in its tool resources.
                print(thread.tool_resources.file_search)
                # Use the create and poll SDK helper to create a run and poll the status of
                # the run until it's in a terminal state.

                run = client.beta.threads.runs.create_and_poll(
                    thread_id=thread.id, assistant_id=assistant.id
                )

                messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

                message_content = messages[0].content[0].text
                annotations = message_content.annotations
                citations = []
                for index, annotation in enumerate(annotations):
                    message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
                    if file_citation := getattr(annotation, "file_citation", None):
                        cited_file = client.files.retrieve(file_citation.file_id)
                        citations.append(f"[{index}] {cited_file.filename}")

                print(message_content.value)
                print("\n".join(citations))
                return message_content.value
    else:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                    {"role": "system", "content": read_text_file(chain['instructions_file'])},
                    {"role": "user", "content": prompt}
                ]
            )
        return completion.choices[0].message.content
    # except Exception as e:
    #     return f"Error: {e}" 