from openai import OpenAI

import pandas as pd

# Load the CSV files
messages_df = pd.read_csv("csv/messages.csv")
chats_df = pd.read_csv("csv/chats.csv")

messages_df = messages_df.head(2)
chats_df = chats_df.head(2)


# Create a DataFrame for model pricing
models_pricing_data = pd.read_csv("csv/models_pricing.csv")   
models_pricing_df = pd.DataFrame(models_pricing_data)

# Define agent thinking workflows
agent_thinking_workflows = {
    "grade_prompt": [
        {
            "source": "messages",
            "prompt_chains": [
                {"instructions": "Your role is to grade this message between 0 and 20. Return only a number between 0 and 20, with no additional text. Grade higher scores for more efficient prompts.", "prompt": "The message is: {source[content]}"}
            ]
        }
    ],
    "explain_grade": [
        {
            "source": "messages",
            "prompt_chains": [
                {"instructions": "Your role is to explain the grade of the prompt. You should give activable reasons for the grade and advises to prompt better.", "prompt": "The message is: {source[content]} and the grade is: {source[grade_prompt]}"}
            ]
        }
    ],
    #"find_skills_in_message": [
    #    {
    #        "source": "messages",
    #        "prompt_chains": [
    #            {"instructions": "Your role is to sum up this prompt with a focus on what the user wants to achieve.", "prompt": "The prompt is: {source[content]}"},
    #            {"instructions": "Analyze the discussion and return a comma-separated list of relevant professional skills (e.g. coding, marketing, data analysis). Return only the skills list, no other text.", "prompt": "The discussion sum up is: {previous_output}"}
    #        ]
    #    }
    #]
}

# Function to calculate message statistics
def calculate_message_stats(df):
    df['message_length'] = df['content'].apply(lambda x: len(x.split()))
    df['total_tokens'] = df['message_length'] * 1.3
    
    # Merge with model pricing to get the correct pricing for each model
    df = df.merge(models_pricing_df, on='model', how='left')
    
    # Calculate cost using the merged pricing information
    df['cost'] = df.apply(
        lambda row: row['total_tokens'] * row['input_price_per_token'] if row['role'] == 'user' 
        else row['total_tokens'] * row['output_price_per_token'], axis=1
    )
    
    return df

# Apply the function to calculate stats
messages_df = calculate_message_stats(messages_df)

# Function to process thinking workflows
def process_thinking_workflows(df, workflows):
    client = OpenAI()
    for workflow_name, steps in workflows.items():
        for step in steps:
            print(f"Step: \n{step}\n\n\n")
            if step['source'] == 'messages':
                df[workflow_name] = None  # Initialize the column
                for index, row in df.iterrows():
                    previous_output = None
                    for chain in step['prompt_chains']:
                        print("\nprevious_output: ", previous_output)
                        previous_output = execute_prompt_chain(client, chain, row, previous_output)
                        print("\n -------->new_output: ", previous_output)
                        print("\n\n")
                    df.at[index, workflow_name] = previous_output
    return df

# Function to execute a prompt chain
def execute_prompt_chain(client, chain, input_data, previous_output):
    print(f"\n========execute_prompt_chain :\ninput_data: {input_data}")
    # Determine if input_data is a Series or a string
    if isinstance(input_data, pd.Series):
        prompt = chain['prompt'].format(source=input_data, previous_output=previous_output)
    else:
        prompt = chain['prompt'].format(column=input_data, previous_output=previous_output)
    
    instructions = chain['instructions']
    print(f"\nprompt:{prompt}\n instructions:{instructions}\n\n")

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

# Process workflows
messages_df = process_thinking_workflows(messages_df, agent_thinking_workflows)
print("messages_df: ", messages_df)

# Define final aggregated thinking with aggregation types
final_aggregated_thinking = {
    "assistant_grade_mean": {
        "source": "messages",
        "column": "grade_prompt",
        "type": "classic",
        "operation": "mean"
    },
    "assistant_grade_explanation": {
        "source": "messages",
        "column": "explain_grade",
        "type": "ai_based",
        "prompt_chains": [
            {"instructions": "With all the explanations provided, explain the mean grade. Example output: 'You have often given precise instructions to the assistat which is good but you couls have added more context sometimes'", "prompt": "Grades explanations: {column}"}
        ]
    },
     #"identify_skills": {
     #    "source": "messages",
     #    "column": "find_skills_in_message",
     #    "type": "ai_based",
     #    "prompt_chains": [
     #        {"instructions": "Looking at the dfferent skills at stake tel which where the skils that were the most often mobilized", "prompt": "skills: {column}"}
     #    ]
    #},
   # "custom_lambda_example": {
   #     "source": "messages",
   #     "column": "message_length",
   #     "type": "lambda",
   #     "function": lambda x: sum(x) / len(x)  # Example lambda function for mean
   # }
}

# Function to aggregate final insights
def aggregate_final_insights(df, aggregated_thinking):
    client = OpenAI()
    user_stats = {}
    for user_id, user_df in df.groupby('user_id'):
        user_stats[user_id] = {}
        for stat_name, config in aggregated_thinking.items():
            if config['type'] == 'classic':
                # Convert column data to numeric, coercing errors to NaN
                column_data = pd.to_numeric(user_df[config['column']], errors='coerce').tolist()
                print(f"++++++++++++++++++++++++++++++++aggregate_final_insights\ncolumn_data (numeric): {column_data}")
                if config['operation'] == 'mean':
                    user_stats[user_id][stat_name] = pd.Series(column_data).mean()
                elif config['operation'] == 'sum':
                    user_stats[user_id][stat_name] = pd.Series(column_data).sum()
                elif config['operation'] == 'count':
                    user_stats[user_id][stat_name] = len(column_data)
                elif config['operation'] == 'min':
                    user_stats[user_id][stat_name] = min(column_data)
                elif config['operation'] == 'max':
                    user_stats[user_id][stat_name] = max(column_data)
                # Add more operations as needed
            else:
                # Use original data type for lambda and ai_based
                column_data = user_df[config['column']].tolist()
                column_data_str = ', '.join(map(str, column_data))
                print(f"\ncolumn_data (original): {column_data}")
                if config['type'] == 'lambda':
                    user_stats[user_id][stat_name] = config['function'](column_data)
                elif config['type'] == 'ai_based':
                    previous_output = None
                    for chain in config['prompt_chains']:
                        print("\nprevious_output: ", previous_output)
                        previous_output = execute_prompt_chain(client, chain, column_data_str, previous_output)
                        print("/n--------->new_output: ", previous_output)
                    user_stats[user_id][stat_name] = previous_output
    return pd.DataFrame.from_dict(user_stats, orient='index')

# Aggregate final insights
user_stats_df = aggregate_final_insights(messages_df, final_aggregated_thinking)

# Ensure user_id is the index
user_stats_df.index.name = 'user_id'

# Calculate chat-related statistics
chat_stats = chats_df.groupby('user_id').agg({
    'id': 'count'  # Total chats
}).rename(columns={'id': 'total_chats'})

# Merge chat statistics with user statistics
final_stats = user_stats_df.join(chat_stats, on='user_id')

# Save the results
final_stats.to_csv("csv/user_stats.csv", index=True)

print("User statistics and insights saved to csv/user_stats.csv")
