from typing import Literal, Optional, TypedDict


ihaAPIVideoStatus = Literal["live", "upcoming", "past", "video"]
ihaAPIVideoPlatform = Literal["youtube", "twitch", "twitter", "twitcasting", "mildom"]


class _ihaAPIVTuberTimeData(TypedDict):
    startTime: Optional[int]
    scheduledStartTime: Optional[int]
    endTime: Optional[int]


class ihaAPIVTuberVideo(TypedDict):
    id: str
    title: str
    status: ihaAPIVideoStatus
    channel_id: str
    timeData: _ihaAPIVTuberTimeData
    platform: ihaAPIVideoPlatform
    is_premiere: bool
    is_member: bool
