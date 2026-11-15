.PHONY: help dev test lint frontend-build prod-up prod-down prod-logs backup eval

PROD = docker compose --env-file .env.production -f docker-compose.prod.yml

help:           ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

dev:            ## Run the development stack (hot reload)
	docker compose up -d --build

test:           ## Run the backend test suite
	python -m pytest -q

lint:           ## Type-check the frontend and lint the backend
	ruff check app tests
	cd frontend && npm run typecheck

frontend-build: ## Build the React app into frontend/dist
	cd frontend && npm ci && npm run build

prod-up:        ## Start the production stack (needs .env.production)
	@test -f .env.production || { echo "Create .env.production from .env.production.example first"; exit 1; }
	$(PROD) up -d --build

prod-down:      ## Stop the production stack
	$(PROD) down

prod-logs:      ## Follow production logs
	$(PROD) logs -f --tail 100

backup:         ## Back up the database and uploads
	scripts/backup.sh

eval:           ## Run the retrieval/answer-quality evaluation
	python eval/run_eval.py
