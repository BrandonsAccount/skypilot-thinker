#!/usr/bin/env python3
from fastapi import APIRouter, Depends, HTTPException, Request
from services import openai
from typing import Any, Optional, Union
from lib.skyhelper_logger.skyhelper_logger import fancy_logger
import json
from lib.schema_validator.validator import validate_or_400

router = APIRouter()
log = fancy_logger(__name__)

def jsonrpc_error(code: int, message: str, request_id: Optional[Union[str, int]] = None, data: Any = None):
    """Wrap an error in a JSON-RPC 2.0 response envelope."""
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": err}

# def jsonrpc_result(request_id: Optional[Union[str, int]], result: Any):
#     """Wrap a successful result in a JSON-RPC 2.0 response envelope."""
#     return {"jsonrpc": "2.0", "id": request_id, "result": result}

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
    log.waiting("Received request... Validating...")

    # Extract and format request details
    try:
        body_bytes = await request.body()
        envelope = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        log.error("body is not valid JSON")
        return jsonrpc_error(-32700, "Parse error: body is not valid JSON")

    # validate the request body against our schema to ensure we are getting a consistent payload.
    status, payload = validate_or_400(envelope)
    if status != 200:
        return jsonrpc_error(400, "Invalid Request", envelope.get("id"), data=payload)

    return await openai.process(request)