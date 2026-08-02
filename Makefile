# AEGIS — developer & ops Makefile. Drives docker-compose and Kubernetes (minikube).
# Extensible: set K8S_PROVIDER (minikube today; add a provider block for kind/k3s).

K8S_PROVIDER ?= minikube
NAMESPACE    ?= aegis
OVERLAY      ?= k8s/overlays/local
HELM_RELEASE ?= aegis
CHART        ?= helm/aegis
BACKEND_IMG  ?= aegis-backend:local
FRONTEND_IMG ?= aegis-frontend:local
SVC          ?= backend
COMPOSE      ?= docker compose

# Build+save always target the HOST docker daemon, even if `minikube docker-env`
# is active in the shell (that mismatch causes "cannot find image in cache").
HOST_DOCKER  := env -u DOCKER_HOST -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH -u MINIKUBE_ACTIVE_DOCKERD

# ── Provider seam ────────────────────────────────────────────────────────────
# Each provider defines: how to start/stop/delete the cluster, enable ingress,
# load a local image, and report the cluster IP. Add kind/k3s as `else ifeq`.
# image_load streams a host-built image as an archive into the cluster; the
# `docker save | … load -` form avoids minikube's "unable to calculate
# manifest: blob not found" when Docker's containerd image store is enabled.
# (kind/k3s map to `kind load image-archive` / `ctr images import`.)
ifeq ($(K8S_PROVIDER),minikube)
CLUSTER_START  := minikube start --driver=docker
CLUSTER_STOP   := minikube stop
CLUSTER_DELETE := minikube delete
INGRESS_ENABLE := minikube addons enable ingress
CLUSTER_IP     := minikube ip
define image_load
$(HOST_DOCKER) docker save $(1) | $(HOST_DOCKER) minikube image load -
endef
else
$(error Unsupported K8S_PROVIDER '$(K8S_PROVIDER)'. Supported: minikube. Add a provider block for kind/k3s.)
endif

IP_NOW   = $(shell $(CLUSTER_IP) 2>/dev/null)
GUARD_IP = test -n "$(IP_NOW)" || { echo ">> $(K8S_PROVIDER) not running or unreachable. Run 'make cluster-up' first."; exit 1; }

# HOST_IP: the Linux host's LAN IP — used by `make expose` to forward the
# ingress controller port so it's reachable from other machines (e.g. a Windows
# dev box). Auto-detected via the default-route interface; override if needed:
#   make expose HOST_IP=192.168.1.42
HOST_IP     ?= $(shell ip route get 1.1.1.1 2>/dev/null | awk '/src/{for(i=1;i<=NF;i++) if($$i=="src") print $$(i+1)}' | head -1)
# EXPOSE_PORT: high port (no root) forwarded to ingress-nginx :80 inside the cluster.
EXPOSE_PORT ?= 8080

.DEFAULT_GOAL := help

##@ Docker Compose

up: ## Start the compose stack and wait until healthy
	$(COMPOSE) up -d --wait

down: ## Stop the compose stack (keep volumes)
	$(COMPOSE) down

down-v: ## Stop the compose stack and DELETE volumes (postgres + azurite data)
	$(COMPOSE) down -v --remove-orphans

build: ## Build compose images
	$(COMPOSE) build

logs: ## Tail compose logs (SVC=backend|frontend|db|azurite; default backend)
	$(COMPOSE) logs -f --tail=100 $(SVC)

ps: ## Show compose container status
	$(COMPOSE) ps

restart: ## Restart a compose service (SVC=…)
	$(COMPOSE) restart $(SVC)

shell: ## Open a shell in a compose service (SVC=…; default backend)
	$(COMPOSE) exec $(SVC) /bin/sh

seed: ## Load demo data into the compose stack (admin + profs + students + quiz)
	$(COMPOSE) exec -T backend python -m scripts.seed

##@ Kubernetes (minikube)

cluster-up: ## Start the cluster and enable the ingress controller
	$(CLUSTER_START)
	$(INGRESS_ENABLE)
	@echo ">> Waiting for ingress controller"
	@for i in $$(seq 1 30); do kubectl -n ingress-nginx get deploy ingress-nginx-controller >/dev/null 2>&1 && break; sleep 2; done
	kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s

images: ## Build backend+frontend images and load them into the cluster (needs cluster-up)
	@$(GUARD_IP)
	$(HOST_DOCKER) docker build -t $(BACKEND_IMG) ./backend
	$(HOST_DOCKER) docker build -f ./frontend/Dockerfile.prod --build-arg VITE_API_URL=http://api.$(IP_NOW).nip.io -t $(FRONTEND_IMG) ./frontend
	$(call image_load,$(BACKEND_IMG))
	$(call image_load,$(FRONTEND_IMG))

deploy: ## Helm-install locally, stamping the live cluster IP into ingress hosts + CORS
	@$(GUARD_IP)
	helm upgrade --install $(HELM_RELEASE) $(CHART) -n $(NAMESPACE) --create-namespace \
		-f $(CHART)/values-local.yaml \
		--set ingress.appHost=app.$(IP_NOW).nip.io \
		--set ingress.apiHost=api.$(IP_NOW).nip.io \
		--set-json 'backend.corsOrigins=["http://app.$(IP_NOW).nip.io"]' \
		--wait --timeout 300s
	@echo ">> Deployed. 'make url' for links, 'make smoke' to verify."

k8s-seed: ## Pre-create Azurite blob containers, then load demo data into the cluster backend
	kubectl exec -n $(NAMESPACE) deploy/backend -- python -m scripts.init_blob
	kubectl exec -n $(NAMESPACE) deploy/backend -- python -m scripts.seed

k8s-status: ## Show cluster resources in the aegis namespace
	kubectl get pods,svc,ingress,job,pvc -n $(NAMESPACE)

k8s-logs: ## Tail cluster logs (SVC=backend|frontend; default backend)
	kubectl logs -f -n $(NAMESPACE) -l app.kubernetes.io/component=$(SVC) --tail=100

k8s-shell: ## Shell into a cluster deployment (SVC=…; default backend)
	kubectl exec -it -n $(NAMESPACE) deploy/$(SVC) -- /bin/sh

url: ## Print the live app/api URLs (minikube IP — only reachable on this Linux host)
	@$(GUARD_IP)
	@echo "App : http://app.$(IP_NOW).nip.io"
	@echo "API : http://api.$(IP_NOW).nip.io  (health: /healthz)"
	@echo ""
	@echo "NOTE: $(IP_NOW) is the minikube docker-bridge IP, only routable on this machine."
	@echo "      Run 'make expose' to forward traffic via the host LAN IP ($(HOST_IP))."

expose: ## Forward ingress to HOST_IP:EXPOSE_PORT (default 8080) — no root needed; rebuilds frontend
	@$(GUARD_IP)
	@test -n "$(HOST_IP)" || { echo ">> Cannot detect HOST_IP. Run: make expose HOST_IP=<your-lan-ip>"; exit 1; }
	@pkill -f "[k]ubectl port-forward.*ingress-nginx" 2>/dev/null || true; sleep 1
	@echo ">> Starting port-forward $(HOST_IP):$(EXPOSE_PORT) -> ingress-nginx:80 (PID in /tmp/aegis-pf.pid)"
	@nohup kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller $(EXPOSE_PORT):80 --address=$(HOST_IP) >/tmp/aegis-pf.log 2>&1 & echo $$! > /tmp/aegis-pf.pid; sleep 2; grep -q "error\|Error" /tmp/aegis-pf.log && { cat /tmp/aegis-pf.log; exit 1; } || true
	@echo ">> Rebuilding frontend with VITE_API_URL=http://api.$(HOST_IP).nip.io:$(EXPOSE_PORT)"
	$(HOST_DOCKER) docker build -f ./frontend/Dockerfile.prod \
		--build-arg VITE_API_URL=http://api.$(HOST_IP).nip.io:$(EXPOSE_PORT) \
		-t $(FRONTEND_IMG) ./frontend
	$(call image_load,$(FRONTEND_IMG))
	helm upgrade --install $(HELM_RELEASE) $(CHART) -n $(NAMESPACE) --create-namespace \
		-f $(CHART)/values-local.yaml \
		--set ingress.appHost=app.$(HOST_IP).nip.io \
		--set ingress.apiHost=api.$(HOST_IP).nip.io \
		--set-json 'backend.corsOrigins=["http://app.$(HOST_IP).nip.io:$(EXPOSE_PORT)"]' \
		--wait --timeout 300s
	kubectl rollout restart deploy/backend -n $(NAMESPACE)
	kubectl rollout restart deploy/frontend -n $(NAMESPACE)
	kubectl rollout status deploy/backend -n $(NAMESPACE) --timeout=120s
	kubectl rollout status deploy/frontend -n $(NAMESPACE) --timeout=120s
	@echo ""
	@echo ">> Exposed. From any machine on the same network:"
	@echo "   App : http://app.$(HOST_IP).nip.io:$(EXPOSE_PORT)"
	@echo "   API : http://api.$(HOST_IP).nip.io:$(EXPOSE_PORT)/healthz"
	@echo "   (port-forward log: /tmp/aegis-pf.log)"

unexpose: ## Stop the port-forward started by `make expose`
	@if [ -f /tmp/aegis-pf.pid ]; then \
		kill $$(cat /tmp/aegis-pf.pid) 2>/dev/null && echo ">> port-forward stopped" || echo ">> process already gone"; \
		rm -f /tmp/aegis-pf.pid; \
	else \
		pkill -f "[k]ubectl port-forward.*ingress-nginx" 2>/dev/null && echo ">> port-forward stopped" || echo ">> no port-forward running"; \
	fi

diagnose: ## Diagnose why the app URLs are unreachable from this machine
	@$(GUARD_IP)
	@echo "=== 1. minikube IP and driver ==="
	@$(CLUSTER_IP)
	@minikube profile list 2>/dev/null | grep -E "minikube|Driver" || true
	@echo ""
	@echo "=== 2. nip.io DNS resolution (needs internet DNS, not corporate) ==="
	@nslookup app.$(IP_NOW).nip.io 8.8.8.8 2>/dev/null | grep -E "Address|Name" || echo "   FAILED — nip.io DNS blocked. Use /etc/hosts workaround (see below)"
	@echo ""
	@echo "=== 3. Can we ping the minikube node? ==="
	@ping -c1 -W2 $(IP_NOW) >/dev/null 2>&1 \
		&& echo "   OK — $(IP_NOW) is routable from this machine" \
		|| { echo "   FAILED — $(IP_NOW) not reachable."; \
		     echo "   If driver=docker: run 'minikube delete && minikube start --driver=docker'"; \
		     echo "   If driver=kvm2/virtualbox: run 'minikube tunnel' in a separate terminal"; }
	@echo ""
	@echo "=== 4. Direct curl to ingress-nginx NodePort (bypasses DNS) ==="
	@NODE_PORT=$$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.spec.ports[?(@.port==80)].nodePort}' 2>/dev/null); \
	if [ -n "$$NODE_PORT" ]; then \
		echo "   NodePort: $$NODE_PORT"; \
		curl -fsS --max-time 3 -H "Host: api.$(IP_NOW).nip.io" http://$(IP_NOW):$$NODE_PORT/healthz >/dev/null \
			&& echo "   OK — ingress routes correctly" \
			|| echo "   FAILED — node IP not reachable (need minikube tunnel for VM drivers)"; \
	else echo "   Cannot read NodePort"; fi
	@echo ""
	@echo "=== 5. Check port-forward (expose) is running ==="
	@pgrep -f "[k]ubectl port-forward.*ingress-nginx" >/dev/null \
		&& echo "   OK — port-forward running (PID: $$(cat /tmp/aegis-pf.pid 2>/dev/null || pgrep -f '[k]ubectl port-forward.*ingress-nginx'))" \
		|| echo "   NOT running — run 'make expose' for LAN access"
	@echo ""
	@echo "=== 6. /etc/hosts workaround (if DNS is blocked) ==="
	@echo "   Add these lines to /etc/hosts on this machine:"
	@echo "   $(IP_NOW)  app.$(IP_NOW).nip.io"
	@echo "   $(IP_NOW)  api.$(IP_NOW).nip.io"

tunnel: ## Start minikube tunnel in background (needed for VM drivers to route cluster IP to host)
	@echo ">> Starting minikube tunnel (routes $(IP_NOW) to this machine, needs sudo)"
	@nohup minikube tunnel >/tmp/aegis-tunnel.log 2>&1 & echo $$! > /tmp/aegis-tunnel.pid
	@sleep 2
	@echo ">> Tunnel PID: $$(cat /tmp/aegis-tunnel.pid) — log: /tmp/aegis-tunnel.log"
	@echo "   Stop with: make tunnel-stop"

tunnel-stop: ## Stop the minikube tunnel started by `make tunnel`
	@if [ -f /tmp/aegis-tunnel.pid ]; then \
		kill $$(cat /tmp/aegis-tunnel.pid) 2>/dev/null && echo ">> tunnel stopped" || echo ">> process already gone"; \
		rm -f /tmp/aegis-tunnel.pid; \
	else \
		pkill -f "[m]inikube tunnel" 2>/dev/null && echo ">> tunnel stopped" || echo ">> no tunnel running"; \
	fi


	$(MAKE) cluster-up
	$(MAKE) images
	$(MAKE) deploy
	$(MAKE) k8s-seed
	$(MAKE) url

##@ Tests & verification

test: ## Run backend unit tests (pytest)
	cd backend && uv run pytest -q

e2e: ## Run Playwright end-to-end tests (auto-starts the compose stack)
	cd frontend && npx playwright test

lint: ## Lint backend (ruff) + frontend (eslint)
	cd backend && uv run ruff check .
	cd frontend && npm run lint

smoke: ## Curl-check the ingress: backend health, frontend health, admin login (needs k8s-seed)
	@$(GUARD_IP)
	@if [ -f /tmp/aegis-pf.pid ] && kill -0 $$(cat /tmp/aegis-pf.pid) 2>/dev/null; then \
		API_HOST="http://api.$(HOST_IP).nip.io:$(EXPOSE_PORT)"; \
		APP_HOST="http://app.$(HOST_IP).nip.io:$(EXPOSE_PORT)"; \
		echo ">> (via expose: $(HOST_IP):$(EXPOSE_PORT))"; \
	else \
		API_HOST="http://api.$(IP_NOW).nip.io"; \
		APP_HOST="http://app.$(IP_NOW).nip.io"; \
		echo ">> (via direct minikube IP: $(IP_NOW))"; \
	fi; \
	echo ">> backend  $$API_HOST/healthz"; curl -fsS "$$API_HOST/healthz" >/dev/null && echo "   OK"; \
	echo ">> frontend $$APP_HOST/health";  curl -fsS "$$APP_HOST/health"  >/dev/null && echo "   OK"; \
	echo ">> login    admin@aegis.ie"; curl -fsS -X POST "$$API_HOST/auth/login" -H 'Content-Type: application/json' -d '{"email":"admin@aegis.ie","password":"SuperAdmin123!"}' | grep -q access_token && echo "   OK" || { echo "   FAILED — run 'make k8s-seed' first"; exit 1; }

##@ Teardown

undeploy: ## Uninstall the Helm release (namespace cascade removes pods + PVCs + data)
	-helm uninstall $(HELM_RELEASE) -n $(NAMESPACE)
	kubectl delete namespace $(NAMESPACE) --ignore-not-found

clean: ## Full in-cluster wipe: delete namespace (cascades pods/PVCs/all data) then wait
	kubectl delete namespace $(NAMESPACE) --ignore-not-found
	-kubectl wait --for=delete namespace/$(NAMESPACE) --timeout=120s

cluster-down: ## Stop the cluster (fast resume later; keeps data)
	$(CLUSTER_STOP)

cluster-delete: ## Delete the cluster entirely (removes ALL data and volumes)
	$(CLUSTER_DELETE)

nuke: cluster-delete ## Alias for cluster-delete (destroy the whole cluster)

##@ Meta

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nAEGIS make targets\n  Usage: make \033[36m<target>\033[0m\n"} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} /^[a-zA-Z0-9_%-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: up down down-v build logs ps restart shell seed \
	cluster-up images deploy k8s-seed k8s-status k8s-logs k8s-shell url expose unexpose tunnel tunnel-stop diagnose k8s-all \
	test e2e lint smoke \
	undeploy clean cluster-down cluster-delete nuke help
