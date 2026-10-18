import time
import uuid
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Middleware Composition Service")

STUDENT_EMAIL = "25f2004578@ds.study.iitm.ac.in"
ALLOWED_CORS_ORIGIN = "https://app-4aq0zr.example.com"
RATE_LIMIT_BUCKET = 12
WINDOW_SECONDS = 10.0

rate_limit_records: Dict[str, List[float]] = defaultdict(list)


def is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin == ALLOWED_CORS_ORIGIN:
        return True
    if "sanand.workers.dev" in origin or "workers.dev" in origin:
        return True
    if "iitm.ac.in" in origin or "localhost" in origin or "127.0.0.1" in origin:
        return True
    return False


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get("x-client-id") or (
        request.client.host if request.client else "anonymous"
    )
    now = time.time()

    bucket = [t for t in rate_limit_records[client_id] if now - t < WINDOW_SECONDS]

    if len(bucket) >= RATE_LIMIT_BUCKET:
        rate_limit_records[client_id] = bucket
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})

    bucket.append(now)
    rate_limit_records[client_id] = bucket
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_CORS_ORIGIN, "https://sanand.workers.dev"],
    allow_origin_regex=r"https://.*\.workers\.dev",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=86400,
)


@app.middleware("http")
async def context_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id")
    request_id = incoming if incoming else str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    origin = request.headers.get("origin")
    if origin and is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"

    return response


@app.options("/ping")
async def ping_options(request: Request):
    origin = request.headers.get("origin", "")
    headers = {
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": request.headers.get(
            "access-control-request-headers", "X-Request-ID, X-Client-Id"
        ),
        "Access-Control-Max-Age": "86400",
    }
    if is_allowed_origin(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Expose-Headers"] = "X-Request-ID"
    return Response(status_code=200, headers=headers)


@app.get("/ping")
async def ping(request: Request):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"email": STUDENT_EMAIL, "request_id": req_id}


@app.get("/")
async def root():
    return {"status": "ok"}
