# 🌦 UK MetOffice Climate Explorer

A full-stack Django application that fetches, stores, and serves UK Met Office regional climate data via a RESTful API, with an interactive browser-based dashboard.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Quick Start (Local Dev)](#quick-start-local-dev)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Project Structure](#project-structure)
- [Git Workflow](#git-workflow)

---

## Architecture Overview

```
┌──────────────┐      HTTP GET       ┌──────────────────────┐
│  Met Office  │◄────────────────────│  Django Fetcher      │
│  .gov.uk     │                     │  (parsers.py)        │
└──────────────┘                     └──────────┬───────────┘
                                                │ upsert
                                     ┌──────────▼───────────┐
                                     │  PostgreSQL           │
                                     │  Parameter / Region   │
                                     │  WeatherDataset       │
                                     │  WeatherRecord        │
                                     └──────────┬───────────┘
                                                │ query
                             ┌──────────────────▼────────────────────┐
                             │  Django REST Framework (DRF)           │
                             │  /api/records/  /api/fetch/            │
                             │  /api/records/annual-series/           │
                             │  /api/records/monthly-averages/        │
                             └──────────────────┬────────────────────┘
                                                │
                             ┌──────────────────▼────────────────────┐
                             │  Frontend Dashboard (Chart.js)         │
                             │  Annual series · Monthly climatology   │
                             │  Decade heatmap · Data table · Export  │
                             └───────────────────────────────────────┘
```

---

## Features

| Area | What's included |
|------|----------------|
| **Data Parsing** | Fetches `.txt` files from Met Office, handles `---` missing values, provisional `*` markers, variable header rows |
| **Models** | `Parameter`, `Region`, `WeatherDataset`, `WeatherRecord` with proper indexing and upsert logic |
| **REST API** | Full CRUD-read via DRF ViewSets, custom actions (`annual-series`, `monthly-averages`), filtering, ordering, pagination |
| **API Docs** | Auto-generated Swagger UI at `/api/docs/` and ReDoc at `/api/redoc/` |
| **Frontend** | Interactive dashboard — time-series chart, monthly climatology bar, decade heatmap, data table, CSV export |
| **Management Command** | `python manage.py fetch_weather` — bulk ingest with parameter/region filters |
| **Celery** | Async fetch tasks, retries on network failure, schedulable via Celery Beat |
| **Docker** | Multi-stage Dockerfile, `docker-compose.yml` with PostgreSQL, Redis, Nginx profiles |
| **Cloud** | Render, Railway, and AWS ECS deployment instructions below |

---

## Quick Start (Local Dev)

### Prerequisites
- Python 3.11+
- PostgreSQL (or use SQLite for local-only)
- Git

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/metoffice-weather.git
cd metoffice-weather

# 2. Virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env
# Edit .env — set DEBUG=True and leave POSTGRES_* blank to use SQLite

# 5. Run migrations
python manage.py migrate

# 6. Create superuser (optional)
python manage.py createsuperuser

# 7. Fetch initial data (Met Office network required)
python manage.py fetch_weather --parameter Tmax Tmin Tmean --region UK England Wales

# 8. Run dev server
python manage.py runserver
```

Open http://127.0.0.1:8000 for the dashboard.
Open http://127.0.0.1:8000/api/docs/ for the Swagger API explorer.

---

## Docker Deployment

### Development with Docker Compose

```bash
# Copy and edit env file
cp .env.example .env

# Build and start (PostgreSQL + Redis + Django)
docker compose up --build

# In another terminal — run migrations and fetch data
docker compose exec web python manage.py migrate
docker compose exec web python manage.py fetch_weather --parameter Tmax Tmean Rainfall --region UK England Scotland Wales

# Open http://localhost:8000
```

### Production with Nginx

```bash
# Start with Nginx profile
docker compose --profile nginx up --build -d

# Open http://localhost:80
```

### Useful Docker commands

```bash
# View logs
docker compose logs -f web

# Django shell
docker compose exec web python manage.py shell

# Run all default datasets
docker compose exec web python manage.py fetch_weather --all

# Stop everything
docker compose down -v    # -v removes volumes (deletes DB data)
```

---

## Cloud Deployment

### Option 1 — Render.com (recommended — free tier available)

1. Push code to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Set:
   - **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start command:** `gunicorn metoffice_weather.wsgi:application --bind 0.0.0.0:$PORT`
4. Add a **PostgreSQL** database from Render dashboard, copy the `DATABASE_URL` into env vars.
5. Set env vars: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=your-app.onrender.com`.
6. Deploy. Once live, open the Shell tab and run:
   ```bash
   python manage.py fetch_weather --parameter Tmax Tmean Rainfall --region UK England
   ```

### Option 2 — Railway.app

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create project
railway init
railway add postgresql
railway add redis

# Set env vars
railway variables set SECRET_KEY=... DEBUG=False ALLOWED_HOSTS=...

# Deploy
railway up
railway run python manage.py migrate
railway run python manage.py fetch_weather --parameter Tmax Tmean --region UK England
```

### Option 3 — AWS ECS (Fargate)

1. Push Docker image to ECR:
   ```bash
   aws ecr create-repository --repository-name metoffice-weather
   docker build -t metoffice-weather .
   docker tag metoffice-weather:latest <account_id>.dkr.ecr.<region>.amazonaws.com/metoffice-weather:latest
   aws ecr get-login-password | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com
   docker push <account_id>.dkr.ecr.<region>.amazonaws.com/metoffice-weather:latest
   ```
2. Create an ECS Cluster → Task Definition → Service using the image above.
3. Add an RDS PostgreSQL instance and set `DATABASE_URL` in the task environment.
4. Create an Application Load Balancer pointing to port 8000.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/parameters/` | List all climate parameters |
| `GET` | `/api/regions/` | List all UK regions |
| `GET` | `/api/datasets/` | List fetched datasets (param × region) |
| `GET` | `/api/records/` | Paginated weather records; filter by `dataset__parameter__code`, `dataset__region__code`, `year__gte`, `year__lte` |
| `GET` | `/api/records/annual-series/?parameter=Tmax&region=UK` | Lightweight year + annual value list for charting |
| `GET` | `/api/records/monthly-averages/?parameter=Tmax&region=UK&year_from=1960&year_to=2020` | Mean value per calendar month |
| `POST` | `/api/fetch/` | Trigger a fresh fetch from Met Office. Body: `{"parameter":"Tmax","region":"UK"}` |
| `GET` | `/api/meta/` | Available parameters, regions, and dataset count |
| `GET` | `/api/docs/` | Swagger interactive API explorer |
| `GET` | `/api/redoc/` | ReDoc documentation |

### Example: Fetch Tmax data for UK

```bash
# Trigger data load
curl -X POST http://localhost:8000/api/fetch/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{"parameter": "Tmax", "region": "UK"}'

# Query records
curl "http://localhost:8000/api/records/?dataset__parameter__code=Tmax&dataset__region__code=UK&year__gte=2000"

# Annual series for charting
curl "http://localhost:8000/api/records/annual-series/?parameter=Tmax&region=UK"

# Monthly climatology (1960–2020)
curl "http://localhost:8000/api/records/monthly-averages/?parameter=Tmax&region=UK&year_from=1960&year_to=2020"
```

---

## Data Model

```
Parameter          Region
──────────         ──────────
id                 id
code (unique)      code (unique)
display_name       display_name
unit
description
       │                 │
       └────────┬────────┘
                │
         WeatherDataset
         ──────────────
         id
         parameter_id (FK)
         region_id (FK)
         source_url
         last_fetched
         row_count
                │
         WeatherRecord (one per year)
         ──────────────────────────────
         id
         dataset_id (FK)
         year
         jan, feb, mar, apr, may, jun
         jul, aug, sep, oct, nov, dec
         annual
```

---

## Project Structure

```
metoffice_weather/
├── manage.py
├── requirements.txt
├── Dockerfile                    # Multi-stage production image
├── docker-compose.yml            # Full stack: Django + PostgreSQL + Redis + Nginx
├── nginx.conf                    # Nginx reverse proxy config
├── .env.example                  # Environment variable template
├── .gitignore
├── README.md
│
├── metoffice_weather/            # Django project package
│   ├── settings.py               # Env-driven settings (SQLite dev, PostgreSQL prod)
│   ├── urls.py                   # URL routing — API + frontend
│   ├── wsgi.py
│   └── celery.py                 # Celery app config
│
├── weather/                      # Main application
│   ├── models.py                 # Parameter, Region, WeatherDataset, WeatherRecord
│   ├── parsers.py                # Met Office .txt file fetcher and parser
│   ├── serializers.py            # DRF serializers (full, compact, annual-series)
│   ├── views.py                  # ViewSets + FetchDataView + MetaView
│   ├── urls.py                   # API router
│   ├── frontend_urls.py          # Dashboard URL
│   ├── frontend_views.py         # Template view
│   ├── tasks.py                  # Celery async tasks
│   ├── admin.py                  # Django admin registration
│   └── management/
│       └── commands/
│           └── fetch_weather.py  # CLI bulk-ingest command
│
├── templates/
│   └── weather/
│       └── dashboard.html        # Single-page interactive dashboard
│
└── static/                       # Static assets (collected by whitenoise)
```

---

## Git Workflow

```bash
# Initial setup
git init
git add .
git commit -m "feat: initial project setup"

# Feature branches
git checkout -b feature/add-decade-comparison
# ... make changes ...
git add .
git commit -m "feat: add decade-by-decade comparison chart"
git push origin feature/add-decade-comparison

# Suggested commit message format:
# feat:     new feature
# fix:      bug fix
# data:     data model / migration change
# api:      API endpoint change
# docs:     documentation update
# docker:   Docker / deployment change
# refactor: code restructure
```

---

## Available Parameters & Regions

**Parameters:** `Tmax` · `Tmin` · `Tmean` · `Rainfall` · `Sunshine` · `Raindays1mm` · `AirFrost`

**Regions:** `UK` · `England` · `Wales` · `Scotland` · `Northern_Ireland` · `England_and_Wales` · `England_N` · `England_S` · `Scotland_N` · `Scotland_E` · `Scotland_W` · `EW_E` · `EW_W` · `Midlands` · `East_Anglia`

Data source: [Met Office UK Climate Datasets](https://www.metoffice.gov.uk/research/climate/maps-and-data/uk-and-regional-series)
# weather-app
