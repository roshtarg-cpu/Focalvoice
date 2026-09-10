"""
Inject stubs for dograh-private pipecat modules before any api.* import
triggers pipecat imports. These modules exist only in dograh's private pipecat
fork; public pipecat-ai/pipecat does not ship them.
"""
import sys
import types
from contextvars import ContextVar
from enum import Enum

# Load the real pipecat package FIRST so our stubs only fill gaps,
# never shadow the real installed package.
import pipecat  # noqa: F401


def _ensure_module(dotted_name: str) -> types.ModuleType:
    """Return existing module or create an empty one registered in sys.modules."""
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


def _stub(dotted_name: str, **attrs) -> None:
    """Create a stub module and set the given attributes on it."""
    mod = _ensure_module(dotted_name)
    for k, v in attrs.items():
        setattr(mod, k, v)


# ── pipecat.utils.run_context ────────────────────────────────────────────────
if "pipecat.utils.run_context" not in sys.modules:
    run_id_var: ContextVar = ContextVar("run_id", default=None)
    turn_var: ContextVar = ContextVar("turn", default=None)
    _org_id_var: ContextVar = ContextVar("org_id", default=None)

    def set_current_run_id(v):
        run_id_var.set(v)

    def set_current_org_id(v):
        _org_id_var.set(v)

    _stub(
        "pipecat.utils.run_context",
        run_id_var=run_id_var,
        turn_var=turn_var,
        set_current_run_id=set_current_run_id,
        set_current_org_id=set_current_org_id,
    )

# ── pipecat.utils.enums ──────────────────────────────────────────────────────
if "pipecat.utils.enums" not in sys.modules:
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

    _stub("pipecat.utils.enums", EndTaskReason=EndTaskReason, RealtimeFeedbackType=RealtimeFeedbackType)

# ── pipecat.utils.context.message_sanitization ───────────────────────────────
if "pipecat.utils.context.message_sanitization" not in sys.modules:
    def strip_thought_ids_from_messages(messages):
        return messages
    _stub("pipecat.utils.context.message_sanitization", strip_thought_ids_from_messages=strip_thought_ids_from_messages)

# ── pipecat.serializers.cloudonix ────────────────────────────────────────────
if "pipecat.serializers.cloudonix" not in sys.modules:
    try:
        from pipecat.serializers.twilio import TwilioFrameSerializer as _TwilioFS
        _stub("pipecat.serializers.cloudonix", CloudonixFrameSerializer=_TwilioFS)
    except Exception:
        class CloudonixFrameSerializer:
            """Stub — dograh-private cloudonix serializer not available."""
        _stub("pipecat.serializers.cloudonix", CloudonixFrameSerializer=CloudonixFrameSerializer)

# ── pipecat.turns.* ──────────────────────────────────────────────────────────
_turn_stubs = [
    "pipecat.turns",
    "pipecat.turns.user_mute",
    "pipecat.turns.user_start",
    "pipecat.turns.user_start.vad_user_turn_start_strategy",
    "pipecat.turns.user_stop",
    "pipecat.turns.user_turn_strategies",
]
for _m in _turn_stubs:
    _ensure_module(_m)

# pipecat.turns.user_mute
if not hasattr(sys.modules.get("pipecat.turns.user_mute", types.ModuleType("")), "CallbackUserMuteStrategy"):
    class CallbackUserMuteStrategy:
        """Stub."""
    class FunctionCallUserMuteStrategy:
        """Stub."""
    class MuteUntilFirstBotCompleteUserMuteStrategy:
        """Stub."""
    _stub("pipecat.turns.user_mute",
          CallbackUserMuteStrategy=CallbackUserMuteStrategy,
          FunctionCallUserMuteStrategy=FunctionCallUserMuteStrategy,
          MuteUntilFirstBotCompleteUserMuteStrategy=MuteUntilFirstBotCompleteUserMuteStrategy)

# pipecat.turns.user_start
if not hasattr(sys.modules.get("pipecat.turns.user_start", types.ModuleType("")), "ExternalUserTurnStartStrategy"):
    class ExternalUserTurnStartStrategy:
        """Stub."""
    class TranscriptionUserTurnStartStrategy:
        """Stub."""
    _stub("pipecat.turns.user_start",
          ExternalUserTurnStartStrategy=ExternalUserTurnStartStrategy,
          TranscriptionUserTurnStartStrategy=TranscriptionUserTurnStartStrategy)

# pipecat.turns.user_start.vad_user_turn_start_strategy
if not hasattr(sys.modules.get("pipecat.turns.user_start.vad_user_turn_start_strategy", types.ModuleType("")), "VADUserTurnStartStrategy"):
    class VADUserTurnStartStrategy:
        """Stub."""
    _stub("pipecat.turns.user_start.vad_user_turn_start_strategy",
          VADUserTurnStartStrategy=VADUserTurnStartStrategy)

# pipecat.turns.user_stop
if not hasattr(sys.modules.get("pipecat.turns.user_stop", types.ModuleType("")), "ExternalUserTurnStopStrategy"):
    class ExternalUserTurnStopStrategy:
        """Stub."""
    class SpeechTimeoutUserTurnStopStrategy:
        """Stub."""
    class TurnAnalyzerUserTurnStopStrategy:
        """Stub."""
    _stub("pipecat.turns.user_stop",
          ExternalUserTurnStopStrategy=ExternalUserTurnStopStrategy,
          SpeechTimeoutUserTurnStopStrategy=SpeechTimeoutUserTurnStopStrategy,
          TurnAnalyzerUserTurnStopStrategy=TurnAnalyzerUserTurnStopStrategy)

# pipecat.turns.user_turn_strategies
if not hasattr(sys.modules.get("pipecat.turns.user_turn_strategies", types.ModuleType("")), "UserTurnStrategies"):
    class UserTurnStrategies:
        """Stub."""
    _stub("pipecat.turns.user_turn_strategies", UserTurnStrategies=UserTurnStrategies)

# ── pipecat.workers.runner ───────────────────────────────────────────────────
if "pipecat.workers.runner" not in sys.modules:
    class WorkerRunner:
        """Stub."""
    _ensure_module("pipecat.workers")
    _stub("pipecat.workers.runner", WorkerRunner=WorkerRunner)

# ── pipecat.extensions.voicemail.voicemail_detector ─────────────────────────
if "pipecat.extensions.voicemail.voicemail_detector" not in sys.modules:
    class VoicemailDetector:
        """Stub."""
    _ensure_module("pipecat.extensions")
    _ensure_module("pipecat.extensions.voicemail")
    _stub("pipecat.extensions.voicemail.voicemail_detector", VoicemailDetector=VoicemailDetector)

# ── pipecat.audio.turn.smart_turn.local_smart_turn_v3 ───────────────────────
if "pipecat.audio.turn.smart_turn.local_smart_turn_v3" not in sys.modules:
    class LocalSmartTurnAnalyzerV3:
        """Stub."""
    _ensure_module("pipecat.audio.turn")
    _ensure_module("pipecat.audio.turn.smart_turn")
    _stub("pipecat.audio.turn.smart_turn.local_smart_turn_v3",
          LocalSmartTurnAnalyzerV3=LocalSmartTurnAnalyzerV3)

# ── pipecat.audio.turn.smart_turn.base_smart_turn ───────────────────────────
if "pipecat.audio.turn.smart_turn.base_smart_turn" not in sys.modules:
    class SmartTurnParams:
        """Stub."""
    _stub("pipecat.audio.turn.smart_turn.base_smart_turn", SmartTurnParams=SmartTurnParams)

# ── pipecat.services.dograh.* ───────────────────────────────────────────────
_dograh_stubs = {
    "pipecat.services.dograh": {},
    "pipecat.services.dograh.flux": {},
    "pipecat.services.dograh.flux.stt": {"DograhFluxSTTService": type("DograhFluxSTTService", (), {})},
    "pipecat.services.dograh.llm": {"DograhLLMService": type("DograhLLMService", (), {})},
    "pipecat.services.dograh.stt": {
        "DograhSTTService": type("DograhSTTService", (), {}),
        "DograhSTTSettings": type("DograhSTTSettings", (), {}),
    },
    "pipecat.services.dograh.tts": {
        "DograhTTSService": type("DograhTTSService", (), {}),
        "DograhTTSSettings": type("DograhTTSSettings", (), {}),
    },
}
for _mod, _attrs in _dograh_stubs.items():
    if _mod not in sys.modules:
        _stub(_mod, **_attrs)

# ── pipecat.services.deepgram.flux.stt (optional) ───────────────────────────
if "pipecat.services.deepgram.flux" not in sys.modules:
    _ensure_module("pipecat.services.deepgram.flux")
    _stub("pipecat.services.deepgram.flux.stt",
          DeepgramFluxSTTService=type("DeepgramFluxSTTService", (), {}),
          DeepgramFluxSTTSettings=type("DeepgramFluxSTTSettings", (), {}))
