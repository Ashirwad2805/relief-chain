# ReliefChain

Local development does not require Docker.

## Run the backend

From the project root in PowerShell:

```powershell
Set-Location backend
..\venv\Scripts\python.exe -m pip install -r requirements.txt
..\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

The API docs are available at `http://localhost:8000/docs`. Keep OpenRouter and
other provider credentials in the backend environment; do not expose them with
`VITE_` variables.

## Run the frontend

In a second terminal, from the project root:

```powershell
npm install
npm run dev
```

Vite runs at `http://localhost:5173`. The frontend API client uses
`VITE_API_URL` when set and otherwise calls `http://localhost:8000` during
development. In production it uses the current site origin, so API calls use
the `/api` Vercel rewrite rather than a separately configured backend URL.

## Deploy on Vercel

The root `vercel.json` configures the Vite app and FastAPI backend as separate
services. `/api/*` and `/ws` are routed to the backend; all other paths go to
the app. The browser calls the backend through those public same-origin paths,
so no service binding is needed.

The landing page's Get Started and Start Donating buttons open the existing
Emergency Funds tracker at `#/funds`. The upstream project does not currently
include a donation checkout or login page.
