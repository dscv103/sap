from pathlib import Path
import sys
import markdown
from weasyprint import HTML

def md_to_pdf(md_path: Path, pdf_path: Path):
    html_body = markdown.markdown(
        md_path.read_text(encoding="utf-8"),
        extensions=["extra", "toc", "fenced_code"]
    )
    title = md_path.stem
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
html {{ font-size: 12pt; }} body {{ font-family: system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; line-height:1.45; margin:0; }}
main {{ padding: 24mm 18mm; }}
h1,h2,h3 {{ margin: 1.1em 0 .4em; }} pre {{ background:#f6f8fa; border:1px solid #eee; padding:.75em; border-radius:6px; white-space:pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; }} th,td {{ border:1px solid #e5e5e5; padding:.35em .5em; }}
@page {{ size: letter; margin: 18mm 16mm 22mm; @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-size:10pt; color:#666; }} @top-left {{ content: "{title}"; font-size:10pt; color:#666; }} }}
</style></head><body><main>
{html_body}
</main></body></html>"""
    HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(pdf_path))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md2pdf.py <file.md> [<file2.md> ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        md = Path(arg)
        if not md.exists() or md.suffix.lower() != ".md":
            print(f"Skip: {md} (must be an existing .md file)")
            continue
        md_to_pdf(md, md.with_suffix(".pdf"))
        print(f"✓ {md.name} → {md.with_suffix('.pdf').name}")