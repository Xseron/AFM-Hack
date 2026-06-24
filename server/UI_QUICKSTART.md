# UI Quickstart

Start the API with inline workers so uploads are analyzed in the same process:

```powershell
cd server
$env:MW_RUN_WORKERS_INLINE="true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

The page lets you upload a video, enter a description, poll the job result, and
view explanations.

## Real Models

To use real model-backed pipelines, install the model extras and enable models
before starting the server:

```powershell
cd server
python -m pip install -e ".[models]"
$env:MW_RUN_WORKERS_INLINE="true"
$env:MW_MODELS_ENABLED="true"
$env:MW_ALLOW_MODEL_DOWNLOADS="true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`MW_ALLOW_MODEL_DOWNLOADS=true` is only needed when weights are not already in
the local cache. After that first warm startup, set it to `false` or omit it.

When `MW_MODELS_ENABLED=true`, the server builds one shared model bundle during
startup through `app.models.loader.load_models()`. The real pipelines reuse that
bundle for every job instead of loading models inside request handling.
