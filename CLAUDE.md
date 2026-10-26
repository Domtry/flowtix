# FlowtTix — Plateforme RPA Intelligente

## Architecture

Monorepo modulaire Python (backend) + Angular (frontend).

### Structure
- `apps/api/` — API FastAPI (point d'entree unique pour le Studio)
- `apps/studio/` — Frontend Angular
- `services/orchestrator/` — Orchestration Temporal
- `services/data-engine/` — Manipulation de donnees (Pandas, Pydantic)
- `services/perception/` — Detection d'elements (DOM, accessibilite, OCR, vision)
- `services/resource-manager/` — Gestion CPU/GPU/RAM
- `agents/browser/` — Robot navigateur (Playwright)
- `agents/windows/` — Robot Windows (UI Automation, pywinauto)
- `agents/common/` — Interface de base des robots
- `packages/process-schema/` — Schema de processus versionne (Pydantic)
- `packages/execution-contracts/` — Contrats orchestrateur-robot
- `packages/security/` — Authentification, chiffrement
- `packages/observability/` — Logs structures, OpenTelemetry
- `services/ai/` — IA locale (Ollama — mistral, llava)
- `infrastructure/docker/` — Docker Compose (PostgreSQL, Redis, MinIO, Temporal, Ollama, Jaeger)

### Stack
- Python 3.11+, FastAPI, Pydantic, SQLModel, asyncpg
- Angular 18+, TypeScript
- PostgreSQL 16, Redis 7, MinIO, Temporal
- Playwright, pywinauto, PaddleOCR, OpenCV, Ollama

### Conventions
- Chaque module Python a son propre `pyproject.toml`
- Tests : `pytest` (backend), Karma/Jest (frontend)
- Linting : `ruff`, `mypy --strict`
- Les secrets ne doivent jamais apparaitre en clair dans le code ou les logs
- Les expressions dans les scenarios sont evaluees dans un sandbox (pas d'eval)

### Commandes
```bash
# Demarrer l'infrastructure
cd infrastructure/docker && docker compose up -d

# API
cd apps/api && pip install -e ".[dev]" && uvicorn src.main:app --reload

# Studio
cd apps/studio && npm install && ng serve

# Tests
cd apps/api && pytest
cd packages/process-schema && pytest
cd packages/security && pytest
cd services/data-engine && pytest
cd services/resource-manager && pytest
cd services/ai && pytest
cd agents/windows && pytest

# Ollama (apres docker compose up)
docker exec flowtix-ollama ollama pull mistral:7b
```

### Securite
- JWT auth (HS256) avec RBAC 4 roles : admin, developer, operator, viewer
- Chiffrement secrets AES-256-GCM (cle via FLOWTIX_ENCRYPTION_KEY)
- Passwords bcrypt, jamais en clair
- Expressions sandbox (regex, pas d'eval/exec)
- CAPTCHA/MFA : pause, jamais contournement
