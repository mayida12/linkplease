````markdown
# LinkPlease Instagram Automation

A backend system that monitors Instagram comments through a mock API and automatically sends a DM when a comment matches a keyword rule.

The system guarantees **one DM per user per rule**, even with duplicate webhooks, retries, concurrent processing, and worker restarts.

## ✨ Features

- Keyword-based Instagram comment matching
- Case-insensitive keyword matching
- Duplicate webhook protection using unique `event_id`
- Database-level DM deduplication per user + rule
- Background worker for processing and sending DMs
- PostgreSQL-backed job queue
- Rate limiting: 10 requests / 60 seconds
- Automatic retries for `429` and `500` responses
- Exponential backoff with `Retry-After` support
- HMAC-SHA256 webhook signature verification
- `202 Accepted` DM reconciliation
- Persistent job state across worker restarts
- Live `/stats` endpoint
- Docker Compose setup
- PostgreSQL-based concurrency control with `FOR UPDATE SKIP LOCKED`

## 🏗️ Architecture

```text
Instagram / Mock API
        │
        ▼
   POST /webhook
        │
        ▼
 Signature Verification
        │
        ▼
 PostgreSQL
        │
        ▼
 Background Worker
        │
        ├── Match keyword
        ├── Prevent duplicates
        ├── Queue DM
        ├── Apply rate limit
        └── Retry failed requests
                │
                ▼
        Mock Instagram API
                │
                ▼
        Delivery Reconciliation
                │
                ▼
             /stats
````

## 🛠️ Tech Stack

* Python 3.11+
* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic
* Pytest
* Docker / Docker Compose

## 🚀 Running Locally

### Using Docker

```bash
cp backend/.env.example backend/.env
```

Add your `MOCK_API_KEY` to `backend/.env`, then:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

### Without Docker

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

Configure `DATABASE_URL` and `MOCK_API_KEY`, then run:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
python -m app.workers.run
```

## 🧪 Tests

The project includes unit and integration tests covering:

* Rule creation
* Keyword matching
* Duplicate webhooks
* Duplicate users
* Multiple rules
* Concurrent processing
* Rate limiting
* `429` / `500` retries
* `400` failures
* Webhook signatures
* Worker restart recovery
* DM reconciliation
* Statistics

Run:

```bash
cd backend
pytest -v
```

**Current test status: 33 tests passing.**

## 📊 API Endpoints

| Method | Endpoint   | Description                      |
| ------ | ---------- | -------------------------------- |
| `POST` | `/rules`   | Create a keyword → DM rule       |
| `POST` | `/webhook` | Receive Instagram comment events |
| `GET`  | `/stats`   | View DM processing statistics    |

## 🔐 Reliability

Duplicate prevention is enforced at the database level using unique constraints:

```text
webhook_events.event_id
        ↓
Prevents duplicate webhook processing

dm_dedup(rule_id, recipient_user_id)
        ↓
Prevents duplicate DMs
```

Jobs and retry state are stored in PostgreSQL, so restarting the worker does not lose queued work.

## 📁 Project Structure

```text
linkplease/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── workers/
│   │   ├── models/
│   │   └── main.py
│   ├── tests/
│   ├── migrations/
│   ├── scripts/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── index.html
├── docker-compose.yml
├── FAILURES.md
└── README.md
```

## ⚠️ Known Limitations

* The current worker architecture assumes a single worker process.
* The load test requires a publicly deployed API.
* PostgreSQL is required for the concurrency guarantees.

## 👤 Assignment

Built as a technical internship assignment demonstrating backend engineering, database consistency, asynchronous job processing, API reliability, and production-oriented error handling.

```
```
