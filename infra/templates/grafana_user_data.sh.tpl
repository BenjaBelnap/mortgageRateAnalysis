#!/bin/bash
# Bootstraps a single small Grafana host. Reasonable-default bootstrap for a
# cheap, low-traffic internal dashboard — pin package/AMI versions before
# treating this as hardened production infra.
set -euxo pipefail

dnf install -y docker jq
systemctl enable --now docker

mkdir -p /opt/grafana/provisioning/datasources /opt/grafana/provisioning/dashboards /opt/grafana/dashboards

SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "${db_secret_arn}" --query SecretString --output text --region "${aws_region}")
DB_PASSWORD=$(echo "$SECRET_JSON" | jq -r '.password')

cat > /opt/grafana/provisioning/datasources/postgres.yaml <<EOF
apiVersion: 1
datasources:
  - name: mortgage_rates_pg
    uid: mortgage_rates_pg
    type: postgres
    access: proxy
    url: "${db_host}:${db_port}"
    database: "${db_name}"
    user: "${db_user}"
    isDefault: true
    editable: true
    secureJsonData:
      password: "$DB_PASSWORD"
    jsonData:
      sslmode: require
      postgresVersion: 1600
EOF

cat > /opt/grafana/provisioning/dashboards/dashboards.yaml <<'EOF'
${dashboards_provider_yaml}
EOF

cat > /opt/grafana/dashboards/mortgage_rates.json <<'EOF'
${dashboard_json}
EOF

docker run -d --name grafana --restart unless-stopped \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  -v /opt/grafana/provisioning:/etc/grafana/provisioning \
  -v /opt/grafana/dashboards:/var/lib/grafana/dashboards \
  grafana/grafana-oss:11.4.0
