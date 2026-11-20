
import requests

url = "http://localhost:11434/api/generate"

data = {
    "model": "llama3.2:1b",
    "prompt": "Hello! Explain how AI works.",
    "stream": False
}

try:
    response = requests.post(
        url,
        json=data,
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    print("\nMYAI RESPONSE:\n")
    print(result["response"])

except requests.exceptions.RequestException as error:
    print("Connection error:", error)
