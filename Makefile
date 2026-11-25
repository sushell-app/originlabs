.PHONY: dev down logs migrate check-compose check-bash check-py

dev:
	docker compose -f compose.dev.yml up --build

down:
	docker compose -f compose.dev.yml down

logs:
	docker compose -f compose.dev.yml logs -f

migrate:
	docker compose -f compose.dev.yml exec api alembic upgrade head

check-compose:
	docker compose --env-file .env.example -f compose.dev.yml config -q
	docker compose --env-file .env.example -f compose.prod.yml config -q

check-bash:
	bash -n installer/install.sh
	bash -n installer/uninstall.sh

check-py:
	python3 -m compileall -q backend/app backend/tests
