import pandas as pd
from config import load_agent_thinking_workflows, load_final_aggregated_thinking
from workflow import process_thinking_workflows
from aggregation import aggregate_final_insights
from stats import calculate_message_stats
from agent import create_agent

def main():
    # Load the CSV files
    messages_df = pd.read_csv("csv/messages.csv")
    chats_df = pd.read_csv("csv/chats.csv")

    #messages_df = messages_df.head(5)
    #chats_df = chats_df.head(5)

    # Load configurations
    agent_thinking_workflows = load_agent_thinking_workflows("analyzer_agent/prompt_config.json")
    final_aggregated_thinking = load_final_aggregated_thinking()

    # Process workflows
    messages_df = calculate_message_stats(messages_df)
    messages_df.to_csv("csv/messages_stats.csv", index=False)
    client, assistant = create_agent()
    messages_df = process_thinking_workflows(client, assistant, messages_df, agent_thinking_workflows)
    messages_df.to_csv("csv/messages_stats_with_workflows.csv", index=False)
    # Aggregate final insights
    print("Aggregating final insights...")
    user_stats_df = aggregate_final_insights(client, assistant, messages_df, final_aggregated_thinking)

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

if __name__ == "__main__":
    main() 