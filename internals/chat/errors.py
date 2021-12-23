class ChatDownloaderError(Exception):
    """Base class for Chat Downloader errors."""


class VideoUnavailable(ChatDownloaderError):
    """Raised when video is unavailable."""

    pass


class LoginRequired(ChatDownloaderError):
    """Raised when video is login is required (e.g. if video is private)."""

    pass


class VideoUnplayable(ChatDownloaderError):
    """Raised when video is unplayable (e.g. if video is members-only)."""

    pass


class NoChatReplay(ChatDownloaderError):
    """Raised when the video does not contain a chat replay."""

    pass


class ChatDisabled(ChatDownloaderError):
    """Raised when the video does not contain a chat replay."""

    pass
