"""Dograh subclass of pipecat's Gemini Live LLM service.

Layers Dograh engine integration quirks onto upstream-pristine
:class:`GeminiLiveLLMService`:

- **Deferred connect.** Connection is held back until ``system_instruction``
  is set via :meth:`_update_settings`, so pre-call-fetch template variables
  land before the live session opens.
- **Reconnect on node transitions.** Gemini Live cannot update
  ``system_instruction`` mid-session, so a setting change triggers a
  reconnect (deferred until the bot turn ends if currently responding).
- **Function-call deferral.** Tool calls emitted mid-turn are queued and run
  when the bot stops speaking, to avoid racing the turn's audio.
- **User-mute audio gating.** ``UserMuteStarted/StoppedFrame`` from the
  user aggregator gates whether incoming audio is forwarded to Gemini.
- **TTSSpeakFrame as greeting trigger.** The engine queues a TTSSpeakFrame
  to kick off the first response after node setup; the service intercepts
  it and runs the initial-context path.
"""

from typing import Any

from loguru import logger

from api.services.pipecat.gemini_json_schema_adapter import (
    DograhGeminiJSONSchemaAdapter,
)
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    Frame,
    TTSSpeakFrame,
    UserMuteStartedFrame,
    UserMuteStoppedFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessorSetup
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, LLMSettings
from pipecat.services.llm_service import FunctionCallFromLLM
from pipecat.utils.tracing.service_decorators import traced_gemini_live


class DograhGeminiLiveLLMService(GeminiLiveLLMService):
    """Gemini Live with Dograh engine integration quirks. See module docstring."""

    # Route tool schemas through Gemini's ``parameters_json_schema`` field so
    # MCP/imported tools that use JSON Schema keywords (``const``, ``not``,
    # nested ``anyOf``) rejected by the strict ``Schema`` model are accepted.
    # Mirrors the non-realtime ``DograhGoogleLLMService`` fix;
    # ``DograhGeminiLiveVertexLLMService`` inherits this via MRO.
    adapter_class = DograhGeminiJSONSchemaAdapter

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # User-mute state, driven by broadcast UserMute{Started,Stopped}Frames.
        # Audio is not forwarded to Gemini while muted.
        self._user_is_muted: bool = False
        # Guards initial-response triggering against double-firing across the
        # initial TTSSpeakFrame and any LLMContextFrame that may arrive.
        self._handled_initial_context: bool = False
        # When a system_instruction change arrives mid-bot-turn, the reconnect
        # is queued and drained when the turn ends.
        self._reconnect_pending: bool = False
        # Function calls emitted by Gemini mid-bot-turn are deferred here and
        # invoked when the turn ends, so they don't race the turn's audio.
        self._pending_function_calls: list[FunctionCallFromLLM] = []

    # ------------------------------------------------------------------
    # Deferred connect: block setup()'s unconditional _connect() until the
    # engine sets a system_instruction (so template variables land first).
    # Override _update_settings() to reconnect when system_instruction changes,
    # because pipecat 1.9.1 does not call _handle_changed_settings() from
    # _update_settings() — it only warns about unhandled changes.
    # ------------------------------------------------------------------

    async def setup(self, setup: FrameProcessorSetup):
        # Skip the parent's immediate _connect(); we connect once the engine
        # calls _update_settings(system_instruction=...) below.
        await super(GeminiLiveLLMService, self).setup(setup)

    async def _update_settings(self, delta: LLMSettings) -> dict[str, Any]:
        # Bypass GeminiLiveLLMService._update_settings (which warns about every
        # changed field including system_instruction) and call ai_service's
        # implementation directly to just apply the delta and get the changed dict.
        changed = await super(GeminiLiveLLMService, self)._update_settings(delta)
        if not changed:
            return changed
        if "system_instruction" in changed:
            if not self._session:
                await self._connect()
            elif self._bot_is_responding:
                self._reconnect_pending = True
            else:
                await self._reconnect()
            other = {k: v for k, v in changed.items() if k != "system_instruction"}
            if other:
                self._warn_unhandled_updated_settings(other)
        else:
            self._warn_unhandled_updated_settings(changed)
        return changed

    async def _run_or_defer_function_calls(
        self, function_calls_llm: list[FunctionCallFromLLM]
    ):
        if self._bot_is_responding:
            # Latest batch wins; Gemini emits tool calls as one batch per
            # tool_call message, so this overwrite is intentional.
            self._pending_function_calls = function_calls_llm
            logger.debug(
                f"{self}: deferring {len(function_calls_llm)} function call(s) "
                "until bot turn ends"
            )
            return
        await super()._run_or_defer_function_calls(function_calls_llm)

    # ------------------------------------------------------------------
    # State-transition side effects
    # ------------------------------------------------------------------

    async def _set_bot_is_responding(self, responding: bool):
        was_responding = self._bot_is_responding
        await super()._set_bot_is_responding(responding)
        if was_responding and not responding:
            await self._run_pending_function_calls()
            if self._reconnect_pending:
                self._reconnect_pending = False
                await self._reconnect()

    async def _run_pending_function_calls(self):
        """Run any function calls deferred during the bot's last turn."""
        if not self._pending_function_calls:
            return
        fcs = self._pending_function_calls
        self._pending_function_calls = []
        logger.debug(
            f"{self}: executing {len(fcs)} deferred function call(s) "
            "after bot turn ended"
        )
        await self.run_function_calls(fcs)

    async def _drain_pending_tool_results(self):
        # pipecat 1.9.1 does not have this base-class method; stub it out so
        # _handle_session_ready doesn't crash on reconnect/session-ready.
        pass

    # ------------------------------------------------------------------
    # Frame handling: mute, TTSSpeakFrame, BotStoppedSpeakingFrame flush
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, UserMuteStartedFrame):
            self._user_is_muted = True
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, UserMuteStoppedFrame):
            self._user_is_muted = False
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, TTSSpeakFrame):
            # Greeting trigger: the engine queues a TTSSpeakFrame to start the
            # bot's first turn after node setup. Gemini Live renders its own
            # audio, so we don't pass the frame through — we re-enter
            # _handle_context to kick off the initial response.
            if not self._handled_initial_context:
                await self._handle_context(self._context)
            else:
                logger.warning(
                    f"{self}: TTSSpeakFrame after initial context already "
                    "handled — Gemini Live owns audio generation, ignoring"
                )
            return
        if isinstance(frame, BotStoppedSpeakingFrame):
            # Belt-and-suspenders: the main drain happens in
            # _set_bot_is_responding(False), but if Gemini delays turn_complete
            # past the audible end of the turn, flushing here ensures pending
            # function calls fire promptly.
            await self._run_pending_function_calls()
            # Fall through to super for the actual push.
        await super().process_frame(frame, direction)

    async def _send_user_audio(self, frame):
        if self._user_is_muted:
            return
        await super()._send_user_audio(frame)

    # ------------------------------------------------------------------
    # Context lifecycle: Dograh pre-populates self._context via the engine,
    # so upstream's "first arrival === self._context is None" check doesn't
    # work. We gate on _handled_initial_context instead and skip the
    # init-instruction reconciliation (Dograh updates system_instruction at
    # runtime via _update_settings, not via init).
    # ------------------------------------------------------------------

    async def _handle_context(self, context: LLMContext):
        if not self._handled_initial_context:
            self._handled_initial_context = True
            self._context = context
            await self._create_initial_response()
        else:
            self._context = context
            await self._process_completed_function_calls(send_new_results=True)

    # ------------------------------------------------------------------
    # Session lifecycle: mirror the upstream _handle_session_ready cases so
    # that node-transition reconnects re-seed conversation history and trigger
    # Gemini to continue speaking (instead of waiting for user input).
    # ------------------------------------------------------------------

    @traced_gemini_live(operation="llm_setup")
    async def _handle_session_ready(self, session):
        logger.debug(
            f"In _handle_session_ready self._run_llm_when_session_ready: {self._run_llm_when_session_ready}"
        )
        self._session = session
        if self._run_llm_when_session_ready:
            # Initial connection: context arrived before session was ready.
            self._run_llm_when_session_ready = False
            await self._create_initial_response()
        elif self._session_resumption_handle:
            # Reconnect with session resumption: server restores state.
            self._ready_for_realtime_input = True
        elif self._context:
            # Node-transition reconnect (no resumption handle): re-seed
            # conversation history so the new session has full context.
            # _create_initial_response sets _ready_for_realtime_input internally.
            await self._create_initial_response(for_reconnect=True)
        else:
            # Initial connection before context arrives — wait for context.
            pass
        await self._drain_pending_tool_results()
        logger.debug("_handle_session_ready complete")

    async def _create_initial_response(self, for_reconnect: bool = False):
        await super()._create_initial_response(for_reconnect=for_reconnect)
        # Gemini 3.x reconnects: base class seeds history but sets
        # trigger_inference=False (waits for user to speak). For node
        # transitions we want Gemini to continue the conversation proactively,
        # so nudge it to generate a response now.
        if for_reconnect and self._is_gemini_3 and self._session and not self._disconnecting:
            await self._session.send_realtime_input(text=" ")
