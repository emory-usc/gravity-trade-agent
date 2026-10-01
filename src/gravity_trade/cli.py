"""Command-line interface.

Commands:
    gravity list                       list tickers with bundled sample data
    gravity analyze TICKER             deterministic six-layer scan + thesis
    gravity agent TICKER               LangGraph agent (LLM if key set, else offline)
    gravity backtest                   run the eval harness over the trade log
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gravity_trade import __version__, data as data_module
from gravity_trade.agent import run_agent
from gravity_trade.models import SignalBundle, TradeThesis
from gravity_trade.scoring import compute_bundle
from gravity_trade.thesis import generate_offline_thesis

app = typer.Typer(
    help="Gravity Trade Agent — six-layer directional equities framework (max pain, beta, GEX, dark pool, sector, term structure).",
    no_args_is_help=True,
)
console = Console()

_DIR_COLOR = {"bull": "green", "bear": "red", "neutral": "yellow"}
_DIR_ARROW = {"bull": "▲", "bear": "▼", "neutral": "—"}


def _render_bundle(bundle: SignalBundle) -> None:
    table = Table(title=f"{bundle.ticker} — six-layer scan", box=box.ROUNDED, show_lines=False)
    table.add_column("Layer", style="bold")
    table.add_column("Dir", justify="center")
    table.add_column("Score", justify="center")
    table.add_column("Conf", justify="right")
    table.add_column("Rationale", overflow="fold", max_width=70)

    for s in bundle.layers:
        c = _DIR_COLOR[s.direction.value]
        table.add_row(
            s.layer,
            f"[{c}]{_DIR_ARROW[s.direction.value]} {s.direction.value}[/]",
            f"{s.score:+d}",
            f"{s.confidence:.2f}",
            s.rationale,
        )
    console.print(table)

    d = bundle.direction.value
    summary = (
        f"[bold {_DIR_COLOR[d]}]{d.upper()}[/]  conviction "
        f"[bold]{bundle.conviction}/6[/]  ({bundle.bullish_count} bull / {bundle.bearish_count} bear)  "
        f"high-conviction: {'[green]YES[/]' if bundle.high_conviction else '[yellow]NO[/]'}"
    )
    console.print(Panel(summary, title="Verdict", border_style=_DIR_COLOR[d]))


def _render_thesis(t: TradeThesis) -> None:
    console.print(Panel(t.thesis, title=f"{t.ticker} thesis ({t.generated_by})", border_style=_DIR_COLOR[t.direction.value]))
    console.print(f"[bold]Entry:[/bold] {t.entry_plan}")
    console.print(f"[bold]Exit:[/bold]  {t.exit_plan}")
    console.print(f"[bold]Risk:[/bold]  {t.risk_notes}")


@app.command()
def list() -> None:
    """List tickers that ship with bundled sample data."""
    tickers = data_module.list_sample_tickers()
    if not tickers:
        console.print("[yellow]No sample data found.[/]")
        return
    console.print("Bundled sample data:")
    for t in tickers:
        console.print(f"  • {t}")


@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Ticker symbol (e.g. NVDA)"),
    threshold: int = typer.Option(None, help="High-conviction threshold (default 4)"),
    as_json: bool = typer.Option(False, "--json", help="Emit the thesis as JSON"),
) -> None:
    """Run the deterministic six-layer scan and emit a trade thesis (no LLM)."""
    data = data_module.load_sample_data(ticker)
    bundle = compute_bundle(ticker.upper(), data, threshold=threshold)
    thesis = generate_offline_thesis(bundle)

    if as_json:
        console.print(json.dumps(json.loads(thesis.model_dump_json()), indent=2))
        return
    _render_bundle(bundle)
    _render_thesis(thesis)


@app.command()
def agent(
    ticker: str = typer.Argument(..., help="Ticker symbol (e.g. NVDA)"),
    as_json: bool = typer.Option(False, "--json", help="Emit the thesis as JSON"),
) -> None:
    """Run the LangGraph agent (LLM narrative if OPENAI_API_KEY is set, else offline fallback)."""
    thesis = run_agent(ticker.upper())
    if as_json:
        console.print(json.dumps(json.loads(thesis.model_dump_json()), indent=2))
        return
    data = data_module.load_sample_data(ticker)
    bundle = compute_bundle(ticker.upper(), data)
    _render_bundle(bundle)
    _render_thesis(thesis)


@app.command()
def backtest() -> None:
    """Run the eval harness over evals/paper_trades.jsonl and print hit rates."""
    from gravity_trade.evals import run_backtest

    report = run_backtest()
    console.print(Panel(f"Backtest over {report['total']} trades (illustrative sample data)", title="Eval"))

    table = Table(box=box.ROUNDED)
    table.add_column("Bucket")
    table.add_column("Trades", justify="right")
    table.add_column("Wins", justify="right")
    table.add_column("Hit rate", justify="right")

    for name, b in report["buckets"].items():
        table.add_row(name, str(b["n"]), str(b["wins"]), f"{b['hit_rate']:.1%}")
    table.add_row("[bold]All[/]", str(report["total"]), str(report["wins"]), f"{report['hit_rate']:.1%}")
    console.print(table)


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"gravity-trade-agent {__version__}")


if __name__ == "__main__":
    app()
