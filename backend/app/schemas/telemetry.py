from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class BaseTelemetryEvent(BaseModel):
    type: str
    sessionId: str | None = None
    clientTs: int | None = None
    payload: dict | None = None


class KeyIntervalEvent(BaseTelemetryEvent):
    type: Literal["key_interval"]
    payload: dict


class ResizeEvent(BaseTelemetryEvent):
    type: Literal["resize"]
    payload: dict | None = None


# Add other specific event types as needed. The union below is discriminated on
# the `type` field so Pydantic will pick the right model.
TelemetryEventSchema = TypeAdapter(
    Annotated[
        Union[KeyIntervalEvent, ResizeEvent, BaseTelemetryEvent],
        Field(discriminator="type"),
    ]
)

