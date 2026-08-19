# regcat — standalone package

Multi-agent decomposition of regulatory PDFs into atomic, verbatim-grounded
catalog entries, with a **provable coverage guarantee**: every byte of the
canonical document text is attributed to exactly one span, every extracted
item carries a `verbatim_quote` that must be an exact substring of its source
span, and a deterministic (no-LLM) audit gate halts the pipeline on any gap,
overlap, or unattributed content.

This is a verbatim lift of `src/regcat/` from the Anvil Clinical repo
(packaged 2026-08-19), plus its tests, its review-publishing scripts, and one
fully processed reference document. It has **zero imports** from the rest of
that repo — it runs on its own.

**If you are adapting this to a new document domain (e.g. drug product
labels), read `PORTING_README.md` first.** It maps which parts are
domain-generic (keep) and which encode the regulatory-CFR domain (replace).

## Layout

```
pyproject.toml            regcat-only metadata; `regcat` console script
src/regcat/
  orchestrator.py         linear 13-stage DAG; artifacts on disk between stages
  cli.py                  regcat ingest/run/ls/status/report + `regcat agent ...`
  schemas.py              Pydantic models for every stage boundary
  stages/                 ingest, boilerplate, segment, classify, decompose,
                          embedded_audit, audit (the hard coverage gate),
                          relate, validate_rel, adjudicate
  parsers/                CFRSegmenter, ICHSegmenter, GenericSegmenter (+ base)
  prompts/                system/user prompts for every LLM stage
  llm.py                  Anthropic / OpenAI / claude-code (subscription) / mock
  agent_packets.py        no-API packet workflow: export -> validate -> merge
  registry.py             multi-doc registry (docs/<jurisdiction>/<short_id>/)
  signals.py              deterministic obligation-signal regex scanner
  text_quality.py         degenerate-span (figure/table word-salad) guard
  global_ids.py           <doc_id>:<local_id> cross-doc identity
  render/markdown.py      final catalog.md renderer
tests/                    segmenter coverage-invariant tests, packet-security
                          tests, downgrade-pending invariant tests
scripts/                  the 9 review-publishing tools that
                          cli._publish_review_artifacts shells out to
docs/fda/21-cfr-part-11/  a complete worked reference doc: source.pdf,
                          canonical text + spans, catalog, audit reports, and
                          the mock-LLM fixtures that replay its full pipeline
```

## Install

```bash
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate
pip install -e ".[dev]"                        # mock mode + tests, no LLM deps
# choose an LLM backend when you need one:
pip install -e ".[claude-code]"                # Claude Code subscription auth
pip install -e ".[anthropic]"                  # or direct API
```

## Quickstart

Run the tests (offline, seconds):

```bash
pytest
```

Replay the reference doc's pipeline end-to-end with no LLM (fixture replay):

```bash
regcat run --doc fda/21-cfr-part-11 --mode mock --root .
```

Expected outcome: `coverage=100.00%  reqs=153  status=needs_review` with
"ambiguous relationships=2" remaining. That is correct behavior, not a
failure — the adjudication stage no-ops in mock mode, so two ambiguous
relationship edges stay preserved (they'd be resolved by
`regcat agent adjudicate-relationships` with a live LLM).

Process a new PDF:

```bash
regcat ingest path/to/doc.pdf --jurisdiction fda --id my-doc-slug \
    --title "Human Title" --citation-format generic --root .
regcat run --doc fda/my-doc-slug --mode claude-code --root .
regcat report fda/my-doc-slug --root .
```

Notes:

- `--root` must be a directory containing `docs/` (created as needed) **and**
  `scripts/` — the finalize step shells out to `scripts/*.py` for review
  publishing. Running from this package's root works as-is.
- `--citation-format` picks the segmenter: `cfr`, `ich`, or `generic`
  (blank-line paragraph blocking — the safe default for any prose document).
- `--mode auto` resolves to `claude-code` (subscription auth via
  `claude login`); API backends are used only when passed explicitly.
- The packaged `docs/` contains only the one reference doc. `docs/registry.json`
  is a regenerable view — run `regcat index --root .` to (re)build it from the
  per-doc `meta.json` files.
- The no-API alternative to `regcat run` is the agent-packet workflow
  (`regcat agent export/validate/merge/finalize`): bounded JSONL work packets
  a workspace agent completes in place, merged only after strict validation.

## The invariants that matter

1. **Segmentation is gap-free by construction** — parsers only record where
   spans *start*; each span ends where the next begins, so no byte can be
   skipped (`parsers/base.py` contract, enforced again in `stages/audit.py`).
2. **The coverage audit is pure code** — `stages/audit.py` raises unless byte
   coverage is exactly 100% with zero overlaps/gaps, every span is classified,
   every requirement-bearing span has >=1 extraction, and every
   `verbatim_quote` is an exact substring of its span.
3. **Disagreement is preserved, never silently resolved** — two independent
   LLM personas per stage + a reconciler; unresolved items are tagged
   `ambiguous`; zero-extraction requirement-bearing spans become
   `downgrade_pending`; finalize refuses to complete until adjudication.

Keep all three when porting. They are the product.
