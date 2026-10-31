from pydantic import BaseModel, Field

from f1pred.config import PIT_LOSS_S


class PitRequest(BaseModel):
    current_lap: int = Field(ge=1)
    total_laps: int = Field(ge=1)
    current_compound: str
    current_tyre_life: int = Field(ge=1)
    new_compound: str
    pit_loss_s: float = Field(default=PIT_LOSS_S, ge=0)