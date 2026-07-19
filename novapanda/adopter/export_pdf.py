"""仲裁包 PDF 展示壳（无第三方依赖）。

验签真源仍是 JSON + ``reverify``；本 PDF 仅供人读，页脚强制声明。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .export_pkg import package_summary_text


def _escape_pdf_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _latin1_safe(s: str) -> str:
    """Helvetica 仅覆盖 Latin-1；中文等改为可打印占位，避免坏 PDF。"""
    return s.encode("latin-1", errors="replace").decode("latin-1")


def build_pdf_bytes(lines: Iterable[str], *, title: str = "NovaPanda Export") -> bytes:
    """最小生成 PDF 1.4（单页文本）。"""
    safe_lines = [_latin1_safe(line)[:120] for line in lines]
    # 从顶部往下排
    y0 = 800
    leading = 14
    content_parts = ["BT", "/F1 10 Tf", "14 TL"]
    for i, line in enumerate(safe_lines):
        y = y0 - i * leading
        if y < 40:
            break
        content_parts.append(f"1 0 0 1 40 {y} Tm ({_escape_pdf_text(line)}) Tj")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        b"4 0 obj<< /Length " + str(len(stream)).encode() + b" >>stream\n"
        + stream + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R /Info ({_escape_pdf_text(_latin1_safe(title))}) >>\n".encode()
    )
    out.extend(f"startxref\n{xref_pos}\n%%EOF\n".encode())
    return bytes(out)


def write_arbitration_pdf(path: Path | str, package: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = package_summary_text(package).splitlines()
    lines.append("")
    lines.append("INFORMATIVE SHELL ONLY — not a cryptographic proof.")
    path.write_bytes(build_pdf_bytes(lines, title="NovaPanda Arbitration"))
    return path
