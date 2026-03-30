import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from src.tusca.utils.config import config
from src.tusca.utils.credits import CreditTracker
from src.tusca.utils.markdown import write_output
from src.tusca.phase1.synthesize import run_phase1, render_onchain_intel

app = typer.Typer(
    name="tusca",
    help="Threat Understanding via Smart Contract Analytics — onchain intelligence for auditors.",
    add_completion=False,
)

console = Console()


def _banner():
    console.print(Panel(
        "[bold cyan]TUSCA[/bold cyan] — Threat Understanding via Smart Contract Analytics\n"
        "[dim]onchain intelligence layer for smart contract auditors[/dim]",
        border_style="cyan",
    ))


def _check_keys(required: list[str]):
    missing = [k for k in required if not getattr(config, k, "")]
    if missing:
        console.print(f"[red]✗ Missing API keys: {', '.join(missing)}[/red]")
        console.print(f"[dim]Add them to your .env file. See .env.example[/dim]")
        raise typer.Exit(1)


@app.command()
def analyze(
    contract_address: str = typer.Argument(
        ..., help="Contract address to analyze"
    ),
    chain: str = typer.Option(
        "ethereum", "--chain", "-c",
        help="Chain: ethereum | arbitrum | optimism | base | polygon"
    ),
    out: str = typer.Option(
        "./tusca-output", "--out", "-o",
        help="Output directory for ONCHAIN-INTEL.md"
    ),
    budget: int = typer.Option(
        500, "--budget", "-b",
        help="Maximum Nansen credits to spend"
    ),
):
    """
    Phase 1 — Run onchain intelligence brief for an audit target.

    Fetches contract identity, TVL, hack history, deployer intelligence,
    smart money signals, and synthesizes via Nansen Agent.

    Output: ONCHAIN-INTEL.md (feeds into PrePosv threat modeling)

    Example:
        tusca analyze 0xabc...def --chain ethereum --out ./output
    """
    _banner()
    _check_keys(["NANSEN_API_KEY", "ETHERSCAN_API_KEY"])

    console.print(f"[bold]Target:[/bold] {contract_address}")
    console.print(f"[bold]Chain:[/bold]  {chain}")
    console.print(f"[bold]Budget:[/bold] {budget} Nansen credits\n")

    tracker = CreditTracker(budget=budget)

    async def _run():
        intel = await run_phase1(contract_address, chain, tracker)
        md = render_onchain_intel(intel, tracker)
        out_path = write_output(f"{out}/ONCHAIN-INTEL.md", md)
        return out_path

    out_path = asyncio.run(_run())

    console.print(Panel(
        f"[bold green]✓ ONCHAIN-INTEL.md written[/bold green]\n"
        f"[dim]{out_path.resolve()}[/dim]\n\n"
        f"[bold]Next step:[/bold] pass this file to PrePosv before running pashov.\n"
        f"PrePosv will use the onchain context to enrich your THREAT-MODEL.md.",
        border_style="green",
        title="Phase 1 Complete",
    ))


@app.command()
def probe(
    contract_address: str = typer.Argument(
        ..., help="Contract address to probe"
    ),
    finding_file: str = typer.Option(
        ..., "--finding-file", "-f",
        help="Path to pashov findings file (x-ray.md or SPECTRA output)"
    ),
    chain: str = typer.Option(
        "ethereum", "--chain", "-c",
        help="Chain: ethereum | arbitrum | optimism | base | polygon"
    ),
    out: str = typer.Option(
        "./tusca-output", "--out", "-o",
        help="Output directory for EXPLOIT-PRECURSOR-REPORT.md"
    ),
    budget: int = typer.Option(
        1000, "--budget", "-b",
        help="Maximum Nansen credits to spend"
    ),
):
    """
    Phase 2 — Run exploit precursor detection against a confirmed finding.

    Parses pashov findings, maps vulnerability class to probe strategy,
    fetches suspicious transactions, decodes calldata, profiles flagged
    senders via Nansen, simulates via Tenderly, synthesizes via Nansen Agent.

    Output: EXPLOIT-PRECURSOR-REPORT.md (feeds into HackenProof triage)

    Example:
        tusca probe 0xabc...def --finding-file ./x-ray.md --chain ethereum
    """
    _banner()
    _check_keys(["NANSEN_API_KEY", "ETHERSCAN_API_KEY"])

    finding_path = Path(finding_file)
    if not finding_path.exists():
        console.print(f"[red]✗ Finding file not found: {finding_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Target:[/bold]  {contract_address}")
    console.print(f"[bold]Chain:[/bold]   {chain}")
    console.print(f"[bold]Findings:[/bold] {finding_file}")
    console.print(f"[bold]Budget:[/bold]  {budget} Nansen credits\n")

    console.print(
        "[yellow]⚠ Phase 2 is under active development. "
        "Run[/yellow] [bold]tusca analyze[/bold] [yellow]first to generate ONCHAIN-INTEL.md[/yellow]"
    )

    # phase 2 orchestration will be wired here
    # for now confirm the finding file is readable
    raw = finding_path.read_text(encoding="utf-8")
    console.print(f"[green]✓ Finding file loaded — {len(raw.splitlines())} lines[/green]")
    console.print(
        Panel(
            "[dim]Phase 2 implementation in progress.\n"
            "Finding parser → probe map → Etherscan → 4byte → "
            "Nansen Profiler → Tenderly → Nansen Agent Expert[/dim]",
            border_style="yellow",
            title="Phase 2 — Coming Next",
        )
    )


@app.command()
def version():
    """Show TUSCA version."""
    console.print("[cyan]TUSCA[/cyan] v0.1.0")


if __name__ == "__main__":
    app()