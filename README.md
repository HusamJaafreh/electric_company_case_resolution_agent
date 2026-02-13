## Setup

1) Create venv + install:
pip install -r requirements.txt

2) Copy env:
copy .env.example .env

3) Migrate:
python manage.py migrate

4) Run:
python manage.py runserver

Swagger:
http://127.0.0.1:8000/api/docs/

Schema:
http://127.0.0.1:8000/api/schema/
