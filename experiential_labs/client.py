"""Minimal streaming client for the Experiential Labs chat completions API."""
import json
import os
import sys
import urllib.request

API_URL = "https://api.experientiallabs.ai/v1/chat/completions"
DEFAULT_MODEL = "glm-5.3-uncensored"


def stream_chat(messages, model=DEFAULT_MODEL, api_key=None):
    """Yield content chunks from a streamed chat completion."""
    api_key = api_key or os.environ.get("XPL_API_KEY")
    if not api_key:
        raise RuntimeError("Set the XPL_API_KEY environment variable.")
    body = json.dumps({"model": model, "stream": True, "messages": messages}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {})
            if delta.get("content"):
                yield delta["content"]


def main():
    prompt = " ".join(sys.argv[1:]) or "Hello from my product"
    for chunk in stream_chat([{"role": "user", "content": prompt}]):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
