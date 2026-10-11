# Baris perintah diawali tanda ">" (bukan TAB) agar aman disalin dari mana pun.
.RECIPEPREFIX = >
.PHONY: up down dev migrate makemigrations superuser seed seed-demo demo-hapus wilayah-csv test lint fmt shell check css css-watch vendor

up:
> docker compose up -d db

down:
> docker compose down

dev: up css
> uv run python manage.py migrate
> uv run python manage.py runserver

migrate:
> uv run python manage.py migrate

makemigrations:
> uv run python manage.py makemigrations

superuser:
> uv run python manage.py createsuperuser

seed:
> uv run python manage.py seed_wilayah

seed-demo:
> uv run python manage.py seed_demo_sekolah

demo-hapus:
> uv run python manage.py seed_demo_sekolah --hapus

wilayah-csv:
> uv run python scripts/build_wilayah_csv.py

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

# Tailwind CLI diunduh otomatis bila belum ada.
bin/tailwindcss:
> bash scripts/get_tailwind.sh

css: bin/tailwindcss
> ./bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify

css-watch: bin/tailwindcss
> ./bin/tailwindcss -i static/css/input.css -o static/css/app.css --watch

vendor:
> bash scripts/get_vendor.sh
