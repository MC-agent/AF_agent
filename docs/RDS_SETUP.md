# AWS RDS Setup

Use this project with a single AWS RDS for PostgreSQL database for both:

- application tables
- pgvector embeddings

## Requirements

- AWS RDS for PostgreSQL with the `vector` extension available
- Security group access from the machine running the API
- Valid `KAKAO_API_KEY` and `OPENAI_API_KEY`

## Recommended `.env`

```env
DEPLOY_ENV=local
ENABLE_PIPELINE_ROUTES=true

PG_HOST=your-rds-endpoint.amazonaws.com
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your_password
PG_DATABASE=af_vectors

KAKAO_API_KEY=your_kakao_api_key
OPENAI_API_KEY=your_openai_api_key
OPENROUTER=your_openrouter_api_key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
SECRET_KEY=your_secret_key
```

## Notes

- Leave `PGVECTOR_DATABASE_URL` unset to reuse the main PostgreSQL connection settings.
- If you prefer explicit URLs, set both `DATABASE_URL` and `PGVECTOR_DATABASE_URL` to the same RDS database.
- The app creates the `vector` extension if needed, but the RDS instance must support it first.

## Run

```bash
python main.py
```

## Upload crawled data

```bash
python src/scripts/local_crawl_and_upload.py \
  --queries "Seongsu restaurant" \
  --place_type restaurant \
  --limit 5 \
  --crawl_limit 3
```
