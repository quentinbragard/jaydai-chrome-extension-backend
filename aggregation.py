import pandas as pd
import json
from openai import OpenAI
from workflow import execute_prompt_chain

def calculate_mean_grade(df, column):
    def parse_and_calculate(x):
        try:
            # Parse the JSON string into a Python object
            grades = json.loads(x)
            print(grades)
            for grade in grades:
                print(grade)
            # Calculate the mean grade
            return sum([grades[grade_name]['grade'] for grade_name in grades]) / len(grades) if grades else 0
        except (json.JSONDecodeError, TypeError):
            # Handle cases where parsing fails or the data is not as expected
            return -1

    return df[column].apply(parse_and_calculate).mean()

def aggregate_final_insights(df, aggregated_thinking):
    client = OpenAI()
    user_stats = {}
    for user_id, user_df in df.groupby('user_id'):
        user_stats[user_id] = {}
        for stat_name, config in aggregated_thinking.items():
            print("\n\n++++++++++++aggregating", stat_name)
            print("++++++++++++config", config)
            print("++++++++++++user_df", user_df)
            print("++++++++++++user_id", user_id)
            if config['type'] == 'classic':
                print(f"user_df = {user_df}")
                column_data = pd.to_numeric(user_df[config['column']], errors='coerce').tolist()
                print(f"user_df : {user_df}\n")
                print(f"config['column'] : {config['column']}\n")
                print(f"user_df[config['column']] : {user_df[config['column']]}\n")
                if config['operation'] == 'mean':
                    user_stats[user_id][stat_name] = pd.Series(column_data).mean()
                # Add more operations as needed
            elif config['type'] == 'custom' and config['operation'] == 'mean_grade':
                user_stats[user_id][stat_name] = calculate_mean_grade(user_df, config['column'])
            else:
                column_data = user_df[config['column']].tolist()
                print("!!!!!!!!!!!!!!!!!!!!column_data", column_data)
                column_data_str = ', '.join(map(str, column_data))
                if config['type'] == 'ai_based':
                    previous_output = None
                    print("---------------------config", config)
                    for chain in config['prompt_chains']:
                        instructions = chain['instructions']
                        prompt = chain['prompt'].format(column=column_data_str, previous_output=previous_output)
                        print("!!!!!!!!!!!!!!!!!!!!!!!instructions", instructions)
                        print("!!!!!!!!!!!!!!!!!!!!!!!prompt", prompt)
                        previous_output = execute_prompt_chain(client, instructions, prompt, previous_output)
                    user_stats[user_id][stat_name] = previous_output
    return pd.DataFrame.from_dict(user_stats, orient='index') 