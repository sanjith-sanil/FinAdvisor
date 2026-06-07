from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/home")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/cards")
async def cards(request: Request):
    return templates.TemplateResponse("cards.html", {"request": request})


@router.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/analysis")
async def analysis_page(request: Request):
    return templates.TemplateResponse("analysis.html", {"request": request})


@router.get("/recommendations")
async def recommendations_page(request: Request):
    return templates.TemplateResponse("recommendations.html", {"request": request})


@router.get("/history")
async def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


@router.get("/profile")
async def profile(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})


@router.get("/signin")
async def signin(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/signup")
async def signup(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register")
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})
