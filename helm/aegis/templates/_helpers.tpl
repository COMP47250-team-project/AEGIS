{{/*
Common labels applied to every resource. Mirrors the provenance labels the
Kustomize base used (app.kubernetes.io/part-of + managed-by), plus the Helm
release/version so `helm` and `kubectl` show consistent ownership.
*/}}
{{- define "aegis.labels" -}}
app.kubernetes.io/part-of: aegis
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{/*
Per-component selector labels. Selectors are immutable on Deployments, so keep
this minimal and stable (component only) — never fold in release/version here.
Usage: {{ include "aegis.selectorLabels" "backend" }}
*/}}
{{- define "aegis.selectorLabels" -}}
app.kubernetes.io/component: {{ . }}
{{- end -}}
