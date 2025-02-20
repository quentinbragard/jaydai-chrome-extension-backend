import json

def load_agent_thinking_workflows(file_path):
    with open(file_path, "r") as file:
        return json.load(file)

def load_final_aggregated_thinking():
    return {
        "assistant_grade_mean": {
            "source": "messages",
            "column": "grade_prompt_output",
            "type": "classic",
            "operation": "mean"
        },
        "assistant_grade_explanation": {
            "source": "messages",
            "column": "explain_grade",
            "type": "ai_based",
            "prompt_chains": [
                {
                    "instructions": "With all the explanations provided, explain the mean grade. Example output: 'You have often given precise instructions to the assistat which is good but you couls have added more context sometimes'",
                    "prompt": "Grades explanations: {column}"
                }
            ]
        }
    } 