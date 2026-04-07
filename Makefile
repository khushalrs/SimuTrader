.PHONY: up down logs api web smoke-backend

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

api:
	docker compose up --build api

web:
	docker compose up --build web

smoke-backend:
	./scripts/run_backend_smoke.sh
