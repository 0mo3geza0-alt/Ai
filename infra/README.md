# Infrastructure Artifacts

These files are **self-host deployment artifacts**. They do NOT run inside the Emergent managed preview (which uses Supervisor on a single pod with fixed MongoDB).

- `Dockerfile.backend` / `Dockerfile.frontend` — container images
- `docker-compose.yml` — local full-stack (Mongo + backend + frontend)

Future phases add: `k8s/` manifests, `helm/` chart, `nginx.conf`, and `.github/workflows/ci.yml` (Phase 11).
