"""Vobiz frame serializer.

Vobiz uses a Plivo-compatible protocol; fall back to pipecat's public
Plivo serializer when the dograh-private Vobiz serializer is unavailable.
"""

try:
    from pipecat.serializers.vobiz import VobizFrameSerializer
except ImportError:
    from pipecat.serializers.plivo import PlivoFrameSerializer as VobizFrameSerializer  # noqa: F401

__all__ = ["VobizFrameSerializer"]
