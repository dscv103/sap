#!/usr/bin/env python3

# /// script

# requires-python = “>=3.13”

# dependencies = [

# “polars>=1.0”,

# “pyyaml>=6.0”,

# “cyclopts>=3.0”,

# “rich>=13.0”,

# “structlog>=24.0”,

# ]

# ///

# “””
Merchant Name Normalizer

Applies YAML-defined rules to normalize merchant name descriptors at scale.

Outputs per row:

- original_name       : raw input descriptor
- processor_prefixes  : comma-separated list of stripped wrapper prefixes
- cleaned_name        : descriptor after prefix stripping
- canonical_name      : matched PARENT_BRAND label (empty if none)

Usage:
uv run merchant_normalizer.py transactions.csv output.csv
uv run merchant_normalizer.py transactions.csv output.csv –column MERCHANT_NAME
uv run merchant_normalizer.py transactions.csv output.csv –workers 16
“””

import multiprocessing as mp
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cyclopts
import polars as pl
import structlog
import yaml
from rich.console import Console
from rich.progress import (
BarColumn,
MofNCompleteColumn,
Progress,
SpinnerColumn,
TaskProgressColumn,
TextColumn,
TimeElapsedColumn,
TimeRemainingColumn,
)

log = structlog.get_logger()
console = Console(stderr=True)

app = cyclopts.App(
name=“merchant-normalizer”,
help=“Apply merchant rules YAML to normalize 8M+ descriptor rows.”,
)

# —————————————————————————

# Data models

# —————————————————————————

@dataclass(slots=True)
class RawRule:
rule_set: str
match_type: str
pattern: str
label: str
priority: int
enabled: bool
notes: str = “”

@dataclass(slots=True)
class CompiledRule:
“”“Compiled, ready-to-match rule.”””
rule_set: str
label: str
priority: int
match_type: str
# One of these will be set depending on match_type
regex: re.Pattern[str] | None = field(default=None)
exact: str | None = field(default=None)

```
def matches(self, text: str) -> bool:
    if self.match_type == "exact":
        return text == self.exact
    return bool(self.regex and self.regex.search(text))

def strip_prefix(self, text: str) -> tuple[str, str] | None:
    """For WRAPPER_PREFIX rules: returns (stripped_text, matched_prefix) or None."""
    if self.regex is None:
        return None
    m = self.regex.match(text)
    if not m:
        return None
    matched = m.group(0)
    remainder = text[len(matched):]
    return remainder.strip(), matched.rstrip()
```

@dataclass(slots=True, frozen=True)
class MatchResult:
original_name: str
processor_prefixes: str   # comma-separated
cleaned_name: str
canonical_name: str

# —————————————————————————

# Rule loading

# —————————————————————————

def load_rules(yaml_path: Path) -> tuple[list[CompiledRule], list[CompiledRule]]:
“”“Load and compile rules. Returns (prefix_rules, brand_rules) sorted by priority.”””
raw = yaml.safe_load(yaml_path.read_text())
prefix_rules: list[CompiledRule] = []
brand_rules: list[CompiledRule] = []

```
for entry in raw.get("rules", []):
    raw_rule = RawRule(
        rule_set=entry.get("rule_set", ""),
        match_type=entry.get("match_type", "regex"),
        pattern=entry.get("pattern", ""),
        label=entry.get("label", ""),
        priority=entry.get("priority", 999),
        enabled=entry.get("enabled", True),
        notes=entry.get("notes", ""),
    )
    if not raw_rule.enabled:
        continue

    compiled = _compile_rule(raw_rule)
    if compiled is None:
        continue

    if raw_rule.rule_set == "WRAPPER_PREFIX":
        prefix_rules.append(compiled)
    elif raw_rule.rule_set == "PARENT_BRAND":
        brand_rules.append(compiled)

prefix_rules.sort(key=lambda r: r.priority)
brand_rules.sort(key=lambda r: r.priority)
return prefix_rules, brand_rules
```

def _compile_rule(raw: RawRule) -> CompiledRule | None:
if raw.match_type == “exact”:
return CompiledRule(
rule_set=raw.rule_set,
label=raw.label,
priority=raw.priority,
match_type=“exact”,
exact=raw.pattern,
)
try:
compiled_re = re.compile(raw.pattern, re.IGNORECASE)
return CompiledRule(
rule_set=raw.rule_set,
label=raw.label,
priority=raw.priority,
match_type=“regex”,
regex=compiled_re,
)
except re.error as exc:
log.warning(“skipping_bad_pattern”, pattern=raw.pattern, error=str(exc))
return None

# —————————————————————————

# Per-row matching logic

# —————————————————————————

def normalize_one(
name: str,
prefix_rules: list[CompiledRule],
brand_rules: list[CompiledRule],
) -> MatchResult:
“”“Apply rules to a single merchant descriptor.”””
original = name

```
# Phase 1: Try PARENT_BRAND on original name first.
# (Rules like TST*FIREHOUSE SUBS embed the prefix in the pattern.)
canonical = _match_brand(original, brand_rules)

# Phase 2: Strip WRAPPER_PREFIX(es) to build cleaned_name regardless.
cleaned, prefixes = _strip_prefixes(original, prefix_rules)

# Phase 3: If no brand match on original, try again on cleaned name.
if not canonical and cleaned != original:
    canonical = _match_brand(cleaned, brand_rules)

return MatchResult(
    original_name=original,
    processor_prefixes=", ".join(prefixes) if prefixes else "",
    cleaned_name=cleaned,
    canonical_name=canonical,
)
```

def _match_brand(name: str, brand_rules: list[CompiledRule]) -> str:
“”“Return first matching PARENT_BRAND label, or empty string.”””
for rule in brand_rules:
if rule.matches(name):
return rule.label
return “”

def _strip_prefixes(
name: str,
prefix_rules: list[CompiledRule],
) -> tuple[str, list[str]]:
“””
Iteratively strip WRAPPER_PREFIX matches from the beginning of name.
Returns (cleaned_name, list_of_stripped_prefixes).
Multiple stacked prefixes are handled (e.g. rare double-wrapped descriptors).
“””
stripped: list[str] = []
current = name
max_passes = 5  # guard against pathological cycles

```
for _ in range(max_passes):
    found = False
    for rule in prefix_rules:
        result = rule.strip_prefix(current)
        if result is not None:
            remainder, prefix = result
            if remainder:  # don't strip if nothing left
                stripped.append(prefix)
                current = remainder
                found = True
                break  # restart from top of prefix_rules
    if not found:
        break

return current, stripped
```

# —————————————————————————

# Multiprocessing worker

# —————————————————————————

# Module-level globals set by pool initializer — avoids re-pickling rules per chunk

_prefix_rules: list[CompiledRule] = []
_brand_rules: list[CompiledRule] = []

def _worker_init(prefix_rules: list[CompiledRule], brand_rules: list[CompiledRule]) -> None:
global _prefix_rules, _brand_rules
_prefix_rules = prefix_rules
_brand_rules = brand_rules

def _process_chunk(names: list[str]) -> list[tuple[str, str, str, str]]:
“”“Process a chunk of names. Returns list of (original, prefixes, cleaned, canonical).”””
results = []
for name in names:
r = normalize_one(name, _prefix_rules, _brand_rules)
results.append((r.original_name, r.processor_prefixes, r.cleaned_name, r.canonical_name))
return results

# —————————————————————————

# CLI entry point

# —————————————————————————

@app.default
def main(
input_csv: Path,
output_csv: Path,
*,
column: str = “merchant_name”,
rules: Path = Path(“merchant_rules.yml”),
workers: int = 0,
chunk_size: int = 25_000,
delimiter: str = “,”,
) -> None:
“””
Normalize merchant name descriptors using YAML rule definitions.

```
Parameters
----------
input_csv
    Path to the input CSV file.
output_csv
    Path to write the normalized output CSV.
column
    Name of the merchant name column in input_csv.
rules
    Path to the merchant_rules.yml file.
workers
    Number of worker processes (0 = auto-detect CPU count).
chunk_size
    Rows per worker task (tune for memory/speed balance).
delimiter
    CSV delimiter character.
"""
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)

# Validate inputs
if not input_csv.exists():
    console.print(f"[red]Error:[/red] Input file not found: {input_csv}")
    sys.exit(1)
if not rules.exists():
    console.print(f"[red]Error:[/red] Rules file not found: {rules}")
    sys.exit(1)

n_workers = workers if workers > 0 else mp.cpu_count()

console.print(f"\n[bold cyan]Merchant Normalizer[/bold cyan]")
console.print(f"  Input   : {input_csv}")
console.print(f"  Output  : {output_csv}")
console.print(f"  Column  : {column}")
console.print(f"  Rules   : {rules}")
console.print(f"  Workers : {n_workers}")
console.print(f"  Chunk   : {chunk_size:,}\n")

# Load rules
console.print("[dim]Loading and compiling rules...[/dim]")
prefix_rules, brand_rules = load_rules(rules)
console.print(
    f"  [green]✓[/green] {len(prefix_rules)} prefix rules, "
    f"{len(brand_rules)} brand rules compiled\n"
)

# Read input
console.print("[dim]Reading input CSV...[/dim]")
df = pl.read_csv(
    input_csv,
    separator=delimiter,
    infer_schema_length=0,          # all strings — preserve original values
    null_values=["", "NULL", "null", "NA", "N/A"],
    truncate_ragged_lines=True,
)

if column not in df.columns:
    available = ", ".join(df.columns[:10])
    console.print(
        f"[red]Error:[/red] Column '{column}' not found.\n"
        f"Available columns: {available}"
    )
    sys.exit(1)

total_rows = len(df)
console.print(f"  [green]✓[/green] {total_rows:,} rows loaded\n")

# Extract merchant names; replace nulls with empty string
names: list[str] = (
    df[column]
    .fill_null("")
    .to_list()
)

# Build chunks
chunks = [
    names[i : i + chunk_size]
    for i in range(0, len(names), chunk_size)
]
n_chunks = len(chunks)

# Process with multiprocessing pool
all_results: list[tuple[str, str, str, str]] = []

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    console=console,
) as progress:
    task = progress.add_task("Normalizing merchants…", total=n_chunks)

    with mp.Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(prefix_rules, brand_rules),
    ) as pool:
        for chunk_result in pool.imap(_process_chunk, chunks, chunksize=1):
            all_results.extend(chunk_result)
            progress.advance(task)

# Build output dataframe
console.print("\n[dim]Writing output...[/dim]")
originals, prefixes_col, cleaned_col, canonical_col = zip(*all_results, strict=True)

output_df = pl.DataFrame(
    {
        "original_name": list(originals),
        "processor_prefixes": list(prefixes_col),
        "cleaned_name": list(cleaned_col),
        "canonical_name": list(canonical_col),
    }
)

output_csv.parent.mkdir(parents=True, exist_ok=True)
output_df.write_csv(output_csv)

# Summary stats
n_with_prefix = sum(1 for p in prefixes_col if p)
n_canonical = sum(1 for c in canonical_col if c)
n_no_match = total_rows - n_canonical

console.print(f"\n[bold green]Done![/bold green]")
console.print(f"  Total rows      : {total_rows:,}")
console.print(f"  Prefix stripped : {n_with_prefix:,} ({n_with_prefix/total_rows*100:.1f}%)")
console.print(f"  Brand matched   : {n_canonical:,} ({n_canonical/total_rows*100:.1f}%)")
console.print(f"  No match        : {n_no_match:,} ({n_no_match/total_rows*100:.1f}%)")
console.print(f"\n  Output → [cyan]{output_csv}[/cyan]")
```

if **name** == “**main**”:
app()