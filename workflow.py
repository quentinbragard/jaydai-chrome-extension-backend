from agent import create_agent
from utils import read_text_file

def process_thinking_workflows(client, assistant, df, workflows):
    print("Processing workflows...")
    for workflow_name, steps in workflows.items():
        for step in steps:
            if step['source'] == 'messages':
                df[f"{workflow_name}_output"] = None
                for index, row in df.iterrows():
                    print(f"Processing message ID: {row['message_id']}")
                    if step['filter']:
                        if row[step['filter']['filter_column']] != step['filter']['filter_value']:
                            continue
                    previous_output = None
                    for chain in step['prompt_chains']:
                        prompt = chain['prompt'].format(source=row, previous_output=previous_output)
                        previous_output = execute_prompt_chain(client, assistant, chain, prompt)
                    df.at[index, f"{workflow_name}_output"] = previous_output
    print("Workflows processed successfully 🎉")
    return df

def execute_prompt_chain(client, assistant, chain, prompt):
    # Use the existing assistant and vector store
    print(f"Executing prompt chain: {chain['prompt']}")
    if 'tools' in chain:
        # Use the existing vector store
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant.id
        )
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
        return messages[0].content[0].text
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