import datetime
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import Config, load_config, save_config


router = APIRouter(prefix="/api/v1")


@router.get("/")
def info():
    return {
        "version": "1.0.0",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/config")
def get_config():
    return load_config()


@router.post("/config")
async def post_config(request: Request):
    config: Config = load_config()

    html = request.query_params.get("html")
    system_prompt = None
    silence_threshold = None
    silence_duration = None

    if request.headers.get("Content-Type") == "application/json":
        data = request.json()
        config.update(data)
    else:
        data = await request.form()

        system_prompt = data.get("system_prompt")
        silence_threshold = float(data.get("silence_threshold"))
        silence_duration = float(data.get("silence_duration"))

        config.update(
            {
                "system_prompt": system_prompt,
                "silence_threshold": silence_threshold,
                "silence_duration": silence_duration,
            }
        )

    try:
        system_prompt = system_prompt.strip()
        save_config(config)

        if not html:
            return {"success": True, "message": "Config updated successfully."}
        else:
            return HTMLResponse(
                """
                <div class="flex w-full justify-center">
                    <p class='color-green text-lg'>Updated!</p>
                </div>
            """
            )
    except:
        if not html:
            return {"error": "An error occurred while updating the config."}
        else:
            return "<p>Failed to update config!</p>"


@router.get("/logs")
def get_logs(amount: Optional[int] = 20):
    with open("logs/app.log", "r") as file:
        logs = []
        for line in file:
            logs.append(line.strip())

        if amount:
            logs = logs[-amount:]
        return {"logs": logs}


@router.get("/history")
def get_history():
    with open("logs/history.log", "r") as file:
        return {"history": file.read()}
