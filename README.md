# FinAdvisor

A production-ready, highly polished personal finance and credit advisory application built with a modern backend and a premium, responsive glassmorphic frontend UI.

## 🚀 Features

*   **📊 Spending Heatmap Calendar**: A GitHub-style contribution heatmap calendar displaying daily spending aggregates for the past 365 days, with hover cards and date filtering.
*   **🏦 Card Comparison Tool**: Select up to 3 cards side-by-side to compare credit limits, balances, annual fees, and monthly EMI burdens, with a dynamic Chart.js Radar comparison chart and automated credit utility/limit recommendations.
*   **🔔 Live Notification Bell (SSE)**: Real-time notification hub in the navbar with an unread badge and dropdown list. Captures statement imports, transaction detections, and EMI alerts via a Server-Sent Events stream, triggering sliding browser toasts and audio alerts.
*   **🏆 Achievement Badges (Trophy Case)**: A gamified rewards panel with 10 financial milestone badges (Shield Up, Streak Master, Card Collector, etc.) evaluated dynamically based on credit utilization, budget discipline, chatbot interactions, and login habits.
*   **🎯 Onboarding Checklist Flow**: A guided 3-step dashboard wizard (Add Card → Connect Gmail → Set Monthly Budget) complete with an SVG progress ring and inline budget setup configurations.
*   **🔥 Daily Login Streak Tracker**: Tracks and displays user login consistency with an animated flame indicator on the dashboard.
*   **Dynamic Theming Engine**: Switch between 6 curated color themes on the fly (e.g., Default Light, Midnight Aurora, Warm Charcoal, Graphite, Slate Glass) via the profile page.
*   **Credit Health Ring Widget**: An interactive, animated gauge providing a real-time overview of your credit utilization, active cards, available limit, and financial health score.
*   **Automatic Email Collection**: Integrated workflows for connecting external accounts (Gmail) and extracting financial data securely.
*   **Table-First CAS Statement Parser**: Robust, multi-bank PDF strategy parsing supporting HDFC, ICICI, Axis, SBI, Kotak, IndusInd, IDFC, and Yes Bank credit card statements.
*   **Mobile-First Responsive Design**: Robust grids that elegantly collapse into stacked layouts on mobile devices with touch-friendly tabs and responsive navbar.
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
