# F1 Regulations Engine — developer shortcuts.
# Requires Docker + Docker Compose. Override the compose command if needed:
#   make demo COMPOSE="docker-compose"
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help up upd down clean logs seed demo ingest test lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build and start all services (foreground)
	$(COMPOSE) up --build

upd: ## Build and start all services (detached)
	$(COMPOSE) up -d --build

down: ## Stop services
	$(COMPOSE) down

clean: ## Stop services AND wipe the database volume
	$(COMPOSE) down -v

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

seed: ## Load the demo dataset (sample articles + embeddings) into the DB
	$(COMPOSE) exec -T db psql -U postgres -d f1_regs < backend/database/seed.sql
	@echo "Demo data loaded. Open http://localhost:3000"

demo: upd ## One command: start everything and load the demo data
	@echo "Waiting for the database to be ready..."
	@for i in $$(seq 1 30); do $(COMPOSE) exec -T db pg_isready -U postgres >/dev/null 2>&1 && break; sleep 2; done
	@$(MAKE) seed
	@echo ""
	@echo "  Ready!  Frontend: http://localhost:3000   API docs: http://localhost:8000/docs"
	@echo "  (Chat answers need OPENROUTER_API_KEY in .env; retrieval/compare work without it.)"

ingest: ## Ingest the PDFs placed in archives/ (your own files)
	$(COMPOSE) exec -T backend python -m scripts.ingest_archives

test: ## Run the backend test suite
	$(COMPOSE) exec -T backend sh -c "pip install -q pytest && python -m pytest tests/ -q"

lint: ## Lint the backend with ruff
	$(COMPOSE) exec -T backend sh -c "pip install -q ruff && ruff check ."

