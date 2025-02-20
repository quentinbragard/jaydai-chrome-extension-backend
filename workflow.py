from openai import OpenAI
from utils import read_text_file

def process_thinking_workflows(df, workflows):
    client = OpenAI()
    for workflow_name, steps in workflows.items():
        for step in steps:
            if step['source'] == 'messages':
                df[workflow_name] = None  # Initialize the column
                for index, row in df.iterrows():
                    previous_output = None
                    for chain in step['prompt_chains']:
                        instructions = read_text_file(chain['instructions_file'])
                        prompt = chain['prompt'].format(source=row, previous_output=previous_output)
                        previous_output = execute_prompt_chain(client, instructions, prompt, previous_output)
                    df.at[index, workflow_name] = previous_output
    return df

def execute_prompt_chain(client, instructions, prompt, previous_output):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {e}" 