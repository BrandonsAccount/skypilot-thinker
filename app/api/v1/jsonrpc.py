#!/usr/bin/env python3
from fastapi import APIRouter, Depends, HTTPException, Request
from services import openai
from lib.skylogger.skypilot_logger import fancy_logger
import json
from lib.schema_validator.validator import validate_or_400

router = APIRouter()
log = fancy_logger(__name__)

@router.post("/jsonrpc")
async def jsonrpc(request: Request):

    body_bytes = await request.body()
    body_string = body_bytes.decode("utf-8")
    request_info = (
        f"Method: {request.method}\n"
        f"URL: {request.url}\n"
        f"Headers: {dict(request.headers)}\n"
        f"Body: {body_string}"
    )
    log.info(f"Received request: \n {request_info}")

    # Extract and format request details
    try:
        body_bytes = await request.body()
        envelope = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        log.error("body is not valid JSON")
        return 400, {"error": "body must be valid JSON"}

    # Normalize+validate (params string → dict, then JSON Schema validate)
    status, payload = validate_or_400(envelope)
    if status != 200:
        return status, payload

    return await openai.process(request)