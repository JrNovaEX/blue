from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()


def die(msg: str) -> None:
    """Print an error and exit the whole process. Only for one-shot CLI commands."""
    console.print(f"[bold red]✗[/] {msg}")
    raise SystemExit(1)


def err(msg: str) -> None:
    """Print an error without exiting. For the interactive menu loop."""
    console.print(f"[bold red]✗[/] {msg}")


def ok(msg: str) -> None:
    console.print(f"[bold green]✓[/] {msg}")


def table_from_rows(title: str, rows: list[dict], columns: list[str]) -> Table:
    t = Table(title=title, show_lines=False)
    for col in columns:
        t.add_column(col)
    for row in rows:
        t.add_row(*[str(row.get(c, "")) for c in columns])
    return t
