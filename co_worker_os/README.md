# Co-Worker OS

A 100% local, zero-subscription, privacy-preserving multi-agent "startup team"
system: Co-Founder, Product Manager, Engineering Lead, GTM/Research Lead, and
Legal/Finance Strategy agent — all running on local Ollama models, with local
scraping (Crawl4AI, yt-dlp, DuckDuckGo) and no required cloud API keys.

## Quick Start

```bash
# 1. Install Ollama and pull the required models
ollama pull qwen2.5:32b
ollama pull qwen2.5-coder:14b
ollama pull llama3.2:3b

# 2. Verify Ollama is serving locally
curl http://localhost:11434/api/tags
# or, from Python: from src.core.config import list_local_models, verify_model_routing

# 3. Install Python dependencies
pip install -e ".[dev]"

# 4. (Optional) install FailproofAI's local security hooks, if available in
#    your environment -- NOT a hard dependency, see "Notes on External
#    Dependencies" below. src/security/guardrails.py enforces the same
#    policies locally either way.
pip install -e ".[failproofai]" && failproofai policies --install --cli claude

# 5. Run tests
pytest

# 6. Run the CLI against your local Ollama
co-worker "A local-first note-taking app for solo founders"
```

## Project Structure

See `docs/Architecture.md` for the full hub-and-spoke design and
`docs/ImplementationPlan.md` for the 5-sprint build sequence.

## Status

All 5 sprints complete. See `docs/ImplementationPlan.md` for the full,
per-sprint result log (including what was verified live vs. mocked in this
development environment, and any deliberate deviations from the original
plan).

## Notes on External Dependencies

- **`strands-agents-evals`** installs cleanly via pip (confirmed in this
  project's development environment) and is a hard dependency. Its real API
  (`strands_evals.detectors.detect_failures`/`analyze_root_cause`,
  `strands_evals.types.trace.Session`) differs from some naming used in early
  planning docs; `src/evals/strands_harness.py` is built against the verified
  real classes, with a local fallback if the package is ever unavailable.
- **`failproofai`** is **not** installable via pip in this project's
  development environment (`pip install failproofai` returned "No matching
  distribution found"). It is an *optional* extra (`pip install
  -e ".[failproofai]"`), not a hard dependency, so a plain `pip install -e .`
  always succeeds. `src/security/guardrails.py` enforces the same policies
  (destructive-command interception, secret sanitization) locally regardless
  of whether the package is present — no sprint is blocked by its absence.

## Ollama Availability

This project was developed and tested in a sandbox without Ollama installed
or reachable, so all local-model calls in the test suite are mocked/stubbed.
Before a real run, verify your own local models are pulled and reachable
(`ollama list`, or `src.core.config.verify_model_routing()`), and don't assume
a model is available just because it's the default in `src/core/config.py`.
