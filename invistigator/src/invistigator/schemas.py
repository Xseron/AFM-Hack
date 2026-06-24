from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    usernames: list[str]


class ProfileData(BaseModel):
    username: str
    full_name: str | None = None
    biography: str | None = None
    external_url: str | None = None
    profile_pic: str = ""           # локальный путь или URL
    followers: int | None = None
    is_private: bool = False
    telegram_links: list[str] = []
    tg_triggered: str = "no"        # "yes" | "no" | "error"
    status: str = "ok"              # ok | private | not_found | rate_limited | error
    scraped_at: str = ""


class AcceptedResponse(BaseModel):
    job_id: str
    accepted: int


class JobStatus(BaseModel):
    job_id: str
    status: str                 # running | done
    accepted: int
    done: int
    results: list[ProfileData]
