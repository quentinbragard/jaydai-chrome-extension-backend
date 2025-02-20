import pandas as pd

def aggregate_final_insights(df, aggregated_thinking):
    user_stats = {}
    for user_id, user_df in df.groupby('user_id'):
        user_stats[user_id] = {}
        for stat_name, config in aggregated_thinking.items():
            if config['type'] == 'classic':
                column_data = pd.to_numeric(user_df[config['column']], errors='coerce').tolist()
                if config['operation'] == 'mean':
                    user_stats[user_id][stat_name] = pd.Series(column_data).mean()
                # Add more operations as needed
            else:
                column_data = user_df[config['column']].tolist()
                column_data_str = ', '.join(map(str, column_data))
                if config['type'] == 'ai_based':
                    previous_output = None
                    for chain in config['prompt_chains']:
                        previous_output = execute_prompt_chain(client, chain, column_data_str, previous_output)
                    user_stats[user_id][stat_name] = previous_output
    return pd.DataFrame.from_dict(user_stats, orient='index') 