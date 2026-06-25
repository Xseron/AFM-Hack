import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import build_components, create_app, init_components


@pytest_asyncio.fixture
async def app_client(tmp_path):
    # _env_file=None keeps tests hermetic — ignore any local .env (e.g. a real
    # MW_MODELS_ENABLED=true) so the suite always runs the lightweight stub path.
    settings = Settings(
        _env_file=None,
        queue_backend="memory",
        database_url="sqlite+aiosqlite:///:memory:",
        storage_dir=str(tmp_path / "buffer"),
        models_enabled=False,
        # Point plugin discovery at an empty tmp dir so the suite is hermetic
        # (never picks up checker plugins shipped in <server>/plugins).
        pipeline_plugins_dir=str(tmp_path / "plugins"),
    )
    components = build_components(settings)
    await init_components(components)
    app = create_app(settings=settings, components=components)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, components
