import json
import os

from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import load_config
from server.routers import api_v1

load_dotenv()  # Load environment variables from .env

SERVER_PORT = os.getenv("SERVER_PORT", 8000)

app = FastAPI()

app.include_router(api_v1.router)
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


# Serve index.html
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with open("logs/app.log", "r") as file:
        logs = []
        for line in file:
            logs.append(line.strip())
    return templates.TemplateResponse("index.html", {"request": request, "logs": logs})


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    amount = request.query_params.get("amount") or 30
    with open("logs/app.log", "r") as file:
        logs = []
        for line in file:
            logs.append(line.strip())
        logs = logs[-int(amount) :]
        logs.reverse()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "system_prompt": config["system_prompt"].strip(),
            "silence_threshold": config["silence_threshold"],
            "silence_duration": config["silence_duration"],
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    history = []
    if os.path.exists("logs/history.log"):
        with open("logs/history.log", "r") as file:
            history = json.load(file)

    return templates.TemplateResponse(
        "history.html", {"request": request, "history": history}
    )


def start_server():
    uvicorn.run("server:app", host="0.0.0.0", port=SERVER_PORT)
