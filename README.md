# GBOGEB / GEMINI 🚀
> **Single Source of Truth (SSOT) Baseline Configuration Engine**

This repository serves as a code-driven repository framework designed for verifying engineering architectures, tracking technical requirement lineages, and providing executable specifications for AI systems (GitHub Copilot / OpenAI GPTs).

## 📊 Repository Components
* **`config/blsn_config.yaml`**: The single source of truth containing raw metrics and metadata constants.
* **`src/pipeline.py`**: The idempotent python engine compiling configuration data into actionable formats.
* **`notebook.md`**: Interactive execution notebook containing modular code-blocks and structured contextual handover guides.

## ⚙️ Automated CI/CD Execution
Every commit or pull request triggers the `.github/workflows/generate_blsn_reports.yml` engine. This automatically checks the configuration integrity and generates fresh, compiled engineering baselines under the GitHub Actions artifacts.
