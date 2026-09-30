"""Fail-closed input-integrity contract for benchmark records.

The classifier does not infer server tokenization from client text or response
length.  Missing server-side evidence remains ``unknown``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


IntegrityStatus = Literal["sent", "server_tokenized", "truncated", "delivered", "unknown"]


@dataclass(frozen=True)
class InputIntegrity:
    status: IntegrityStatus
    request_sent: bool
    server_tokenized: bool | None
    input_tokens_sent: int | None
    input_tokens_server: int | None
    truncated: bool | None
    response_complete: bool | None
    reason: str


def classify_input_integrity(
    *,
    request_sent: bool,
    server_tokenized: bool | None,
    input_tokens_sent: int | None = None,
    input_tokens_server: int | None = None,
    truncated: bool | None = None,
    response_complete: bool | None = None,
) -> InputIntegrity:
    """Classify evidence without filling unknown fields by inference."""
    if not isinstance(request_sent, bool):
        raise TypeError("request_sent must be bool")
    for name, value in (("input_tokens_sent", input_tokens_sent), ("input_tokens_server", input_tokens_server)):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{name} must be a nonnegative integer or None")
    for name, value in (("server_tokenized", server_tokenized), ("truncated", truncated), ("response_complete", response_complete)):
        if value is not None and type(value) is not bool:
            raise TypeError(f"{name} must be bool or None")
    if not request_sent:
        return InputIntegrity("unknown", False, server_tokenized, input_tokens_sent, input_tokens_server, truncated, response_complete, "request_not_sent")
    if server_tokenized is None:
        return InputIntegrity("unknown", True, None, input_tokens_sent, input_tokens_server, truncated, response_complete, "server_tokenization_unknown")
    if truncated is True:
        return InputIntegrity("truncated", True, server_tokenized, input_tokens_sent, input_tokens_server, True, response_complete, "server_reported_truncation")
    if response_complete is True and server_tokenized is True:
        if truncated is not False:
            return InputIntegrity("server_tokenized", True, True, input_tokens_sent, input_tokens_server, truncated, True, "truncation_status_unknown")
        return InputIntegrity("delivered", True, True, input_tokens_sent, input_tokens_server, False, True, "complete_response_without_truncation_signal")
    if server_tokenized is True:
        return InputIntegrity("server_tokenized", True, True, input_tokens_sent, input_tokens_server, truncated, response_complete, "server_tokenization_observed")
    return InputIntegrity("sent", True, False, input_tokens_sent, input_tokens_server, truncated, response_complete, "request_sent_without_server_tokenization")
