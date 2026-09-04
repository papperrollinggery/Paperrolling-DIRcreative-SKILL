#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dircreative_route import classify_media_scope


CONTRACT_ID = "dircreative_request_scope_v1"
MAX_PACKET_BYTES = 256 * 1024
MAX_SOURCE_MESSAGES = 16
MAX_SOURCE_MESSAGE_CHARS = 32768
MAX_DELEGATED_PROMPT_CHARS = 65536
MAX_REQUIRED_METHODS = 16


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_packet(packet: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["request_scope_packet_must_be_object"]
    if packet.get("contract_id") != CONTRACT_ID:
        errors.append("request_scope_contract_id_invalid")
    messages = packet.get("source_messages")
    valid_messages: list[str] = []
    if not isinstance(messages, list) or not messages or len(messages) > MAX_SOURCE_MESSAGES:
        errors.append("source_messages_missing")
    else:
        seen: set[str] = set()
        for index, item in enumerate(messages):
            if not isinstance(item, dict):
                errors.append(f"source_message_invalid:{index}")
                continue
            message_id = item.get("message_id")
            text = item.get("text")
            digest = item.get("sha256")
            if not isinstance(message_id, str) or not message_id or message_id in seen:
                errors.append(f"source_message_id_invalid:{index}")
                continue
            seen.add(message_id)
            if not isinstance(text, str) or not text.strip():
                errors.append(f"source_message_text_missing:{message_id}")
                continue
            if len(text) > MAX_SOURCE_MESSAGE_CHARS:
                errors.append(f"source_message_too_large:{message_id}")
                continue
            valid_messages.append(text)
            if digest != _sha256_text(text):
                errors.append(f"source_message_hash_mismatch:{message_id}")
    delegated = packet.get("delegated_prompt")
    if not isinstance(delegated, str) or not delegated.strip():
        errors.append("delegated_prompt_missing")
        delegated = ""
    elif len(delegated) > MAX_DELEGATED_PROMPT_CHARS:
        errors.append("delegated_prompt_too_large")
        delegated = ""
    elif packet.get("delegated_prompt_sha256") != _sha256_text(delegated):
        errors.append("delegated_prompt_hash_mismatch")

    source_scope = classify_media_scope("\n".join(valid_messages))
    delegated_scope = classify_media_scope(delegated)
    declared = packet.get("declared_scope")
    declared_fields = (
        "media_scope",
        "image_generation_authorized",
        "video_generation_authorized",
    )
    if not isinstance(declared, dict) or any(field not in declared for field in declared_fields):
        errors.append("declared_scope_missing")
    else:
        if any(declared.get(field) != source_scope.get(field) for field in declared_fields):
            errors.append("declared_scope_mismatch")
        if any(delegated_scope.get(field) != source_scope.get(field) for field in declared_fields):
            errors.append("delegated_media_scope_mismatch")
    if valid_messages and any(text not in delegated for text in valid_messages):
        errors.append("source_scope_excerpt_missing_from_delegation")
    required_methods = packet.get("required_methods", [])
    if (
        not isinstance(required_methods, list)
        or len(required_methods) > MAX_REQUIRED_METHODS
        or not all(
        isinstance(item, str) and 0 < len(item) <= 64 for item in required_methods
        )
    ):
        errors.append("required_methods_invalid")
    else:
        delegated_lower = delegated.lower()
        for method in required_methods:
            if method.lower() not in delegated_lower:
                errors.append(f"required_method_missing:{method}")
    return list(dict.fromkeys(errors))


def assess_packet(packet: Any) -> dict[str, Any]:
    errors = validate_packet(packet)
    return {
        "scope_consistency_status": "pass" if not errors else "fail",
        "source_provenance": "unverified",
        "authorization_authority": "none",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that a delegated DIRcreative task preserves user scope verbatim.")
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        if args.packet.stat().st_size > MAX_PACKET_BYTES:
            raise ValueError("packet_too_large")
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        assessment = assess_packet(packet)
        errors = assessment["errors"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        errors = [f"packet_unreadable:{type(exc).__name__}"]
        assessment = {
            "scope_consistency_status": "fail",
            "source_provenance": "unverified",
            "authorization_authority": "none",
            "errors": errors,
        }
    print(json.dumps(assessment, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
