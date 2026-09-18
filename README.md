# Self-Healing Infra Monitor

**The problem:** Manual server monitoring doesn't scale, and when a monitoring process itself dies, nobody notices until something else breaks. I built this to answer a specific question from my own work as a system admin *what does "self-healing" actually look like at the orchestration layer, not just in a script or a scheduled task?*

This is a small monitoring app, containerized, deployed to Kubernetes, and configured so that if the app crashes, K8s detects and recovers it without anyone SSHing in the same pattern production monitoring stacks rely on.

## What it does
Flask app reporting host CPU/memory/disk, with endpoints kubelet uses to decide whether the container is alive and ready:
- `/health` - liveness signal
- `/ready` - readiness signal (traffic gating)
- `/metrics` - raw stats (JSON)
- `/crash` - manually kill the process, to test recovery on demand

## Design decisions (and why)
- **Separate liveness vs readiness probes** - a slow-starting container and a dead container need different responses. Liveness failure = restart. Readiness failure = pull from traffic, don't restart. Conflating the two is a common misconfiguration that causes unnecessary restart loops.
- **Startup probe** - protects a slow-booting container from being killed by liveness checks before it's even finished starting.
- **Resource requests/limits set explicitly** - no container should be able to starve the node it's on. Requests guarantee scheduling headroom; limits cap blast radius.
- **Non-root container user** - default `root` in a container is an unnecessary privilege escalation surface for zero benefit.
- **3 replicas + ReplicaSet** - single-instance monitoring is a single point of failure, which defeats the point of a monitoring app.

## Proof it self-heals
Deployed on a Kubernetes cluster (Minikube, AWS EC2), then deliberately killed a running pod to confirm the ReplicaSet controller replaces it without manual intervention:

```
kubectl delete pod infra-monitor-6475bf5f89-5k8bt
kubectl get pods
```

```
NAME                             READY   STATUS    RESTARTS   AGE
infra-monitor-6475bf5f89-8jjrc   1/1     Running   0          9m59s
infra-monitor-6475bf5f89-rqs62   1/1     Running   0          9m59s
infra-monitor-6475bf5f89-vd6vn   1/1     Running   0          22s   <- replacement, auto-created
```

Old pod gone, new pod up in seconds, replica count back to 3 - no alert paged, no one logged in to fix it.

## Stack
```
app/          Flask app (app.py, requirements.txt)
Dockerfile    Non-root build, Docker-level HEALTHCHECK
k8s/
  deployment.yaml   3 replicas, liveness/readiness/startup probes, resource limits
  service.yaml      NodePort
  hpa.yaml          CPU-based autoscaling, 2-6 pods
```

## Run it
```bash
# Build
docker build -t infra-monitor:latest .

# Local sanity check
docker run -d -p 5000:5000 infra-monitor:latest
curl localhost:5000/health

# Deploy to Minikube
minikube start --driver=docker
minikube image load infra-monitor:latest
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl get pods

# Prove self-healing
kubectl delete pod <any-pod-name>
kubectl get pods    # replacement pod appears automatically
```

## What I'd do next
- Wire `/metrics` into Prometheus + Grafana instead of a raw JSON endpoint turns this from a demo into an actual observability stack.
- Move image build/push into a GitHub Actions pipeline (CI), currently manual.
- Add a PodDisruptionBudget so voluntary disruptions (node drains) can't take out all replicas at once.

## Author
Lokesh Yadav — Infrastructure Specialist
