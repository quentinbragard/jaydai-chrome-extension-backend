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
                        instructions = read_text_file(chain['instructions_file'])
                        prompt = chain['prompt'].format(source=row, previous_output=previous_output)
                        previous_output = execute_prompt_chain(client, instructions, prompt, previous_output)
                    print(f"--> Next output output: {previous_output}\n")
                    df.at[index, f"{workflow_name}_output"] = previous_output
    return df

def execute_prompt_chain(client, instructions, prompt, previous_output):
    #try:
    print(f"Executing prompt chain with instructions: {instructions}\n")
    print(f"Executing prompt chain with prompt: {prompt}\n")    
    print(f"Executing prompt chain with previous_output: {previous_output}\n")
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt}
            ]
        )
    return completion.choices[0].message.content
    # except Exception as e:
    #     return f"Error: {e}" 