from datetime import datetime, timezone
from pathlib import Path


def write_output(path: str, content: str) -> Path:
    """Write markdown content to output path, creating dirs if needed."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return out


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def section(title: str, content: str) -> str:
    return f"### {title}\n\n{content}\n"


def table(headers: list[str], rows: list[list[str]]) -> str:
    header_row = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return f"{header_row}\n{separator}\n{data_rows}"