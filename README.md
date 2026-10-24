# Experiential Labs API client

A streaming chat client that uses only the Python standard library.

```bash
export EXPLABS_API_KEY="your-key"   # Settings -> API Keys; never commit this
python -m experiential_labs.client "Hello from my product"
```

In code:

```python
from experiential_labs.client import stream_chat
for chunk in stream_chat([{"role": "user", "content": "Hi"}]):
    print(chunk, end="")
```

## Decision helper (GPT-6 Luna Decisions)

`experiential_labs/decisions.py` asks typed decision questions (predicate / choice / score)
via `POST https://api.experientiallabs.ai/v1/decisions` with model `gpt-6-luna-decisions`.
It does not generate chat completions; the chat client above is unchanged.

```bash
export EXPERIENTIAL_API_KEY=...   # set locally; never paste or log it
python -m experiential_labs.decisions diff_summary.txt test_summary.txt
```

Results are advisory only: nothing is executed, merged or auto-approved. No automatic
retries, since an unknown outcome may already be charged. Tests: `python -m unittest discover -s tests -t .`
