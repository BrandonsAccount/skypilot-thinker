import os, json
from lib.skylogger.skypilot_logger import fancy_logger
from typing import Any, Dict, Optional, Union
from fastapi import FastAPI, Request
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY from env
supported_models = os.getenv("OPENAI_SUPPORTED_MODELS")
log = fancy_logger(__name__)

def jsonrpc_error(code: int, message: str, request_id: Optional[Union[str, int]] = None, data: Any = None):
    """Wrap an error in a JSON-RPC 2.0 response envelope."""
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": err}

def jsonrpc_result(request_id: Optional[Union[str, int]], result: Any):
    """Wrap a successful result in a JSON-RPC 2.0 response envelope."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}

async def process(request: Request):
    body: Dict[str, Any] = await request.json()
    request_id = body.get("id")

    params = body.get("params") or {}
    params_json = json.loads(params)

    # ensure our provider is configured to support the requested model
    llm = params_json.get("llm")
    if llm not in supported_models.split(","):
        return jsonrpc_error(-32001, f"Unsupported LLM {llm!r}", request_id)

    # parse the output schema from params. if it's a dict, use it directly; if it's a string, parse it as JSON
    output_schema = params_json.get("output_schema")
    schema = output_schema if isinstance(output_schema, dict) else json.loads(output_schema)

    # use your prompt field if present; otherwise fall back to the whole params blob
    # user_text = params.get("prompt") or json.dumps(params)
    try:
        resp = client.chat.completions.create(
            model=llm,
            messages=[{"role": "system", "content": params},],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Reply", "schema": schema, "strict": False}
            },
        )
        obj = json.loads(resp.choices[0].message.content)
        return jsonrpc_result(request_id, obj)
    except Exception as e:
        log.error("LLM call failed")
        return jsonrpc_error(-32000, "LLM invocation failed", request_id, data=str(e))