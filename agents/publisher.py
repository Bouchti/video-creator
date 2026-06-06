"""Publishing boundary for future platform integrations."""


def publish_video(*args, **kwargs):
    """Reject publishing until a platform integration is configured."""
    raise NotImplementedError("Video publishing is not implemented")
