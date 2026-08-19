"""Pipeline orchestrator.

A linear DAG: each stage produces artifacts on disk, the next stage reads them.
Validation gates between stages halt the pipeline on any anomaly. State is
persisted, so re-running picks up where it left off unless `--force` is set.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .llm import LLMClient
from .schemas import RunMetadata


@dataclass
class Paths:
    root: Path             # project root (contains docs/)
    doc_id: str            # "<jurisdiction>/<short_id>"
    doc_dir: Path          # docs/<doc_id>/
    pdf: Path
    source_dir: Path
    catalog_dir: Path
    audit_dir: Path
    fixtures_dir: Path
    meta_path: Path

    @classmethod
    def for_doc(cls, root: Path, doc_id: str) -> "Paths":
        from .registry import doc_dir as resolve_doc_dir
        dd = resolve_doc_dir(root, doc_id)
        return cls(
            root=root,
            doc_id=doc_id,
            doc_dir=dd,
            pdf=dd / "source.pdf",
            source_dir=dd / "source",
            catalog_dir=dd / "catalog",
            audit_dir=dd / "audit",
            fixtures_dir=dd / "fixtures",
            meta_path=dd / "meta.json",
        )

    def ensure(self) -> None:
        for p in (self.source_dir, self.catalog_dir, self.audit_dir, self.fixtures_dir):
            p.mkdir(parents=True, exist_ok=True)


@dataclass
class StageSpec:
    name: str
    func: Callable[["RunContext"], None]


@dataclass
class RunContext:
    paths: Paths
    llm: LLMClient
    meta: RunMetadata
    log_lines: list[str]

    def log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        self.log_lines.append(line)

    def write_json(self, path: Path, obj) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(obj, "model_dump"):
            data = obj.model_dump(mode="json")
        else:
            data = obj
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_jsonl(self, path: Path, objs) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for o in objs:
                if hasattr(o, "model_dump"):
                    o = o.model_dump(mode="json")
                f.write(json.dumps(o, ensure_ascii=False))
                f.write("\n")

    def read_jsonl(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class PipelineError(RuntimeError):
    pass


def run_pipeline(
    doc_id: str,
    root: Path,
    mode: str = "auto",
    model: Optional[str] = None,
    stages: Optional[list[str]] = None,
) -> RunContext:
    paths = Paths.for_doc(root, doc_id)
    if not paths.pdf.exists():
        raise FileNotFoundError(
            f"No source PDF for {doc_id} at {paths.pdf}. "
            f"Run `regcat ingest <pdf> --jurisdiction <j> --id <id>` first."
        )
    paths.ensure()
    llm = LLMClient(mode=mode, model=model, fixtures_root=paths.fixtures_dir, env_root=root)

    meta = RunMetadata(
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        pdf_path=str(paths.pdf),
        pdf_sha256="",  # filled by ingest stage
        mode=llm.mode,
        model=llm.model,
    )
    ctx = RunContext(paths=paths, llm=llm, meta=meta, log_lines=[])

    # Lazy imports so each stage's deps load only when needed.
    from .stages import (
        ingest, boilerplate, segment, classify, decompose,
        embedded_audit, audit, relate, validate_rel, adjudicate,
    )
    from .render import markdown as render_md

    pipeline: list[StageSpec] = [
        StageSpec("ingest",          ingest.run),
        StageSpec("boilerplate",     boilerplate.run),
        StageSpec("segment",         segment.run),
        StageSpec("classify",        classify.run),
        StageSpec("decompose",       decompose.run),
        StageSpec("embedded_audit",  embedded_audit.run),
        StageSpec("audit",           audit.run),
        StageSpec("relate",          relate.run),
        StageSpec("validate_rel",    validate_rel.run),
        StageSpec("adjudicate",      adjudicate.run),
        StageSpec("audit",           audit.run),
        StageSpec("validate_rel",    validate_rel.run),
        StageSpec("render",          render_md.run),
    ]

    enabled = set(stages) if stages else None

    ctx.log(f"pipeline start  doc={doc_id}  mode={llm.mode}  model={llm.model}  pdf={paths.pdf.name}")
    for stage in pipeline:
        if enabled and stage.name not in enabled:
            ctx.log(f"  skip {stage.name}")
            continue
        ctx.log(f"  stage: {stage.name}")
        t0 = time.time()
        try:
            stage.func(ctx)
        except Exception as e:
            ctx.meta.error = f"{stage.name}: {e}"
            _persist_meta(ctx)
            ctx.log(f"  stage {stage.name} FAILED: {e}")
            raise
        dt = time.time() - t0
        ctx.meta.stages_completed.append(stage.name)
        ctx.log(f"  stage {stage.name} ok ({dt:.2f}s)")

    ctx.meta.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    _persist_meta(ctx)
    log_path = ctx.paths.audit_dir / "run.log"
    log_path.write_text("\n".join(ctx.log_lines), encoding="utf-8")
    ctx.log("pipeline complete")
    return ctx


def _persist_meta(ctx: RunContext) -> None:
    ctx.write_json(ctx.paths.audit_dir / "run_meta.json", ctx.meta)
