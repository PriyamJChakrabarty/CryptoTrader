from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai.chat_models import base as _lc_oai_base

logger = logging.getLogger(__name__)

_PATCH_FLAG = "_cryptotrader_reasoning_patch_applied"


def _wrap_convert_dict_to_message(original):
    def wrapped(_dict: Mapping[str, Any]) -> BaseMessage:
        msg = original(_dict)
        if isinstance(msg, AIMessage) and "reasoning_content" in _dict:
            rc = _dict.get("reasoning_content")
            if rc:
                msg.additional_kwargs["reasoning_content"] = rc
        return msg

    return wrapped


def _wrap_convert_message_to_dict(original):
    def wrapped(message: BaseMessage, api: str = "chat/completions") -> dict[str, Any]:
        out = original(message, api=api)
        if isinstance(message, AIMessage):
            rc = message.additional_kwargs.get("reasoning_content")
            if rc:
                out["reasoning_content"] = rc
        return out

    return wrapped


def apply_patch() -> None:
    if getattr(_lc_oai_base, _PATCH_FLAG, False):
        return

    _lc_oai_base._convert_dict_to_message = _wrap_convert_dict_to_message(  # type: ignore[attr-defined]
        _lc_oai_base._convert_dict_to_message
    )
    _lc_oai_base._convert_message_to_dict = _wrap_convert_message_to_dict(  # type: ignore[attr-defined]
        _lc_oai_base._convert_message_to_dict
    )
    setattr(_lc_oai_base, _PATCH_FLAG, True)
    logger.debug("Applied langchain_openai reasoning_content round-trip patch")


apply_patch()
