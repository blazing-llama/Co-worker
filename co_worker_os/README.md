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

# 3. Install Python dependencies
pip install -e ".[dev]"

# 4. Install local security hooks
failproofai policies --install --cli claude   # falls back to local hooks if unavailable

# 5. Run tests
pytest
```

## Project Structure

See `docs/Architecture.md` for the full hub-and-spoke design and
`docs/ImplementationPlan.md` for the 5-sprint build sequence.

## Status

Scaffolding phase (Phase 0) complete. See `docs/ImplementationPlan.md` for
current sprint status.

## Notes on External Dependencies

`failproofai` and `strands-agents-evals` are external packages this project
depends on for security hooks and eval diagnostics, respectively. If either
fails to install in your environment, the corresponding module
(`src/security/guardrails.py`, `src/evals/strands_harness.py`) falls back to
an equivalent local implementation — no sprint is blocked by a missing
third-party package.
