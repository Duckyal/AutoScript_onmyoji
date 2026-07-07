# api/ui.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from module import adb_stream
import time

import requests


router = APIRouter()
templates = Jinja2Templates(directory="static")

@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "time_now": time.time()})

@router.get("/api/wallpaper")
async def wallpaper():
    """
    直接抓取官网，找到最新的 1920x1080 横屏壁纸
    """
    url = 'https://yys.163.com/media/picture.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    html = requests.get(url, headers=headers, timeout=10).text

    import re
    # 优先横版高清
    m = (re.search(r'https://yys\.res\.netease\.com[^"\'\s]*?1920x1080\.jpg' , html)
         or re.search(r'https://yys\.res\.netease\.com[^"\'\s]*?\.jpg' , html))
    return {"url": m.group(0) if m else ""}


@router.get("/home")
async def home(request: Request, device: str):
    ok, msg = adb_stream.check_adb(device)
    return templates.TemplateResponse("home.html", {
        "request": request, "time_now": time.time(),
        "device": device, "device_ok": ok, "device_msg": msg
    })

@router.get("/dev")
async def dev(request: Request, device: str):
    ok, msg = adb_stream.check_adb(device)
    return templates.TemplateResponse("dev.html", {
        "request": request, "time_now": time.time(),
        "device": device, "device_ok": ok, "device_msg": msg
    })
