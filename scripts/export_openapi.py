"""Export the exact FastAPI schema without a cloud key or model download."""

import json
import tempfile
from pathlib import Path

from knowflow.api.app import create_app
from knowflow.config import Settings
from knowflow.rag.llm import FakeLLM

ROOT = Path(__file__).parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="knowflow-openapi-") as temporary:
        root = Path(temporary)
        settings = Settings(
            database_url=f"sqlite:///{root / 'openapi.db'}",
            chroma_path=str(root / "chroma"),
            upload_path=str(root / "uploads"),
            report_path=str(root / "reports"),
            embedding_backend="hash",
            vector_backend="memory",
        )
        schema = create_app(settings, llm=FakeLLM()).openapi()
    output = ROOT / "docs" / "openapi.json"
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
