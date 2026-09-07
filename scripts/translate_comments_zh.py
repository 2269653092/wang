"""将项目内 Python 注释和文档字符串批量翻译为中文。"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from transformers import MarianMTModel, MarianTokenizer


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {"__pycache__", ".venv", "venv", ".git"}
HAN_RE = re.compile(r"[\u3400-\u9fff]")
EN_RE = re.compile(r"[A-Za-z]{2,}")
CODE_COMMENT_RE = re.compile(
    r"^(?:from\s+[\w.]+\s+import\s+|import\s+[\w.]|[A-Za-z_][\w.]*\s*=|[)}\]]|noqa\b|type:\s*ignore|fmt:|pylint:|ruff:|pragma:)",
)


def needs_translation(text: str) -> bool:
    """判断文本是否包含需要翻译的英文说明。"""
    stripped = text.strip()
    return bool(EN_RE.search(stripped)) and not HAN_RE.search(stripped) and not CODE_COMMENT_RE.match(stripped)


MODEL_NAME = "Helsinki-NLP/opus-mt-en-zh"
TOKENIZER: MarianTokenizer | None = None
MODEL: MarianMTModel | None = None


def translate_many(texts: list[str]) -> list[str]:
    """使用本地机器翻译模型批量翻译文本。"""
    global TOKENIZER, MODEL
    if TOKENIZER is None or MODEL is None:
        TOKENIZER = MarianTokenizer.from_pretrained(MODEL_NAME)
        MODEL = MarianMTModel.from_pretrained(MODEL_NAME)
    results: list[str] = []
    for start in range(0, len(texts), 16):
        batch = texts[start : start + 16]
        encoded = TOKENIZER(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
        generated = MODEL.generate(**encoded)
        results.extend(item.strip() for item in TOKENIZER.batch_decode(generated, skip_special_tokens=True))
    return results


def docstring_rows(source: str) -> set[int]:
    """收集模块、类和函数文档字符串所占的起始行。"""
    tree = ast.parse(source)
    rows: set[int] = set()
    nodes = [tree, *(node for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))]
    for node in nodes:
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            rows.add(body[0].value.lineno)
    return rows


def quote_docstring(original: str, translated: str) -> str:
    """沿用原文档字符串的引号形式，并保留缩进。"""
    match = re.match(r"(?s)([rubfRUBF]*)(\"\"\"|''')", original)
    if not match:
        return original
    prefix, quote = match.groups()
    return f"{prefix}{quote}{translated}{quote}"


def process(path: Path) -> int:
    """翻译单个 Python 文件，返回发生修改的注释数量。"""
    source = path.read_text(encoding="utf-8-sig")
    rows = docstring_rows(source)
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    targets: list[tuple[int, str, str]] = []
    for index, token in enumerate(tokens):
        replacement = token.string
        if token.type == tokenize.COMMENT and not replacement.startswith("#!"):
            body = replacement[1:].strip()
            if needs_translation(body):
                targets.append((index, "comment", body))
        elif token.type == tokenize.STRING and token.start[0] in rows:
            try:
                value = ast.literal_eval(replacement)
            except (ValueError, SyntaxError):
                value = ""
            if isinstance(value, str) and needs_translation(value):
                targets.append((index, "docstring", value))

    if not targets:
        return 0

    translations = translate_many([item[2] for item in targets])
    for (index, kind, _), translated in zip(targets, translations):
        token = tokens[index]
        replacement = "# " + translated if kind == "comment" else quote_docstring(token.string, translated)
        tokens[index] = token._replace(string=replacement)

    path.write_text(tokenize.untokenize(tokens), encoding="utf-8")
    return len(targets)


def main() -> None:
    """遍历项目中的 Python 文件并输出翻译统计。"""
    total = 0
    files = 0
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_PARTS for part in path.parts) or path == Path(__file__):
            continue
        count = process(path)
        if count:
            files += 1
            total += count
            print(f"{path.relative_to(ROOT)}: {count}")
    print(f"完成：修改 {files} 个文件，共翻译 {total} 处。")


if __name__ == "__main__":
    main()
