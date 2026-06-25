from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    usernames: list[str]


class OsintData(BaseModel):
    # контакты (regex из biography + full_name)
    phones: list[str] = []
    emails: list[str] = []
    whatsapp: list[str] = []
    crypto_wallets: list[str] = []
    other_socials: list[str] = []
    # домен (из external_url / link-in-bio)
    final_url: str | None = None
    domain: str | None = None
    domain_age_days: int | None = None
    registrar: str | None = None
    nameservers: list[str] = []
    redirect_chain: list[str] = []
    page_title: str | None = None
    # username по платформам
    accounts_found: list[str] = []
    # image
    avatar_phash: str | None = None
    reverse_image_url: str | None = None
    osint_error: str | None = None


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
    osint: OsintData | None = None


class AcceptedResponse(BaseModel):
    job_id: str
    accepted: int


class JobStatus(BaseModel):
    job_id: str
    status: str                 # running | done
    accepted: int
    done: int
    results: list[ProfileData]


class GraphNode(BaseModel):
    id: str                     # "account:<username>" | "<kind>:<value>"
    type: str                   # account | domain | telegram | phone | email | wallet | social | avatar
    label: str
    data: dict = {}


class GraphEdge(BaseModel):
    source: str                 # account id
    target: str                 # attribute id
    kind: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
