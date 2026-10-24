"""Minimal streaming client for the Experiential Labs chat completions API."""
import json
import os
import sys
import urllib.request

BASE_URL = "https://api.experientiallabs.ai/v1"
API_URL = f"{BASE_URL}/chat/completions"
DEFAULT_MODEL = "glm-5.3-flash-uncensored"


def stream_chat(messages, model=DEFAULT_MODEL, api_key=None, usage=None):
    """Yield content chunks from a streamed chat completion.

    Pass a dict as ``usage`` to have it filled with the final token usage.
    """
    api_key = api_key or os.environ.get("EXPLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "EXPLABS_API_KEY is not set. Create a key under Settings -> API Keys "
            "and export it: export EXPLABS_API_KEY=..."
        )
    body = json.dumps({
        "model": model,
        "stream": True,
        "stream_options": {"include_usage": True},
        "messages": messages,
    }).encode()
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
            event = json.loads(data)
            if usage is not None and event.get("usage"):
                usage.update(event["usage"])
            if not event.get("choices"):
                continue
            delta = event["choices"][0].get("delta", {})
            if delta.get("content"):
                yield delta["content"]


def main():
    prompt = " ".join(sys.argv[1:]) or "Hello from my product"
    usage = {}
    for chunk in stream_chat([{"role": "user", "content": prompt}], usage=usage):
        print(chunk, end="", flush=True)
    print()
    if usage:
        print(f"[usage] {json.dumps(usage)}", file=sys.stderr)


if __name__ == "__main__":
    main()
