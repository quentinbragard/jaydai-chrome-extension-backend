import json

def load_agent_thinking_workflows(file_path):
    with open(file_path, "r") as file:
        return json.load(file)

def load_final_aggregated_thinking(file_path="analyzer_agent/final_aggregated_thinking.json"):
    with open(file_path, "r") as file:
        return json.load(file) 