"""
hipixel-core CLI — Typer + Rich command-line interface.

Commands:
    enhance   Process a single video file with a preset or custom filters
    batch     Process multiple files from a directory
    presets   List / inspect built-in presets
    models    Manage AI model weights (list, download, remove)
    info      Show system info: detected backend, VRAM, platform
    bench     Run a quick benchmark on the active backend

Usage:
    hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4
    hipixel-core enhance input.mp4 --filter nafnet --filter real_esrgan -o out.mp4
    hipixel-core models download RealESRGAN_x2plus
    hipixel-core presets list
    hipixel-core info
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

app = typer.Typer(
    name="hipixel-core",
    help="AI video enhancement engine — HiVideo / HiPixel",
    add_completion=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
)
console = Console()
err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Global callback — verbose / quiet flags
# ---------------------------------------------------------------------------


@app.callback()
def _main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable DEBUG log output from hipixel-core.",
        is_eager=False,
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Suppress all log output except errors.",
        is_eager=False,
    ),
) -> None:
    """hipixel-core — AI video enhancement engine."""
    import logging

    from hipixel_core._log import setup_rich_logging

    if verbose:
        setup_rich_logging(logging.DEBUG)
    elif quiet:
        setup_rich_logging(logging.ERROR)
    else:
        setup_rich_logging(logging.WARNING)


# ---------------------------------------------------------------------------
# enhance
# ---------------------------------------------------------------------------


@app.command()
def enhance(
    input_path: Annotated[
        Path,
        typer.Argument(help="Input video file path"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Output video path"),
    ] = None,
    preset: Annotated[
        str | None,
        typer.Option("--preset", "-p", help="Built-in or custom preset ID / path"),
    ] = None,
    filter_names: Annotated[
        list[str] | None,
        typer.Option("--filter", "-f", help="Filter name (repeatable, ordered)"),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option("--backend", "-b", help="Force backend: coreml|cuda|cpu"),
    ] = None,
    codec: Annotated[
        str,
        typer.Option("--codec", help="Output codec: h264|h265|av1|prores"),
    ] = "h265",
    crf: Annotated[
        int,
        typer.Option("--crf", help="Constant Rate Factor [0-51]"),
    ] = 18,
    no_audio: Annotated[
        bool,
        typer.Option("--no-audio", help="Strip audio from output"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Parse and validate without processing"),
    ] = False,
) -> None:
    """[bold]Enhance[/bold] a video file using AI filters.

    [dim]Examples:[/dim]

      [green]# Use a built-in preset[/green]
      hipixel-core enhance input.mp4 --preset old-film-revival -o output.mp4

      [green]# Compose filters manually[/green]
      hipixel-core enhance input.mp4 --filter nafnet --filter real_esrgan -o out.mp4
    """
    from hipixel_core.backends.selector import select_backend
    from hipixel_core.pipeline import Pipeline
    from hipixel_core.presets.manager import PresetManager
    from hipixel_core.types import OutputSpec, ProgressEvent
    from hipixel_core.video.decoder import probe

    # ── Resolve output path ──────────────────────────────────────────────
    if output is None:
        stem = input_path.stem
        output = input_path.parent / f"{stem}_enhanced.mp4"

    if not input_path.exists():
        err_console.print(f"Input file not found: {input_path}")
        raise typer.Exit(1)

    # ── Load preset or build ad-hoc pipeline ────────────────────────────
    if preset and filter_names:
        err_console.print("--preset and --filter are mutually exclusive.")
        raise typer.Exit(1)

    if not preset and not filter_names:
        err_console.print("Specify --preset or at least one --filter.")
        raise typer.Exit(1)

    console.rule("[bold cyan]hipixel-core[/bold cyan]")

    with console.status("[bold]Probing input file…"):
        meta = probe(str(input_path))

    console.print(
        f"[green]✓[/green] Input  : [cyan]{input_path}[/cyan] "
        f"([white]{meta.width}x{meta.height}[/white] @ "
        f"[white]{meta.fps:.2f}[/white] fps, "
        f"[white]{meta.frame_count}[/white] frames)"
    )

    if preset:
        pm = PresetManager.load(preset)
        pipeline = Pipeline.from_preset(PresetManager.as_pipeline_dict(pm))
        console.print(f"[green]✓[/green] Preset : [magenta]{pm.name or pm.id}[/magenta]")
    else:
        assert filter_names is not None
        from hipixel_core.filters import get_filter

        filters = [get_filter(n) for n in filter_names]
        pipeline = Pipeline(filters=filters)  # type: ignore[arg-type]
        console.print(f"[green]✓[/green] Filters: [magenta]{' → '.join(filter_names)}[/magenta]")

    spec = OutputSpec(
        path=str(output),
        codec=codec,
        crf=crf,
        audio_copy=not no_audio,
    )

    if dry_run:
        console.print("[yellow]Dry run complete — no processing performed.[/yellow]")
        return

    # ── Select backend ───────────────────────────────────────────────────
    with console.status("[bold]Selecting inference backend…"):
        be = select_backend(force=backend)
        be.initialize()

    console.print(
        f"[green]✓[/green] Backend: [blue]{be.device_info.backend_name}[/blue] "
        f"({be.device_info.device_name})"
    )

    # ── Set up filters (load models + CoreML warmup) ─────────────────────
    # This phase can take many minutes on first run while CoreML compiles
    # models from ONNX.  Show a dedicated spinner so the user can see which
    # filter is being initialised rather than a frozen progress bar.
    n = len(pipeline._filters)
    try:
        with console.status("", spinner="dots") as status:
            _setup_idx = [0]

            def _setup_cb(filter_name: str) -> None:
                _setup_idx[0] += 1
                status.update(
                    f"[bold]Setting up [cyan]{filter_name}[/cyan]"
                    f"[dim] ({_setup_idx[0]}/{n})"
                    " — first run compiles CoreML models, may take several minutes[/dim]"
                )
            pipeline.setup(be, status_cb=_setup_cb)
    except Exception as exc:
        err_console.print(f"Filter setup failed: {exc}")
        be.shutdown()
        raise typer.Exit(1)

    # ── Run with progress bar ────────────────────────────────────────────
    start = time.monotonic()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Enhancing…", total=meta.frame_count)

            def cb(event: ProgressEvent) -> None:
                progress.update(
                    task,
                    completed=event.frame_index,
                    description=(
                        f"[cyan]{event.fps_avg:.1f} fps[/cyan]"
                    ),
                )

            result = pipeline.run(
                source=meta,
                output_spec=spec,
                backend=be,
                progress_cb=cb,
            )
    finally:
        pipeline.teardown(be)
        be.shutdown()
    # ── Result summary ───────────────────────────────────────────────────
    elapsed = time.monotonic() - start
    if result.success:
        console.print(
            f"\n[bold green]✓ Done![/bold green] "
            f"Output: [cyan]{output}[/cyan]\n"
            f"  Frames : {result.frames_processed}\n"
            f"  Time   : {elapsed:.1f}s\n"
            f"  Speed  : [white]{result.avg_fps:.1f}[/white] fps avg"
        )
    else:
        err_console.print(f"Processing failed: {result.error}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------


@app.command()
def batch(
    input_dir: Annotated[Path, typer.Argument(help="Directory of input videos")],
    output_dir: Annotated[Path, typer.Argument(help="Directory for enhanced output")],
    preset: Annotated[str, typer.Option("--preset", "-p", help="Preset ID")],
    glob: Annotated[
        str,
        typer.Option("--glob", "-g", help="File glob pattern"),
    ] = "*.mp4",
    backend: Annotated[str | None, typer.Option("--backend")] = None,
    workers: Annotated[int, typer.Option("--workers", "-w", help="Parallel jobs")] = 1,
) -> None:
    """Batch-enhance all matching videos in a directory."""
    if not input_dir.is_dir():
        err_console.print(f"Input directory not found: {input_dir}")
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.glob(glob))

    if not files:
        console.print(f"[yellow]No files matching '{glob}' in {input_dir}[/yellow]")
        return

    console.print(
        f"[bold]Batch processing[/bold] {len(files)} files with preset [magenta]{preset}[/magenta]"
    )

    success = failed = 0
    for i, src in enumerate(files, 1):
        dst = output_dir / src.name
        console.print(f"[dim]({i}/{len(files)})[/dim] {src.name}")
        # Invoke enhance programmatically
        try:
            from hipixel_core.backends.selector import select_backend
            from hipixel_core.pipeline import Pipeline
            from hipixel_core.presets.manager import PresetManager
            from hipixel_core.types import OutputSpec
            from hipixel_core.video.decoder import probe

            meta = probe(str(src))
            pm = PresetManager.load(preset)
            pipeline = Pipeline.from_preset(PresetManager.as_pipeline_dict(pm))
            spec = OutputSpec(path=str(dst))
            be = select_backend(force=backend)
            be.initialize()
            result = pipeline.run(source=meta, output_spec=spec, backend=be)
            be.shutdown()
            if result.success:
                success += 1
                console.print(f"  [green]✓[/green] {dst.name}")
            else:
                failed += 1
                console.print(f"  [red]✗[/red] {result.error}")
        except Exception as exc:
            failed += 1
            console.print(f"  [red]✗[/red] {exc}")

    console.print(
        f"\n[bold]Done.[/bold] [green]{success} succeeded[/green] / [red]{failed} failed[/red]"
    )


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

presets_app = typer.Typer(help="Manage enhancement presets")
app.add_typer(presets_app, name="presets")


@presets_app.command("list")
def presets_list() -> None:
    """List all built-in presets."""
    from hipixel_core.presets.manager import PresetManager

    table = Table("ID", "Name", "Filters", "Min VRAM", title="Built-in Presets")
    for preset_id in PresetManager.list_builtin():
        try:
            p = PresetManager.load(preset_id)
            filters_str = " → ".join(s.filter for s in p.filters)
            vram = f"{p.requirements.min_vram_mb} MB" if p.requirements.min_vram_mb else "CPU"
            table.add_row(p.id, p.name or "", filters_str, vram)
        except Exception as exc:
            table.add_row(preset_id, "[red]error[/red]", str(exc), "")
    console.print(table)


@presets_app.command("show")
def presets_show(
    preset_id: Annotated[str, typer.Argument(help="Preset ID to inspect")],
) -> None:
    """Show detailed information about a preset."""
    import json

    from hipixel_core.presets.manager import PresetManager

    p = PresetManager.load(preset_id)
    console.print_json(json.dumps(p.model_dump(by_alias=False), indent=2))


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

models_app = typer.Typer(help="Manage AI model weights")
app.add_typer(models_app, name="models")


@models_app.command("list")
def models_list() -> None:
    """List all models in the registry."""
    from hipixel_core.models.manager import ModelManager

    cached = set(ModelManager.list_cached())
    table = Table("Model", "Type", "Scale", "Cached", title="Model Registry")
    for entry in ModelManager.list_registry():
        name = entry.get("filename", "").replace(".onnx", "")
        status = "[green]✓ cached[/green]" if name in cached else "[dim]not cached[/dim]"
        table.add_row(
            name,
            entry.get("type", "?"),
            str(entry.get("scale", "?")),
            status,
        )
    console.print(table)


@models_app.command("download")
def models_download(
    model_name: Annotated[str, typer.Argument(help="Model name to download")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Re-download even if cached"),
    ] = False,
) -> None:
    """Download a model to the local cache."""
    from hipixel_core.models.manager import ModelManager

    path = ModelManager.download(model_name, force=force)
    console.print(f"[green]✓[/green] Model cached at: [cyan]{path}[/cyan]")


@models_app.command("remove")
def models_remove(
    model_name: Annotated[str, typer.Argument(help="Model name to remove")],
) -> None:
    """Remove a cached model from disk."""
    from hipixel_core.models.manager import ModelManager

    removed = ModelManager.remove(model_name)
    if removed:
        console.print(f"[green]✓[/green] Removed: {model_name}")
    else:
        console.print(f"[yellow]Not cached: {model_name}[/yellow]")


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@app.command()
def info() -> None:
    """Show system information: platform, backend, VRAM."""
    import platform as _platform

    from hipixel_core import __version__
    from hipixel_core.backends.selector import list_available_backends, select_backend

    table = Table("Property", "Value", title="hipixel-core System Info")
    table.add_row("Version", __version__)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Platform", _platform.platform())
    table.add_row("Machine", _platform.machine())

    available = list_available_backends()
    table.add_row("Available backends", ", ".join(available))

    try:
        be = select_backend()
        be.initialize()
        di = be.device_info
        table.add_row("Active backend", di.backend_name)
        table.add_row("Device", di.device_name)
        table.add_row(
            "VRAM",
            f"{di.total_vram_mb} MB total / {di.available_vram_mb} MB free"
            if di.has_gpu
            else "N/A (CPU)",
        )
        be.shutdown()
    except Exception as exc:
        table.add_row("Active backend", f"[red]error: {exc}[/red]")

    console.print(table)


# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------


@app.command()
def bench(
    backend: Annotated[str | None, typer.Option("--backend", "-b", help="Force a specific backend (cpu/coreml/cuda)")] = None,
    frames: Annotated[int, typer.Option("--frames", help="Number of timed process_frame calls per filter")] = 30,
    resolution: Annotated[
        str,
        typer.Option("--resolution", "-r", help="Resolution string: '1280x720', '720p', '1080p', '4k'"),
    ] = "1280x720",
    filter_name: Annotated[
        str | None,
        typer.Option("--filter", "-f", help="Single filter to benchmark (e.g. cas, aces)"),
    ] = None,
    all_filters: Annotated[
        bool,
        typer.Option("--all-filters", "-a", help="Benchmark all CPU-capable filters (cas + aces)"),
    ] = False,
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Save report to this path (.json or .md)"),
    ] = None,
    fmt: Annotated[
        str | None,
        typer.Option("--format", help="Output format: json, md, table (default: table)"),
    ] = None,
) -> None:
    """Run a performance benchmark on the active backend.

    By default benchmarks CAS (CPU-only, no model needed).  Use --all-filters
    to benchmark every CPU-capable filter, or --filter NAME to pick one.
    Results can be saved to a file with --output.

    Examples::

        hipixel-core bench
        hipixel-core bench --all-filters --output results.md
        hipixel-core bench --filter aces --resolution 1080p --frames 60
        hipixel-core bench --all-filters --format json
    """
    from hipixel_core.backends.selector import select_backend
    from hipixel_core.bench.runner import BenchmarkReport, BenchmarkRunner, CPU_ONLY_FILTERS
    from hipixel_core.bench.synthetic import parse_resolution

    # Validate resolution early for a clear error message
    try:
        w, h = parse_resolution(resolution)
        canonical = f"{w}x{h}"
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    console.rule("[bold cyan]Benchmark[/bold cyan]")

    be = select_backend(force=backend)
    be.initialize()
    di = be.device_info

    console.print(
        f"Backend  : [blue]{di.backend_name}[/blue]  "
        f"Device   : [blue]{di.device_name}[/blue]\n"
        f"Resolution: [white]{canonical}[/white]  "
        f"Frames: [white]{frames}[/white]"
    )

    runner = BenchmarkRunner(be)

    # --- decide which filters to run ---
    if all_filters:
        targets = list(CPU_ONLY_FILTERS)
    elif filter_name:
        targets = [filter_name]
    else:
        targets = ["cas"]

    results = []
    for name in targets:
        with Progress(
            SpinnerColumn(),
            TextColumn(f"  [cyan]{name}[/cyan] {{task.description}}"),
            console=console,
        ) as prog:
            prog.add_task(f"({canonical}, {frames} frames)…")
            result = runner.run_filter(name, resolution=canonical, frames=frames)
        results.append(result)
        console.print(
            f"  [green]✓[/green] [cyan]{name:<12}[/cyan]"
            f"  avg [white]{result.avg_fps:.1f}[/white] fps"
            f"  p50 [white]{result.p50_ms:.2f}[/white] ms"
            f"  p95 [white]{result.p95_ms:.2f}[/white] ms"
        )

    report = BenchmarkReport(
        results=results,
        device_name=di.device_name,
        backend_name=di.backend_name,
    )

    be.shutdown()

    # --- terminal output ---
    effective_fmt = fmt or ("table" if output is None else None)
    if effective_fmt == "json":
        console.print(report.to_json())
    elif effective_fmt == "md":
        console.print(report.to_markdown())
    else:
        # Rich table (default terminal view)
        table = Table(title="Benchmark Results", show_header=True, header_style="bold magenta")
        table.add_column("Filter", style="cyan")
        table.add_column("Resolution")
        table.add_column("FPS avg", justify="right")
        table.add_column("FPS min", justify="right")
        table.add_column("FPS max", justify="right")
        table.add_column("p50 ms", justify="right")
        table.add_column("p95 ms", justify="right")
        for r in report.results:
            table.add_row(
                r.filter_name,
                r.resolution,
                f"{r.avg_fps:.1f}",
                f"{r.min_fps:.1f}",
                f"{r.max_fps:.1f}",
                f"{r.p50_ms:.2f}",
                f"{r.p95_ms:.2f}",
            )
        console.print(table)

    # --- optional file export ---
    if output:

        report.save(Path(output), fmt=fmt)
        console.print(f"\n[green]Report saved →[/green] {output}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
