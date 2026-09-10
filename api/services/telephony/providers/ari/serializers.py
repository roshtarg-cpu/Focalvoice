"""Asterisk frame serializer (re-exported from pipecat)."""

try:
    from pipecat.serializers.asterisk import AsteriskFrameSerializer
except (ImportError, ModuleNotFoundError):
    class AsteriskFrameSerializer:
        """Stub — pipecat.serializers.asterisk not available."""
        pass

__all__ = ["AsteriskFrameSerializer"]
