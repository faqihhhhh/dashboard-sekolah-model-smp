# Baris perintah diawali tanda ">" (bukan TAB) agar aman disalin dari mana pun.
.RECIPEPREFIX = >
.PHONY: up down dev migrate test lint fmt shell check

up:
> docker compose up -d db

down:
> docker compose down

dev: up
> uv run python manage.py migrate
> uv run python manage.py runserver

migrate:
> uv run python manage.py migrate

test:
> uv run pytest

lint:
> uv run ruff check .
> uv run ruff format --check .

fmt:
> uv run ruff check --fix .
> uv run ruff format .

shell:
> uv run python manage.py shell

check:
> uv run python manage.py check
> $(MAKE) lint
> $(MAKE) test
