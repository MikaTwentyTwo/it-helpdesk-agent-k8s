# IT HelpDesk Agent

Local multi-agent IT support assistant for Wi-Fi, printers, access requests
and software issues.

Repository: https://github.com/MikaTwentyTwo/pc-helper-agent-k8s
## Architecture

Python, FastAPI and LangGraph.
Supervisor selects topics; selected specialists prepare recommendations;
Critic reviews them; Synthesizer produces the final answer.
Rejected recommendations can be revised once, with at most two rounds.
The system provides advice and does not execute administrative actions.

LLM: Qwen3.5:4b through Ollama.
Embeddings: embeddinggemma, 768 dimensions.
Memory: SQLite session history and confirmed solutions.
RAG: cosine similarity over four local Markdown documents.
Knowledge dependencies: knowledge/dependencies.json.

## Deployment

Agent, Ollama and Jaeger run in Kubernetes using Minikube.
Prometheus, Grafana and Alertmanager run in separate Docker containers.
The notification receiver runs on Windows. Docker Compose is not used.

Prerequisites: Docker Desktop, Minikube, kubectl and Python 3.13.
Run commands from the repository directory.

### Start the existing configured environment

```powershell
minikube start -p helpdesk --driver=docker
docker update --cpus=8 --memory=6g --memory-swap=6g helpdesk
kubectl --context=helpdesk wait --for=condition=Ready node/helpdesk --timeout=180s
kubectl --context=helpdesk -n helpdesk get pods
docker start helpdesk-prometheus helpdesk-grafana helpdesk-alertmanager
```

Run each command below in a separate terminal and keep it open:

```powershell
kubectl --context=helpdesk -n helpdesk port-forward --address=0.0.0.0 service/agent 8081:8080
```

```powershell
kubectl --context=helpdesk -n helpdesk port-forward service/jaeger 16688:16686
```

```powershell
.\.venv\Scripts\python.exe observability\alert_receiver.py
```

The agent port listens on all host interfaces so Docker-based Prometheus
can scrape it. This is a local demonstration environment, not a public API.

### First deployment of Kubernetes components

```powershell
minikube start -p helpdesk --driver=docker --cpus=8 --memory=6144
minikube -p helpdesk image build -t helpdesk-agent:0.2 .
kubectl --context=helpdesk apply -f k8s\agent.yaml
kubectl --context=helpdesk apply -f k8s\ollama.yaml
kubectl --context=helpdesk apply -f k8s\jaeger.yaml
kubectl --context=helpdesk -n helpdesk rollout status deployment/ollama --timeout=300s
kubectl --context=helpdesk -n helpdesk exec deployment/ollama -- ollama pull qwen3.5:4b
kubectl --context=helpdesk -n helpdesk exec deployment/ollama -- ollama pull embeddinggemma
kubectl --context=helpdesk -n helpdesk rollout status deployment/agent --timeout=180s
kubectl --context=helpdesk -n helpdesk exec deployment/agent -- python -c "import asyncio; from app.rag import index_knowledge; print(asyncio.run(index_knowledge()))"
```

External monitoring containers must be created separately using the
configuration files under observability. The existing-environment commands
above do not create missing containers.

## Interfaces

| Component | URL |
|---|---|
| Swagger | http://127.0.0.1:8081/docs |
| Agent health | http://127.0.0.1:8081/health |
| Agent metrics | http://127.0.0.1:8081/metrics |
| Jaeger | http://127.0.0.1:16688 |
| Prometheus | http://127.0.0.1:9091 |
| Grafana | http://127.0.0.1:3001 |
| Alertmanager | http://127.0.0.1:9094 |
| Receiver health | http://127.0.0.1:8082/health |

## Demo request

POST /chat:

```json
{
  "session_id": "demo-final-1",
  "question": "Какие сведения нужны IT для запроса доступа к папке? Ответь кратко и укажи источник."
}
```

Reuse session_id for follow-up questions. Use a new value for a new session.

## Tests and evaluation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Live evaluations require a running API. Check runner options before use:

```powershell
.\.venv\Scripts\python.exe evals\run_evals.py --help
```

Evaluation results are stored in evals/results.
Formal checks cover routing, retrieval, citations and round limits.
They do not replace manual review of factual accuracy and safety.

## Observability

Metrics cover operation counts, duration and LLM input/output tokens.
Structured operation logs include trace_id.
Jaeger shows request, agent and memory spans.
Alertmanager sends notifications to the local receiver.
The firing/resolved notification cycle was verified for port 8081.

## Persistence and limitations

agent-data PVC stores SQLite databases; ollama-data PVC stores models.
Do not delete PVCs when restarting components.
Local Windows databases and Kubernetes databases are separate.

This is an educational prototype with no API authentication.
Confirmed solutions use the fixed demo user.
The model runs on CPU; observed request durations are several minutes.
Critic approval does not guarantee factual correctness.
Jaeger traces are not configured for persistent storage.

Updating Python code requires rebuilding the image and updating its tag
in k8s/agent.yaml. Restart port-forward after replacing the agent pod.

## Project directories

- app: API, graph, memory, retrieval and telemetry
- prompts: role instructions
- skills: specialist procedures
- knowledge: Markdown documents and dependencies
- tests: unit tests without a real LLM
- evals: live evaluation runner and results
- k8s: Kubernetes manifests
- observability: monitoring configuration and notification receiver
- docs: project documentation
