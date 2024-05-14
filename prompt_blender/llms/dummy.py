import time
import random

def info():
    return {
        "name": "dummy",
        "description": "Dummy LLMS module for testing purposes.",
    }

def exec_init():
    pass

def get_args(args=None):
    return {}


def exec(prompt):
    fake_response = {
        "choices": [
            {
                "message": {
                    "content": "Texto de resposta do modelo GPT."
                }
            }
        ]
    }
    print("Executando o modelo dummy...")

    time.sleep(0.05)

    return {
        "response": fake_response,
        "cost": 0.001 + random.random() * 0.002
    }

def exec_close():
    pass

        
