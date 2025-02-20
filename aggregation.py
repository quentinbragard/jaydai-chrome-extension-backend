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

def calculate_max_grade(df, column):
    def parse_and_calculate(x):
        try:
            # Parse the JSON string into a Python object
            grades = json.loads(x)
            return max([grades[grade_name]['grade'] for grade_name in grades]) if grades else 0
        except (json.JSONDecodeError, TypeError):
            # Handle cases where parsing fails or the data is not as expected
            return -1

    return df[column].apply(parse_and_calculate).max()

def calculate_min_grade(df, column):
    def parse_and_calculate(x):
        try:
            # Parse the JSON string into a Python object
            grades = json.loads(x)
            return min([grades[grade_name]['grade'] for grade_name in grades]) if grades else 0
        except (json.JSONDecodeError, TypeError):
            # Handle cases where parsing fails or the data is not as expected
            return -1

    return df[column].apply(parse_and_calculate).min()


def aggregate_final_insights(df, aggregated_thinking):
    client = OpenAI()
    user_stats = {}
    for user_id, user_df in df.groupby('user_id'):
        user_stats[user_id] = {}
        for stat_name, config in aggregated_thinking.items():
            if stat_name == 'global_messages_avg_grade':
                print("user_df", user_df)
            if config['type'] == 'classic':
                column_data = pd.to_numeric(user_df[config['column']], errors='coerce').tolist()
                if config['operation'] == 'mean':
                    user_stats[user_id][stat_name] = pd.Series(column_data).mean()
                elif config['operation'] == 'median':
                    user_stats[user_id][stat_name] = pd.Series(column_data).median()
                elif config['operation'] == 'min':
                    user_stats[user_id][stat_name] = pd.Series(column_data).min()
                elif config['operation'] == 'max':
                    user_stats[user_id][stat_name] = pd.Series(column_data).max()
                elif config['operation'] == 'sum':
                    user_stats[user_id][stat_name] = pd.Series(column_data).sum()
                elif config['operation'] == 'count':
                    if 'filter' in config:
                        user_stats[user_id][stat_name] = user_df[user_df[config['column']] == config['filter']['role']].shape[0]
                    else:
                        user_stats[user_id][stat_name] = user_df.shape[0]
                elif config['operation'] == 'custom':
                    if config['custom_function'] == 'mean_grade':
                        user_stats[user_id][stat_name] = calculate_mean_grade(user_df, config['column'])
                    elif config['custom_function'] == 'max_grade':
                        user_stats[user_id][stat_name] = calculate_max_grade(user_df, config['column'])
                    elif config['custom_function'] == 'min_grade':
                        user_stats[user_id][stat_name] = calculate_min_grade(user_df, config['column'])
                    # Add more custom functions here as needed
                    # elif config['custom_function'] == 'another_custom_function':
                    #     user_stats[user_id][stat_name] = another_custom_function(user_df, config['column'])
           
            else:
                column_data = user_df[config['column']].tolist()
                column_data_str = ', '.join(map(str, column_data))
                if config['type'] == 'ai_based':
                    previous_output = None
                    for chain in config['prompt_chains']:
                        prompt = chain['prompt'].format(column=column_data_str, previous_output=previous_output)
                        previous_output = execute_prompt_chain(client, chain, prompt, previous_output)
                    user_stats[user_id][stat_name] = previous_output
    return pd.DataFrame.from_dict(user_stats, orient='index') 