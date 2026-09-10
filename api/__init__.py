"""
Inject stubs for dograh-private pipecat modules before any api.* import
triggers pipecat imports. These modules exist only in the dograh fork;
public pipecat-ai/pipecat does not have them.
"""
import sys
import types
from contextvars import ContextVar
from enum import Enum


def _ensure_module(dotted_name: str) -> types.ModuleType:
    """Return existing module or create an empty one, registered in sys.modules."""
    if dotted_name in sys.modules:
        return sys.modules[dotted_name]
    parts = dotted_name.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
            if i > 1:
                parent_name = ".".join(parts[: i - 1])
                setattr(sys.modules[parent_name], parts[i - 1], mod)
    return sys.modules[dotted_name]


# ── pipecat.utils.run_context ────────────────────────────────────────────────
if "pipecat.utils.run_context" not in sys.modules:
    _rc = _ensure_module("pipecat.utils.run_context")

    run_id_var: ContextVar = ContextVar("run_id", default=None)
    turn_var: ContextVar = ContextVar("turn", default=None)
    _org_id_var: ContextVar = ContextVar("org_id", default=None)

    def set_current_run_id(v):
        run_id_var.set(v)

    def set_current_org_id(v):
        _org_id_var.set(v)

    _rc.run_id_var = run_id_var
    _rc.turn_var = turn_var
    _rc.set_current_run_id = set_current_run_id
    _rc.set_current_org_id = set_current_org_id

# ── pipecat.utils.enums ──────────────────────────────────────────────────────
if "pipecat.utils.enums" not in sys.modules:
    _enums = _ensure_module("pipecat.utils.enums")

    class EndTaskReason(str, Enum):
        CALL_DURATION_EXCEEDED = "call_duration_exceeded"
        END_CALL_TOOL_REASON = "end_call_tool_reason"
        PIPELINE_ERROR = "pipeline_error"
        TRANSFER_CALL = "transfer_call"
        UNEXPECTED_ERROR = "unexpected_error"
        USER_HANGUP = "user_hangup"
        USER_IDLE_MAX_DURATION_EXCEEDED = "user_idle_max_duration_exceeded"
        USER_QUALIFIED = "user_qualified"
        VOICEMAIL_DETECTED = "voicemail_detected"

    class RealtimeFeedbackType(str, Enum):
        BOT_STARTED_SPEAKING = "bot_started_speaking"
        BOT_STOPPED_SPEAKING = "bot_stopped_speaking"
        BOT_TEXT = "bot_text"
        FUNCTION_CALL_END = "function_call_end"
        FUNCTION_CALL_START = "function_call_start"
        LATENCY_MEASURED = "latency_measured"
        NODE_TRANSITION = "node_transition"
        PIPELINE_ERROR = "pipeline_error"
        TTFB_METRIC = "ttfb_metric"
        USER_MUTE_STARTED = "user_mute_started"
        USER_MUTE_STOPPED = "user_mute_stopped"
        USER_TRANSCRIPTION = "user_transcription"

    _enums.EndTaskReason = EndTaskReason
    _enums.RealtimeFeedbackType = RealtimeFeedbackType

# ── pipecat.utils.context.message_sanitization ───────────────────────────────
if "pipecat.utils.context.message_sanitization" not in sys.modules:
    _ms = _ensure_module("pipecat.utils.context.message_sanitization")

    def strip_thought_ids_from_messages(messages):
        return messages

    _ms.strip_thought_ids_from_messages = strip_thought_ids_from_messages
