# FinAdvisor

Production-ready personal finance advisory app built with FastAPI, PostgreSQL, SQLAlchemy async, Alembic, and vanilla HTML/CSS/JS.

## Setup

1. Create a virtual environment and install dependencies:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Create a `.env` file (copy from `.env.example`) and update values.

3. Run database migrations:

```
alembic upgrade head
```

4. Start the server:

```
uvicorn main:app --reload
```

Open `http://localhost:8000`.

### Notes
- Advisory-only platform. No payment processing.
- Stores only last 4 digits of card numbers.
- Use `/api/v1` endpoints for programmatic access.

#### Docker

Run the app and database with Docker Compose:

```
docker compose up --build
```

The API will be available at `http://localhost:8000`.

To stop and remove containers:

```
docker compose down
```





<!--
C:\Users\Prajwal Nair\OneDrive\Desktop\New folder>cd FinAdvisor

C:\Users\Prajwal Nair\OneDrive\Desktop\New folder\FinAdvisor>python -m venv .venv

C:\Users\Prajwal Nair\OneDrive\Desktop\New folder\FinAdvisor>.venv\Scripts\activate -->

<!-- to run this project  -->
<!--
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
-->


py -3.11 -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload