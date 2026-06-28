import glob
import re
import struct
import sys

def extract_doc_text(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()

  # Try UTF-16-LE chunks common in legacy .doc files
    parts = []
    i = 0
    while i < len(data) - 1:
        if data[i] >= 0x20 and data[i + 1] == 0x00:
            run = []
           

            j = i
            while j < len(data) - 1:
                lo, hi = data[j], data[j + 1]
                if hi != 0:
                    break
                if lo == 0:
                    break
                if lo < 0x20 and lo not in (9, 10, 13):
                    break
                run.append(chr(lo))
                j += 2
            if len(run) >= 4:
                parts.append("".join(run))
            i = j
        else:
            i += 1

    text = "\n".join(parts)
    if len(re.findall(r"[\u4e00-\u9fff]", text)) > 100:
        return text

    # Fallback: decode whole file loosely
    for enc in ("utf-16-le", "gb18030", "gbk"):
        try:
            t = data.decode(enc, errors="ignore")
            chinese = re.findall(r"[\u4e00-\u9fff，。、；：""''（）\-\d\w\s]{5,}", t)
            if len(chinese) > 50:
                return "\n".join(chinese)
        except Exception:
            pass
    return text


def main():
    files = glob.glob(r"D:\project\jiazhi\*.doc")
    if not files:
        print("No doc found", file=sys.stderr)
        sys.exit(1)
    text = extract_doc_text(files[0])
    out = r"D:\project\jiazhi\extracted.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {len(text)} chars to {out}")


if __name__ == "__main__":
    main()
