from datetime import datetime

from pydantic import BaseModel
from pydantic.types import PositiveInt

from typing import List
from typing_extensions import Annotated

from pydantic import StringConstraints

class Channel(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1)]
    num_samples: PositiveInt
    sample_frequency: PositiveInt
    factor: float
    signal: list[int] = None


class Device(BaseModel):
    name: str | None = 'N/A'
    company: str | None = 'N/A'
    firmware: str | None = '1.0.0'
    serial_number: str | None = ''


class HolterCreate(BaseModel):
    date: datetime
    device: "Device"
    channels: List[Channel]

    class Config:
        json_encoders = {
            datetime: lambda value: value.strftime('%Y-%m-%dT%H:%M:%S')
        }
