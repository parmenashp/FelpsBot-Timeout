from typing import Optional


def to_codeblock(content: str, language: Optional[str] = "") -> str:
    if language:
        return f"```{language}\n{content}\n```"
