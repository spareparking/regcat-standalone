"""Command-line interface for the multi-doc regcat catalog."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# Force UTF-8 stdout on Windows so non-ASCII characters in log messages
# (e.g. ≤, §, §, smart quotes) don't crash the print() call when the
# default code page is cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import click

from .orchestrator import run_pipeline
from .registry import (
    DocMeta, DocStats, DocStatus, DocumentType, CitationFormat,
    Jurisdiction, Subsystem,
    all_docs, doc_dir, doc_id_for, load_meta, save_meta,
    sha256_of, slugify, write_registry, write_registry_md,
)


@click.group()
def main():
    """regcat — regulatory requirement extraction with provable coverage.

    Multi-document catalog. Each PDF is registered as a doc with a stable
    doc_id of the form <jurisdiction>/<short_id> (e.g. `fda/21-cfr-part-11`).
    """


# ---------------------------------------------------------------------------
# ingest — register a new PDF
# ---------------------------------------------------------------------------

@main.command("ingest")
@click.argument("pdf", type=click.Path(exists=True, path_type=Path))
@click.option("--jurisdiction", "-j", type=click.Choice([j.value for j in Jurisdiction]),
              required=True, help="Top-level regulatory authority.")
@click.option("--id", "short_id", type=str, required=True,
              help="Short slug-style id, unique within the jurisdiction (e.g. 21-cfr-part-11).")
@click.option("--title", type=str, required=True, help="Human-readable title.")
@click.option("--type", "doc_type", type=click.Choice([t.value for t in DocumentType]),
              default=DocumentType.REGULATION.value)
@click.option("--citation-format", type=click.Choice([c.value for c in CitationFormat]),
              default=CitationFormat.GENERIC.value)
@click.option("--version", type=str, default=None)
@click.option("--effective-date", type=str, default=None)
@click.option("--source-url", type=str, default=None)
@click.option("--applies-to", multiple=True, type=click.Choice([s.value for s in Subsystem]),
              help="CTMS subsystems this document applies to. Repeat for multiple.")
@click.option("--supersedes", type=str, default=None, help="doc_id this version supersedes.")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--force", is_flag=True, help="Overwrite an existing doc directory.")
def cmd_ingest(pdf, jurisdiction, short_id, title, doc_type, citation_format,
               version, effective_date, source_url, applies_to, supersedes, root, force):
    """Register a PDF as a new document in the catalog."""
    j = Jurisdiction(jurisdiction)
    short_id = slugify(short_id)
    did = doc_id_for(j, short_id)
    target = doc_dir(root, did)
    if target.exists() and not force:
        click.echo(f"ERROR: {target} already exists. Use --force to overwrite.", err=True)
        sys.exit(2)
    target.mkdir(parents=True, exist_ok=True)
    dest_pdf = target / "source.pdf"
    shutil.copy2(pdf, dest_pdf)
    sha = sha256_of(dest_pdf)

    meta = DocMeta(
        doc_id=did,
        jurisdiction=j,
        short_id=short_id,
        title=title,
        document_type=DocumentType(doc_type),
        citation_format=CitationFormat(citation_format),
        version=version,
        effective_date=effective_date,
        source_url=source_url,
        applies_to=[Subsystem(s) for s in applies_to],
        status=DocStatus.REGISTERED,
        pdf_sha256=sha,
        ingested_at=date.today().isoformat(),
        supersedes=supersedes,
    )
    save_meta(root, meta)
    write_registry(root)
    write_registry_md(root)
    click.echo(f"Ingested {did}  pdf_sha256={sha[:12]}  -> {target}")


# ---------------------------------------------------------------------------
# run — process a single document
# ---------------------------------------------------------------------------

@main.command("run")
@click.option("--doc", "doc_id", type=str, required=True,
              help="doc_id to process, e.g. fda/21-cfr-part-11")
@click.option("--mode", type=click.Choice(["auto", "live", "claude-code", "openai", "mock"]),
              default="auto",
              help="LLM mode. 'auto' picks Anthropic, then OpenAI, then mock.")
@click.option("--model", type=str, default=None,
              help="Override the backend model, e.g. gpt-4.1 or claude-opus-4-7.")
@click.option("--stages", default=None, help="Comma-separated stages to run (default: all).")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_run(doc_id, mode, model, stages, root):
    """Run the pipeline end-to-end on one doc."""
    stage_list = stages.split(",") if stages else None
    try:
        meta = load_meta(root, doc_id)
    except FileNotFoundError:
        click.echo(f"ERROR: doc {doc_id} not registered. Run `regcat ingest` first.", err=True)
        sys.exit(2)

    # Mark in-progress
    meta.status = DocStatus.IN_PROGRESS
    save_meta(root, meta)

    try:
        ctx = run_pipeline(doc_id, root, mode=mode, model=model, stages=stage_list)
    except Exception as e:
        meta.status = DocStatus.NEEDS_REVIEW
        save_meta(root, meta)
        click.echo(f"\nFAILED: {e}", err=True)
        sys.exit(2)

    # Refresh stats from coverage report + relationship validation, mark completed
    cov_path = ctx.paths.audit_dir / "coverage_report.json"
    if cov_path.exists():
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        rels_path = ctx.paths.catalog_dir / "relationships.jsonl"
        rel_count = 0
        if rels_path.exists():
            rel_count = sum(1 for line in rels_path.read_text(encoding="utf-8").splitlines() if line.strip())
        meta.stats = DocStats(
            spans=cov.get("span_count", 0),
            requirements=cov.get("requirements_extracted", 0),
            relationships=rel_count,
            coverage_pct=cov.get("coverage_pct", 0.0),
        )
        meta.canonical_sha256 = cov.get("canonical_source_sha256", meta.canonical_sha256)
        from .agent_packets import unresolved_catalog_counts
        unresolved = unresolved_catalog_counts(ctx.paths)
        has_unresolved = any(unresolved.values())
        meta.status = DocStatus.COMPLETED if cov.get("passed") and not has_unresolved else DocStatus.NEEDS_REVIEW
        meta.completed_at = date.today().isoformat()
        save_meta(root, meta)
        write_registry(root)
        write_registry_md(root)
        _publish_review_artifacts(root, doc_id)
        click.echo(f"\n{doc_id}: coverage={cov['coverage_pct']:.2f}%  "
                   f"reqs={cov['requirements_extracted']}  status={meta.status.value}")
        if has_unresolved:
            detail = ", ".join(f"{k}={v}" for k, v in unresolved.items() if v)
            click.echo(f"unresolved catalog ambiguity remains: {detail}", err=True)


# ---------------------------------------------------------------------------
# ls — list documents
# ---------------------------------------------------------------------------

@main.command("ls")
@click.option("--jurisdiction", "-j", type=str, default=None)
@click.option("--status", type=str, default=None)
@click.option("--tag", type=str, default=None,
              help="Filter by applies_to tag (e.g. edc, iwrs, ecoa).")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_ls(jurisdiction, status, tag, root):
    """List registered documents."""
    docs = all_docs(root)
    if jurisdiction:
        docs = [d for d in docs if d.jurisdiction.value == jurisdiction]
    if status:
        docs = [d for d in docs if d.status.value == status]
    if tag:
        docs = [d for d in docs if any(t.value == tag for t in d.applies_to)]
    if not docs:
        click.echo("(no documents)")
        return
    click.echo(f"{'doc_id':40s} {'status':14s} {'reqs':>6s}  {'cov':>7s}  title")
    click.echo("-" * 100)
    for d in sorted(docs, key=lambda x: x.doc_id):
        click.echo(f"{d.doc_id:40s} {d.status.value:14s} "
                   f"{d.stats.requirements:>6d}  {d.stats.coverage_pct:>6.2f}%  {d.title}")


# ---------------------------------------------------------------------------
# status — detail for one doc
# ---------------------------------------------------------------------------

@main.command("status")
@click.argument("doc_id", type=str)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_status(doc_id, root):
    try:
        meta = load_meta(root, doc_id)
    except FileNotFoundError:
        click.echo(f"ERROR: doc {doc_id} not registered.", err=True)
        sys.exit(2)
    click.echo(meta.model_dump_json(indent=2))


# ---------------------------------------------------------------------------
# index — rebuild registry.json + registry.md
# ---------------------------------------------------------------------------

@main.command("index")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_index(root):
    """Rebuild docs/registry.json and docs/registry.md from per-doc meta.json files."""
    p1 = write_registry(root)
    p2 = write_registry_md(root)
    click.echo(f"wrote {p1}")
    click.echo(f"wrote {p2}")


# ---------------------------------------------------------------------------
# report — print coverage report for one doc
# ---------------------------------------------------------------------------

@main.command("report")
@click.argument("doc_id", type=str)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_report(doc_id, root):
    """Print the coverage report for one doc."""
    from .registry import doc_dir as resolve_doc_dir
    cov_path = resolve_doc_dir(root, doc_id) / "audit" / "coverage_report.json"
    if not cov_path.exists():
        click.echo(f"no coverage report at {cov_path}", err=True)
        sys.exit(1)
    click.echo(cov_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# agent — subscription-agent packet workflow (Codex / Claude in workspace)
# ---------------------------------------------------------------------------

@main.group("agent")
def agent_group():
    """Create, validate, and merge Codex/Claude agent work packets.

    This workflow does not call an LLM API. It exports bounded JSONL packets for
    workspace agents to complete, then refuses to merge anything until strict
    validation passes.
    """


@agent_group.command("status")
@click.argument("doc_id", type=str)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_status(doc_id, root):
    from .agent_packets import status
    click.echo(json.dumps(status(root, doc_id), indent=2))


@agent_group.command("export")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--stage", type=click.Choice(["classify", "decompose", "embedded", "relate"]),
              required=True)
@click.option("--limit", type=int, default=50, show_default=True)
@click.option("--batch-id", type=str, default=None)
@click.option("--force", is_flag=True, help="Overwrite an existing packet directory.")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_export(doc_id, stage, limit, batch_id, force, root):
    """Export the next bounded packet for a subscription agent to complete."""
    from .agent_packets import export_packet
    out = export_packet(root, doc_id, stage, limit=limit, batch_id=batch_id, force=force)
    click.echo(f"wrote {out}")
    click.echo(f"agent instructions: {out / 'instructions.md'}")


@agent_group.command("validate")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--stage", type=click.Choice(["classify", "decompose", "embedded", "relate"]),
              required=True)
@click.option("--batch-id", type=str, required=True)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_validate(doc_id, stage, batch_id, root):
    """Validate a completed packet without merging it."""
    from .agent_packets import validate_packet
    report = validate_packet(root, doc_id, stage, batch_id)
    click.echo(json.dumps(report, indent=2))
    if not report["passed"]:
        sys.exit(2)


@agent_group.command("merge")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--stage", type=click.Choice(["classify", "decompose", "embedded", "relate"]),
              required=True)
@click.option("--batch-id", type=str, required=True)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_merge(doc_id, stage, batch_id, root):
    """Validate then atomically merge a completed packet."""
    from .agent_packets import merge_packet
    report = merge_packet(root, doc_id, stage, batch_id)
    click.echo(json.dumps(report, indent=2))


@agent_group.command("claims")
@click.argument("doc_id", type=str)
@click.option("--stage", type=click.Choice(["classify", "decompose", "embedded", "relate"]),
              default=None)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_claims(doc_id, stage, root):
    """List packet claims/reservations."""
    from .agent_packets import list_claims
    click.echo(json.dumps(list_claims(root, doc_id, stage), indent=2))


@agent_group.command("release")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--stage", type=click.Choice(["classify", "decompose", "embedded", "relate"]),
              required=True)
@click.option("--batch-id", type=str, required=True)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_release(doc_id, stage, batch_id, root):
    """Release a non-merged claim so its items can be re-exported."""
    from .agent_packets import release_claim
    click.echo(json.dumps(release_claim(root, doc_id, stage, batch_id), indent=2))


@agent_group.command("finalize")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
def cmd_agent_finalize(doc_id, root):
    """Run deterministic audit, relationship validation, render, and review publishing."""
    from .agent_packets import finalize
    finalize(root, doc_id)
    _publish_review_artifacts(root, doc_id)
    click.echo("deterministic finalize and review publishing passed")


@agent_group.command("adjudicate-relationships")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--mode", type=click.Choice(["auto", "live", "claude-code", "openai", "mock"]),
              default="auto")
@click.option("--model", type=str, default=None)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--finalize/--no-finalize", "do_finalize", default=True,
              help="Run deterministic finalize and review publishing after applying decisions.")
def cmd_agent_adjudicate_relationships(doc_id, mode, model, root, do_finalize):
    """Use an LLM to resolve ambiguous relationship edges."""
    from .agent_packets import adjudicate_ambiguous_relationships, finalize
    report = adjudicate_ambiguous_relationships(root, doc_id, mode=mode, model=model)
    click.echo(json.dumps(report, indent=2))
    if do_finalize and report.get("changed"):
        finalize(root, doc_id)
        _publish_review_artifacts(root, doc_id)
        click.echo("relationship adjudication finalized and review publishing passed")


@agent_group.command("adjudicate-downgrades")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--mode", type=click.Choice(["auto", "live", "claude-code", "openai", "mock"]),
              default="auto")
@click.option("--model", type=str, default=None)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--finalize/--no-finalize", "do_finalize", default=True,
              help="Run deterministic finalize and review publishing after applying decisions.")
def cmd_agent_adjudicate_downgrades(doc_id, mode, model, root, do_finalize):
    """Resolve pending downgrades (requirement-bearing spans where decomposers
    returned zero requirements): confirm_downgrade applies the recorded
    non-requirement label; extract supplies the missed requirements."""
    from .agent_packets import adjudicate_pending_downgrades, finalize
    report = adjudicate_pending_downgrades(root, doc_id, mode=mode, model=model)
    click.echo(json.dumps(report, indent=2))
    if do_finalize and report.get("changed"):
        finalize(root, doc_id)
        _publish_review_artifacts(root, doc_id)
        click.echo("downgrade adjudication finalized and review publishing passed")


@agent_group.command("adjudicate-ambiguities")
@click.option("--doc", "doc_id", type=str, required=True)
@click.option("--mode", type=click.Choice(["auto", "live", "claude-code", "openai", "mock"]),
              default="auto")
@click.option("--model", type=str, default=None)
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd())
@click.option("--finalize/--no-finalize", "do_finalize", default=True,
              help="Run deterministic finalize and review publishing after applying decisions.")
def cmd_agent_adjudicate_ambiguities(doc_id, mode, model, root, do_finalize):
    """Use an LLM to resolve classification, requirement, and relationship ambiguity."""
    from .agent_packets import adjudicate_ambiguous_catalog, finalize
    report = adjudicate_ambiguous_catalog(root, doc_id, mode=mode, model=model)
    click.echo(json.dumps(report, indent=2))
    if do_finalize:
        finalize(root, doc_id)
        _publish_review_artifacts(root, doc_id)
        click.echo("catalog ambiguity adjudication finalized and review publishing passed")


def _publish_review_artifacts(root: Path, doc_id: str) -> None:
    """Refresh human-review and cross-doc artifacts after agent finalization."""
    scripts = root / "scripts"
    steps = [
        ("completeness report", [scripts / "verify_completeness.py", "--doc", doc_id]),
        ("confidence summary", [scripts / "confidence_summary.py", "--doc", doc_id]),
        ("side-by-side review", [scripts / "review_sidebyside.py", "--doc", doc_id]),
        ("review site", [scripts / "build_review_site.py", "--doc", doc_id]),
        ("cross-doc references", [scripts / "scan_cross_doc_refs.py"]),
        ("scope triage", [scripts / "triage_unresolved_refs.py"]),
        ("atomic relationship map", [scripts / "build_atomic_relationship_map.py"]),
        ("pivot views", [scripts / "build_pivot_views.py"]),
        ("integrated audit", [scripts / "integrated_audit.py"]),
    ]
    for label, args in steps:
        click.echo(f"publishing: {label}")
        subprocess.run(
            [sys.executable, *(str(arg) for arg in args)],
            cwd=root,
            check=True,
        )


if __name__ == "__main__":
    main()
