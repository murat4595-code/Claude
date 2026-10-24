# Experiential Labs API client

A streaming chat client that uses only the Python standard library.

```bash
export XPL_API_KEY="your-key"   # never commit this
python -m experiential_labs.client "Hello from my product"
```

In code:

```python
from experiential_labs.client import stream_chat
for chunk in stream_chat([{"role": "user", "content": "Hi"}]):
    print(chunk, end="")
```
