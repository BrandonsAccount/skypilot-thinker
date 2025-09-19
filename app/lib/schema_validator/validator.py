"""
WHAT:
  Minimal validation entrypoint:
    - If envelope["params"] is a JSON string, parse it (normalization).
    - Validate the entire envelope against JSON Schema.
    - Return a normalized copy or a (400, error payload) you can send back.

WHY:
  Keep code light and push rules into a declarative schema.
"""

from __future__ import annotations
import json
from typing import Any, Dict, Tuple
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JSValidationError
from lib.skyhelper_logger.skyhelper_logger import fancy_logger

log = fancy_logger(__name__)

# WHAT: JSON Schema for Skypilot Thinker JSON-RPC envelope + nested params.
# WHY: Central, declarative source of truth that's easy to diff, document, and test.
ENVELOPE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://skypilot/schema/jsonrpc-envelope",
    "title": "Skypilot Thinker JSON-RPC Envelope",
    "type": "object",
    "additionalProperties": False,
    "required": ["jsonrpc", "method", "id", "params"],
    "properties": {
        "jsonrpc": {"const": "2.0"},
        "method":  {"const": "processMessage"},
        "id":      {"$ref": "#/$defs/uuidString"},
        "params":  {"$ref": "#/$defs/params"}
    },

    "$defs": {
        "uuidString": {
            "type": "string",
            "format": "uuid",
            # Safety net for older validators or missing format checkers
            "pattern": "^[0-9a-fA-F-]{36}$"
        },

        "nonEmptyString": {"type": "string", "minLength": 1},

        "timestampIso": {
            "type": "string",
            # Accepts "YYYY-MM-DDTHH:MM:SS(.fraction)?(Z|±hh:mm)?"
            "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?$"
        },

        "conversationItem": {
            "type": "object",
            "additionalProperties": False,
            "required": ["role", "content", "timestamp"],
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["user", "assistant", "system", "tool"]
                },
                "content": {"$ref": "#/$defs/nonEmptyString"},
                "timestamp": {"$ref": "#/$defs/timestampIso"}
            }
        },

        "instructionItem": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "text"],
            "properties": {
                "id":   {"$ref": "#/$defs/nonEmptyString"},
                "text": {"$ref": "#/$defs/nonEmptyString"}
            }
        },

        "params": {
            "type": "object",
            "additionalProperties": True,  # keep flexible for future fields
            "required": [
                "user_id", "session_id", "instructions",
                "options", "capabilities", "resources", "output_schema"
            ],
            "properties": {
                "user_id":     {"$ref": "#/$defs/nonEmptyString"},
                "session_id":  {"$ref": "#/$defs/nonEmptyString"},
                "prompt":      {"$ref": "#/$defs/nonEmptyString"},
                "llmprovider": {"$ref": "#/$defs/nonEmptyString"},
                "llm":      {"$ref": "#/$defs/nonEmptyString"},
                "user_profile": {"type": ["object", "null"]},
                "conversation": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/conversationItem"}
                },
                "instructions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/instructionItem"}
                },
                "options":      {"type": "object"},
                "capabilities": {"type": "object"},
                "resources":    {"type": "object"},

                # We don't deeply validate the caller-provided output schema,
                # but we enforce the essential shape and key requirements.
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "type": {"const": "object"},
                        "properties": {"type": "object"},
                        "required":   {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["type", "properties", "required"],
                    "allOf": [
                        { "properties": { "required": { "contains": { "const": "answer" }}}},
                        { "properties": { "required": { "contains": { "const": "confidence" }}}},
                        { "properties": { "required": { "contains": { "const": "citations" }}}},
                        { "properties": { "required": { "contains": { "const": "actions" }}}},
                        { "properties": { "required": { "contains": { "const": "debug" }}}}
                    ]
                }
            },
            # Require at least one of prompt or conversation (both allowed too)
            "anyOf": [
                {"required": ["prompt"]},
                {"required": ["conversation"]}
            ]
        }
    }
}

_validator = Draft202012Validator(ENVELOPE_SCHEMA, format_checker=FormatChecker())

def _normalize_params(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """WHAT: Parse params if it arrived as a JSON string. WHY: Your example input does this."""
    params = envelope.get("params")
    if isinstance(params, str):
        try:
            envelope = {**envelope, "params": json.loads(params)}
        except Exception as e:
            raise ValueError(f"params must be a JSON object or JSON string object: {e}") from e
    return envelope

def validate_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    WHAT:
      Normalize then validate. Raises JSValidationError or ValueError on failure.
    WHY:
      Single source of truth (schema), tiny Python maintenance surface.
    """
    if not isinstance(envelope, dict):
        raise ValueError("body must be a JSON object")

    env_norm = _normalize_params(envelope)

    # jsonschema raises first error; we collect them for better DX
    errors = sorted(_validator.iter_errors(env_norm), key=lambda e: e.path)
    if errors:
        # build a human-friendly list of dotted paths and messages
        details = []
        for e in errors:
            path = ".".join(str(p) for p in e.absolute_path) or "(root)"
            details.append(f"{path}: {e.message}")
        raise JSValidationError("\n".join(details))

    return env_norm

def validate_or_400(envelope: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    # WHAT: Handler-friendly wrapper: returns (status, body).
    try:
        payload = validate_envelope(envelope)
        log.success("validated request payload")
        return 200, payload
    except (JSValidationError, ValueError) as e:
        # emit a concise error with structured details
        msg = str(e)
        log.error("invalid request payload", details=msg)
        return 400, {"error": "invalid request payload", "details": msg.split("\n")}
