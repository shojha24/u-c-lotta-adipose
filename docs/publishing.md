# Publishing to Read the Docs (Direct Upload)

This project builds static HTML documentation externally (with MkDocs Material + FastAPI's exported OpenAPI schema) and publishes it to Read the Docs via **Direct Upload**.

## One-Time Read the Docs Setup

1. Create a project on Read the Docs and choose **Build externally and upload** *(or contact Read the Docs support to enable Direct Upload on an existing project)*.
2. Under **Project Settings → API tokens → Add API token**, create a token with the **Upload documentation** permission.
3. For GitHub Actions, save the token as a repository secret named `READTHEDOCS_TOKEN` under **Settings → Secrets and variables → Actions**.

## Build Locally

From the repository root (with the `ucla-dining` conda environment active):

```bash
pip install -r docs/requirements.txt -r ucla-dining-api/requirements.txt
python docs/generate_openapi.py
mkdocs build --strict -d _build/html
```

Preview locally at `http://127.0.0.1:8000`:

```bash
mkdocs serve
```

## Upload from Your Terminal

```bash
export READTHEDOCS_TOKEN="<your-project-token>"
readthedocs upload \
  --project-slug <your-project-slug> \
  --html _build/html \
  --privacy-level public
```

!!! warning "Always pass `--privacy-level public`"
    Read the Docs Direct Upload makes uploaded versions **private** by default. Any upload without `privacy-level: public` will revert a public version back to private.

## Automated Uploads (GitHub Actions)

`.github/workflows/docs.yaml` automatically rebuilds `_build/html` and uploads it on pushes to `main`, `v*` tags (also publishing a `stable` version), and non-fork pull requests. Remember to replace `<your-project-slug>` in `.github/workflows/docs.yaml` with your Read the Docs project slug.
