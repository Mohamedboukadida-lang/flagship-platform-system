{{- define "lotse.name" -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels for an object: call with (dict "ctx" . "component" "api"). */}}
{{- define "lotse.labels" -}}
app.kubernetes.io/name: lotse
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/managed-by: {{ .ctx.Release.Service }}
helm.sh/chart: {{ .ctx.Chart.Name }}-{{ .ctx.Chart.Version }}
{{- end -}}

{{- define "lotse.selector" -}}
app.kubernetes.io/name: lotse
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "lotse.secretName" -}}
{{- required "secrets.existingSecret is required" .Values.secrets.existingSecret -}}
{{- end -}}

{{- define "lotse.image" -}}
{{- required "image.repository is required" .Values.image.repository -}}:{{- required "image.tag is required" .Values.image.tag -}}
{{- end -}}

{{- define "lotse.publicUrl" -}}
{{- if .Values.ingress.tls.enabled -}}https{{- else -}}http{{- end -}}://{{- required "host is required" .Values.host -}}
{{- end -}}

{{- define "lotse.dbHost" -}}
{{- if .Values.postgres.enabled -}}
{{- include "lotse.name" . -}}-postgres
{{- else -}}
{{- required "postgres.host is required when postgres.enabled is false" .Values.postgres.host -}}
{{- end -}}
{{- end -}}

{{/* One env entry read from the Secret: (dict "ctx" . "key" "POSTGRES_PASSWORD"). */}}
{{- define "lotse.secretEnv" -}}
- name: {{ .name | default .key }}
  valueFrom:
    secretKeyRef:
      name: {{ include "lotse.secretName" .ctx }}
      key: {{ .key }}
{{- end -}}

{{/* Hardened container security context shared by every workload. */}}
{{- define "lotse.containerSecurity" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
{{- end -}}
