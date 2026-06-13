# FinAdvisor

A production-ready, highly polished personal finance and credit advisory application built with a modern backend and a premium, responsive glassmorphic frontend UI.

## 🚀 Features

*   **Credit Health Ring Widget**: An interactive, animated gauge providing a real-time overview of your credit utilization, active cards, and available limit.
*   **Premium Glassmorphic UI**: High-end visual design utilizing frosted glass elements, ambient glowing blobs, and smooth micro-animations.
*   **Dynamic Theming Engine**: Switch between 6 curated color themes on the fly (e.g., Default Light, Midnight Aurora, Warm Charcoal, Graphite) via the profile page.
*   **Mobile-First Responsive Design**: Robust responsive grids (`.grid-2`, `.grid-3`, `.grid-4`) that elegantly collapse into stacked layouts on mobile devices. Features touch-friendly horizontal scroll tabs and a responsive hamburger navigation.
*   **Email Auto-Collection**: Integrated workflows for connecting external accounts (Gmail) and extracting financial data securely.
*   **Robust Security Architecture**: Complete JWT authentication with IDOR access validation across all API routers and client scripts to ensure strict data isolation. 
*   **Privacy-Centric**: Advisory-only platform. No payment processing. Stores only the last 4 digits of your credit cards.

## 🛠️ Technology Stack

*   **Backend**: FastAPI, PostgreSQL, SQLAlchemy (async), Alembic, PyJWT
*   **Frontend**: Vanilla HTML5, CSS3 (Custom Properties & Modern Grids), Vanilla JavaScript, Lucide Icons
*   **Architecture**: RESTful JSON APIs (`/api/v1/*`) serving decoupled frontend views.

## 💻 Local Setup

1. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Mac/Linux
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

2. Create a `.env` file (copy from `.env.example`) and configure your PostgreSQL database credentials.

3. Run database migrations to set up the schema:
```bash
alembic upgrade head
```

4. Start the development server:
```bash
uvicorn main:app --reload
```

Open `http://localhost:8000` in your browser.

## 🐳 Docker Deployment

Run the app and database simultaneously with Docker Compose:

```bash
docker compose up --build
```

The API and frontend will be exposed at `http://localhost:8000`.

To stop and remove containers:
```bash
docker compose down
```
