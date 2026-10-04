{{- define "arp-phase9.labels" -}}
app.kubernetes.io/part-of: azure-reliability-platform
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end }}

{{- define "arp-phase9.appLabels" -}}
app.kubernetes.io/name: arp-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
