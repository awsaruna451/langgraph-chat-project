# Helm Charts — AI Agent Platform

One Helm chart per service, plus an umbrella chart (`ai-agent-platform`) that installs all three together.

## Structure

```
helm/
├── mcp-server/           # standalone chart
├── chat-be/              # standalone chart
├── chat-fe/              # standalone chart
└── ai-agent-platform/    # umbrella chart (bundles the three above as subcharts)
```

## Option A: install everything at once (recommended)

```bash
cd ai-agent-platform
helm dependency build
helm install ai-agent-platform . \
  --namespace ai-agent-platform --create-namespace \
  --set secrets.openaiApiKey=sk-... \
  --set secrets.googleApiKey=... \
  --set secrets.openweatherApiKey=... \
  --set secrets.alphavantageApiKey=...
```

Or better, put real secret values in a separate file that's never committed:

```yaml
# secrets.values.yaml (gitignored)
secrets:
  openaiApiKey: sk-...
  googleApiKey: ...
```

```bash
helm install ai-agent-platform . -n ai-agent-platform --create-namespace -f secrets.values.yaml
```

## Option B: install services independently

Useful while iterating on one service without touching the others:

```bash
helm install mcp-server ./mcp-server -n ai-agent-platform --create-namespace
helm install chat-be ./chat-be -n ai-agent-platform
helm install chat-fe ./chat-fe -n ai-agent-platform
```

Note: standalone installs use each chart's own `fullnameOverride` (`mcp-server`, `chat-be`, `chat-fe`), so service DNS names stay identical either way — `chat-be` reaches the MCP server at `http://mcp-server:8000` regardless of which install method you used.

## Building images for minikube first

Same as the plain-manifest version:

```bash
eval $(minikube docker-env)
docker build -t mcp-cal-server:local -f path/to/mcp-server/Dockerfile path/to/mcp-server
docker build -t chat-be:local        -f path/to/backend/Dockerfile   path/to/backend
docker build -t chat-fe:local        -f path/to/frontend/Dockerfile  path/to/frontend
```

## Validate before installing

```bash
helm lint ./mcp-server
helm lint ./chat-be
helm lint ./chat-fe
helm lint ./ai-agent-platform

helm template ./ai-agent-platform   # renders manifests without installing — inspect before applying
```

**I could not run `helm lint`/`helm template` myself in this environment** (no network access to Helm's or GitHub's release servers from this sandbox) — I checked brace-balance and YAML validity manually, but please run the two commands above yourself before `helm install` to catch anything a static check can't.

## Access the frontend (minikube)

```bash
minikube service chat-fe -n ai-agent-platform
```

## Uninstall

```bash
helm uninstall ai-agent-platform -n ai-agent-platform
# or, if installed separately:
helm uninstall mcp-server chat-be chat-fe -n ai-agent-platform
```

## What changes for EKS later

Same notes as the plain-manifest version:
- Switch `image.repository`/`tag` to ECR URIs, drop `pullPolicy: IfNotPresent`
- Replace `chat-fe`'s NodePort with an Ingress (AWS Load Balancer Controller)
- Pull secrets from AWS Secrets Manager instead of `--set`/plaintext values files
- Add a `HorizontalPodAutoscaler` template per chart once on EKS
