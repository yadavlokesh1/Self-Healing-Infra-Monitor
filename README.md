# Infra Monitor — Multi-Container Infra Monitoring Stack

Small Flask app reporting host CPU/memory/disk, containerized with Docker,
deployed to Kubernetes (Minikube/Kind) with health checks, auto-restart,
and resource limits.

## Stack
- `app/` — Flask app (`/`, `/health`, `/ready`, `/metrics`, `/crash`)
- `Dockerfile` — non-root, multi-stage-style build, Docker `HEALTHCHECK`
- `k8s/deployment.yaml` — 3 replicas, liveness/readiness/startup probes, resource limits
- `k8s/service.yaml` — NodePort service
- `k8s/hpa.yaml` — CPU-based autoscaling (2–6 pods)

## Why containerize (not just run the script)
| Problem without container | Solved by container |
|---|---|
| "works on my machine" — different Python/OS versions | Image pins exact Python + deps, runs identically anywhere |
| Manual dependency install on every server | `pip install` baked into image once |
| No isolation — app can hog host resources | `resources.limits` caps CPU/mem per container |
| Hard to scale — one process, one host | Same image runs as N replicas across nodes |
| Slow, manual rollback on bad deploy | Image tags = instant rollback (`kubectl rollout undo`) |

## How Kubernetes self-heals this app
1. **Liveness probe** (`/health`) — kubelet checks every 10s. 3 consecutive
   failures → kubelet **kills and restarts** the container in place.
2. **Readiness probe** (`/ready`) — if it fails, the pod is pulled out of
   the Service's endpoint list immediately (no restart) so it stops
   receiving traffic until it's healthy again — zero downtime for users.
3. **Startup probe** — gives slow-booting containers up to 30s before
   liveness checks even start, so a slow start isn't mistaken for a crash.
4. **ReplicaSet** — Deployment always reconciles actual pod count back to
   `replicas: 3`. Delete a pod manually → a new one is scheduled instantly.
5. **Resource limits** — a runaway container is OOM-killed/CPU-throttled
   instead of starving the node and taking other pods down with it.
6. **HPA** — under CPU load, pods auto-scale 2→6 and back down when load drops.

### Prove it yourself
```bash
kubectl get pods -w
# in another terminal, kill a pod's process from inside:
kubectl exec -it <pod-name> -- curl localhost:5000/crash
# watch it restart automatically (RESTARTS count increments)
```

## Run locally with Docker
```bash
docker build -t infra-monitor:latest .
docker run -p 5000:5000 infra-monitor:latest
curl localhost:5000/health
```

## Deploy to Minikube
```bash
minikube start
eval $(minikube docker-env)        # build image inside Minikube's Docker
docker build -t infra-monitor:latest .

kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml       # requires metrics-server: minikube addons enable metrics-server

kubectl get pods
minikube service infra-monitor-svc --url
```

## Deploy to Kind
```bash
kind create cluster
docker build -t infra-monitor:latest .
kind load docker-image infra-monitor:latest

kubectl apply -f k8s/
kubectl port-forward svc/infra-monitor-svc 8080:80
curl localhost:8080/health
```

## Useful commands
```bash
kubectl describe pod <name>          # see probe failures/events
kubectl top pods                     # live CPU/mem vs limits
kubectl rollout restart deployment infra-monitor
kubectl rollout undo deployment infra-monitor
```
