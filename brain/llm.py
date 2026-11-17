import json
import urllib.request


class LLM:
    def __init__(self, llm_config):
        self.config = llm_config
        self.history = []

    def ask(self, question: str) -> str | None:
        if not self.config.api_key:
            return None
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            *self.history[-6:],
            {"role": "user", "content": question},
        ]
        payload = json.dumps({
            "model": self.config.model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.api_base.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                answer = json.loads(response.read())["choices"][0]["message"]["content"]
        except Exception:
            return None
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
        return answer

    def reset(self):
        self.history = []
