import pandas as pd

def calculate_message_stats(df):
    models_pricing_data = pd.read_csv("csv/models_pricing.csv")   
    models_pricing_df = pd.DataFrame(models_pricing_data)
    df['message_length'] = df['content'].apply(lambda x: len(x.split()))
    df['total_tokens'] = df['message_length'] * 1.3
    
    # Merge with model pricing to get the correct pricing for each model
    df = df.merge(models_pricing_df, on='model', how='left')
    
    # Calculate cost using the merged pricing information
    df['cost'] = df.apply(
        lambda row: row['total_tokens'] * row['input_price_per_token'] if row['role'] == 'user' 
        else row['total_tokens'] * row['output_price_per_token'], axis=1
    )
    
    # Calculate energy consumption
    df['energy_consumption'] = df['total_tokens'] * 3.24 / 3600000
    
    return df