#!/usr/bin/env bash
set -Eeuo pipefail

readonly BACKEND_APP_SERVICE="trainsight-app"
readonly BACKEND_RETENTION_DAYS=30
readonly API_WEBTEST_NAME="wt-praxys-api-health"
readonly SCHEDULED_QUERY_API_VERSION="2026-03-01"
readonly MANAGED_PLAN_PROVIDER_ALERT="praxys-managed-plan-provider-failures"
readonly MANAGED_PLAN_DEFECT_ALERT="praxys-managed-plan-defects"
readonly FEEDBACK_PUBLICATION_CONFIG_ALERT="praxys-feedback-publication-config-provider"
readonly FEEDBACK_PUBLICATION_AGING_ALERT="praxys-feedback-publication-aging"
readonly OPERATIONS_ACTION_GROUP="praxys-feedback-ag"
readonly OPERATIONS_EMAIL_RECEIVER="support@praxys.run"
readonly BACKEND_ALERT_NAMES=(
  "praxys-db-health-unhealthy"
  "praxys-feedback-needs-review"
  "${FEEDBACK_PUBLICATION_CONFIG_ALERT}"
  "${FEEDBACK_PUBLICATION_AGING_ALERT}"
  "praxys-today-latency-regression"
  "praxys-sync-systemic-failures"
  "praxys-connect-systemic-failures"
  "${MANAGED_PLAN_PROVIDER_ALERT}"
  "${MANAGED_PLAN_DEFECT_ALERT}"
)

fail() {
  echo "ERROR: $*" >&2
  return 1
}

is_managed_plan_alert() {
  local alert_name="$1"
  [[ "${alert_name}" == "${MANAGED_PLAN_PROVIDER_ALERT}" ||
     "${alert_name}" == "${MANAGED_PLAN_DEFECT_ALERT}" ]]
}

is_feedback_publication_alert() {
  local alert_name="$1"
  [[ "${alert_name}" == "${FEEDBACK_PUBLICATION_CONFIG_ALERT}" ||
     "${alert_name}" == "${FEEDBACK_PUBLICATION_AGING_ALERT}" ]]
}

feedback_alert_action() {
  local transition="$1"
  local prior_scope="${2:-}"
  local prior_enabled="${3:-false}"
  case "${transition}" in
    backend) echo "backend-enabled" ;;
    frontend) echo "delete" ;;
    restore)
      if [[ -n "${BACKEND_AI_ID:-}" ]] &&
         ids_equal "${prior_scope}" "${BACKEND_AI_ID}"; then
        if [[ "${prior_enabled,,}" == "true" ]]; then
          echo "backend-preserve-enabled"
        else
          echo "backend-preserve-disabled"
        fi
      else
        echo "delete"
      fi
      ;;
    *) fail "unknown feedback alert transition: ${transition}" ;;
  esac
}

require_env() {
  local name
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || fail "required environment variable ${name} is empty"
  done
}

ids_equal() {
  local left="${1//$'\r'/}"
  local right="${2//$'\r'/}"
  [[ "${left,,}" == "${right,,}" ]]
}

component_id() {
  az resource show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "$1" \
    --resource-type Microsoft.Insights/components \
    --query id -o tsv
}

load_boundary_resources() {
  require_env \
    AZURE_RESOURCE_GROUP \
    LOG_ANALYTICS_WORKSPACE \
    FRONTEND_APPINSIGHTS_NAME \
    BACKEND_APPINSIGHTS_NAME

  WORKSPACE_ID="$(az monitor log-analytics workspace show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --query id -o tsv)"
  FRONTEND_AI_ID="$(component_id "${FRONTEND_APPINSIGHTS_NAME}")"
  BACKEND_AI_ID="$(component_id "${BACKEND_APPINSIGHTS_NAME}")"

  [[ -n "${WORKSPACE_ID}" && -n "${FRONTEND_AI_ID}" && -n "${BACKEND_AI_ID}" ]] ||
    fail "observability resources must exist before deployment"
  ! ids_equal "${FRONTEND_AI_ID}" "${BACKEND_AI_ID}" ||
    fail "frontend and backend Application Insights resources must be distinct"

  local resource_id linked_workspace
  for resource_id in "${FRONTEND_AI_ID}" "${BACKEND_AI_ID}"; do
    linked_workspace="$(az resource show \
      --ids "${resource_id}" \
      --query properties.WorkspaceResourceId -o tsv)"
    ids_equal "${linked_workspace}" "${WORKSPACE_ID}" ||
      fail "${resource_id} is not linked to ${LOG_ANALYTICS_WORKSPACE}"
  done

}

verify_resource_context_access() {
  local resource_context_access
  resource_context_access="$(az monitor log-analytics workspace show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --query features.enableLogAccessUsingOnlyResourcePermissions -o tsv)"
  [[ "${resource_context_access,,}" == "true" ]] ||
    fail "${LOG_ANALYTICS_WORKSPACE} must allow resource-context log access for exact-resource Monitoring Reader"
}

write_github_env() {
  require_env GITHUB_ENV
  printf '%s=%s\n' "$1" "$2" >> "${GITHUB_ENV}"
}

verify_anonymous_ingestion_rejected() {
  local connection_string="$1"
  local instrumentation_key=""
  local ingestion_endpoint=""
  local segment key value

  while IFS= read -r segment; do
    key="${segment%%=*}"
    value="${segment#*=}"
    case "${key}" in
      InstrumentationKey) instrumentation_key="${value}" ;;
      IngestionEndpoint) ingestion_endpoint="${value}" ;;
    esac
  done < <(tr ';' '\n' <<< "${connection_string}")

  [[ -n "${instrumentation_key}" && -n "${ingestion_endpoint}" ]] ||
    fail "backend connection string is missing ingestion routing fields"

  local payload response_file status
  payload="$(jq -cn \
    --arg ikey "${instrumentation_key}" \
    --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{
      name: "Microsoft.ApplicationInsights.Event",
      time: $time,
      iKey: $ikey,
      data: {
        baseType: "EventData",
        baseData: {
          ver: 2,
          name: "praxys.product_event",
          properties: {
            event_name: "forged_browser_probe",
            source: "deployment-boundary-check"
          }
        }
      }
    }')"
  response_file="$(mktemp)"
  status="$(curl \
    --silent \
    --show-error \
    --output "${response_file}" \
    --write-out "%{http_code}" \
    --header "Content-Type: application/json" \
    --request POST \
    --data "${payload}" \
    "${ingestion_endpoint%/}/v2.1/track")"
  rm -f "${response_file}"

  case "${status}" in
    401|403) return 0 ;;
    *) fail "backend accepted anonymous instrumentation-key ingestion (HTTP ${status})" ;;
  esac
}

scheduled_alert_url() {
  printf 'https://management.azure.com%s?api-version=%s' \
    "$1" "${SCHEDULED_QUERY_API_VERSION}"
}

scheduled_alert_body() {
  local source_json="$1"
  local target_scope="$2"
  local enabled_override="${3:-preserve}"

  jq -S -c \
    --arg scope "${target_scope}" \
    --arg enabled_override "${enabled_override}" \
    '
      def writable_identity:
        if . == null then null
        else {
          type,
          userAssignedIdentities: (
            if .userAssignedIdentities == null then null
            else (.userAssignedIdentities | with_entries(.value = {}))
            end
          )
        } | with_entries(select(.value != null))
        end;
      {
        location,
        tags,
        kind,
        identity: (.identity | writable_identity),
        properties: (
          .properties
          | del(.createdWithApiVersion)
          | .scopes = [$scope]
          | if $enabled_override == "true" then .enabled = true
            elif $enabled_override == "false" then .enabled = false
            else . end
        )
      } | with_entries(select(.value != null))
    ' <<< "${source_json}"
}

normalize_scheduled_alert() {
  jq -S -c '
    def writable_identity:
      if . == null then null
      else {
        type,
        userAssignedIdentities: (
          if .userAssignedIdentities == null then null
          else (.userAssignedIdentities | with_entries(.value = {}))
          end
        )
      } | with_entries(select(.value != null))
      end;
    {
      location,
      tags,
      kind,
      identity: (.identity | writable_identity),
      properties: (.properties | del(.createdWithApiVersion))
    } | with_entries(select(.value != null))
  '
}

is_resource_not_found() {
  grep -Eqi 'ResourceNotFound|status.?404|HTTP.?404' <<< "$1"
}

resolve_scheduled_alert_id() {
  local alert_name="$1"
  local output status
  if output="$(az resource show \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --name "${alert_name}" \
      --resource-type Microsoft.Insights/scheduledQueryRules \
      --query id -o tsv 2>&1)"; then
    if [[ -z "${output}" ]]; then
      fail "scheduled alert lookup returned an empty id: ${alert_name}"
      return 1
    fi
    printf '%s\n' "${output}"
    return 0
  else
    status=$?
  fi
  if is_resource_not_found "${output}"; then
    return 3
  fi
  echo "${output}" >&2
  # Status 3 is reserved internally for content-proven resource absence.
  # Normalize every other Azure CLI failure so a raw exit code cannot collide.
  return 1
}

delete_scheduled_alert() {
  local alert_id="$1"
  local output

  if ! output="$(az rest \
    --method delete \
    --url "$(scheduled_alert_url "${alert_id}")" \
    --output none 2>&1)"; then
    if is_resource_not_found "${output}"; then
      return 0
    fi
    echo "${output}" >&2
    return 1
  fi

  local attempt
  for attempt in {1..10}; do
    if output="$(az rest \
      --method get \
      --url "$(scheduled_alert_url "${alert_id}")" \
      -o json 2>&1)"; then
      sleep 2
      continue
    fi
    if is_resource_not_found "${output}"; then
      return 0
    fi
    echo "${output}" >&2
    return 1
  done

  fail "timed out waiting for scheduled alert deletion: ${alert_id}"
}

recreate_scheduled_alert() {
  local alert_id="$1"
  local source_json="$2"
  local target_scope="$3"
  local enabled_override="${4:-preserve}"
  local body output actual_json expected_normalized actual_normalized

  body="$(
    scheduled_alert_body \
      "${source_json}" \
      "${target_scope}" \
      "${enabled_override}"
  )"
  delete_scheduled_alert "${alert_id}"

  local attempt
  for attempt in {1..5}; do
    if output="$(az rest \
      --method put \
      --url "$(scheduled_alert_url "${alert_id}")" \
      --headers "Content-Type=application/json" \
      --body "${body}" \
      --output none 2>&1)"; then
      break
    fi
    if [[ "${attempt}" == "5" ]]; then
      echo "${output}" >&2
      return 1
    fi
    sleep "$((attempt * 2))"
  done

  for attempt in {1..10}; do
    if actual_json="$(az rest \
      --method get \
      --url "$(scheduled_alert_url "${alert_id}")" \
      -o json 2>/dev/null)"; then
      break
    fi
    if [[ "${attempt}" == "10" ]]; then
      fail "timed out waiting for scheduled alert recreation: ${alert_id}"
    fi
    sleep 2
  done

  expected_normalized="$(normalize_scheduled_alert <<< "${body}")"
  actual_normalized="$(normalize_scheduled_alert <<< "${actual_json}")"
  if [[ "${actual_normalized}" != "${expected_normalized}" ]]; then
    echo "Expected scheduled alert:" >&2
    jq . <<< "${expected_normalized}" >&2
    echo "Actual scheduled alert:" >&2
    jq . <<< "${actual_normalized}" >&2
    fail "scheduled alert recreation changed behavior: ${alert_id}"
  fi
}

managed_plan_alert_definition() {
  local alert_name="$1"
  local scope="$2"
  local action_group_id="$3"
  local location="$4"
  local enabled="${5:-true}"
  local description query workload
  local severity=2
  workload="managed-plan"

  case "${alert_name}" in
    "${MANAGED_PLAN_PROVIDER_ALERT}")
      description="Five or more athletes hit managed-plan provider/auth failures for one execution target in 15 minutes."
      query="$(cat <<'KQL'
let managed = union isfuzzy=true
  (customEvents
   | where name == "praxys.managed_plan"
   | project target=tostring(customDimensions.target),
       outcome=tostring(customDimensions.outcome),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash)),
  (customMetrics
   | where name == "praxys.managed_plan"
   | project target=tostring(customDimensions.target),
       outcome=tostring(customDimensions.outcome),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash));
managed
| where outcome in ("failed", "blocked", "partial")
| where failure_domain in ("provider", "provider_auth")
| where target != "none" and isnotempty(user)
| summarize affected_users=dcount(user), failures=count()
    by target, failure_domain
| where affected_users >= 5
KQL
)"
      ;;
    "${MANAGED_PLAN_DEFECT_ALERT}")
      description="A managed-plan delivery hit a known Praxys ledger, reconciliation, finalization, or adapter defect."
      query="$(cat <<'KQL'
union isfuzzy=true
  (customEvents
   | where name == "praxys.managed_plan"
   | project action=tostring(customDimensions.action),
       outcome=tostring(customDimensions.outcome),
       target=tostring(customDimensions.target),
       reason=tostring(customDimensions.reason),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash)),
  (customMetrics
   | where name == "praxys.managed_plan"
   | project action=tostring(customDimensions.action),
       outcome=tostring(customDimensions.outcome),
       target=tostring(customDimensions.target),
       reason=tostring(customDimensions.reason),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash))
| where outcome in ("failed", "blocked", "partial")
| where failure_domain == "praxys"
| summarize failures=count(), affected_users=dcountif(user, isnotempty(user))
    by target, action, reason
| where failures > 0
KQL
)"
      ;;
    "${FEEDBACK_PUBLICATION_CONFIG_ALERT}")
      workload="feedback-publication"
      description="Feedback publication has an actionable configuration, authentication, or GitHub provider failure."
      query="$(cat <<'KQL'
union isfuzzy=true
  (customEvents
   | where name == "praxys.feedback_publication"
   | project status=tostring(customDimensions.status),
       reason=tostring(customDimensions.reason)),
  (customMetrics
   | where name == "praxys.feedback_publication"
   | project status=tostring(customDimensions.status),
       reason=tostring(customDimensions.reason))
| where status in ("config_failure", "provider_failure")
| summarize failures=count() by status, reason
| where failures > 0
KQL
)"
      ;;
    "${FEEDBACK_PUBLICATION_AGING_ALERT}")
      workload="feedback-publication"
      severity=3
      description="A consent-bound feedback publication has remained queued or ambiguous beyond its action threshold."
      query="$(cat <<'KQL'
union isfuzzy=true
  (customEvents
   | where name == "praxys.feedback_publication"
   | project status=tostring(customDimensions.status),
       reason=tostring(customDimensions.reason)),
  (customMetrics
   | where name == "praxys.feedback_publication"
   | project status=tostring(customDimensions.status),
       reason=tostring(customDimensions.reason))
| where status in ("queue_aged", "unknown_aged")
| summarize aged=count() by status, reason
| where aged > 0
KQL
)"
      ;;
    *)
      fail "unknown managed-plan alert: ${alert_name}"
      ;;
  esac

  jq -S -c -n \
    --arg location "${location}" \
    --arg scope "${scope}" \
    --arg action_group_id "${action_group_id}" \
    --arg display_name "${alert_name}" \
    --arg description "${description}" \
    --arg query "${query}" \
    --arg workload "${workload}" \
    --argjson severity "${severity}" \
    --argjson enabled "${enabled}" \
    '{
      location: $location,
      kind: "LogAlert",
      tags: {
        managedBy: "deploy-backend",
        workload: $workload
      },
      properties: {
        displayName: $display_name,
        description: $description,
        severity: $severity,
        enabled: $enabled,
        evaluationFrequency: "PT15M",
        windowSize: "PT15M",
        scopes: [$scope],
        targetResourceTypes: ["Microsoft.Insights/components"],
        criteria: {
          allOf: [{
            query: $query,
            timeAggregation: "Count",
            operator: "GreaterThan",
            threshold: 0,
            failingPeriods: {
              numberOfEvaluationPeriods: 1,
              minFailingPeriodsToAlert: 1
            },
            criterionType: "StaticThresholdCriterion"
          }]
        },
        autoMitigate: true,
        checkWorkspaceAlertsStorageConfigured: false,
        skipQueryValidation: false,
        actions: {
          actionGroups: [$action_group_id],
          customProperties: {}
        }
      }
    }'
}

upsert_managed_plan_alert() {
  local alert_name="$1"
  local alert_id="$2"
  local scope="$3"
  local action_group_id="$4"
  local location="$5"
  local enabled="${6:-true}"
  local body output actual expected_query expected_severity expected_workload

  body="$(
    managed_plan_alert_definition \
      "${alert_name}" \
      "${scope}" \
      "${action_group_id}" \
      "${location}" \
      "${enabled}"
  )"
  expected_query="$(jq -r '.properties.criteria.allOf[0].query' <<< "${body}")"
  expected_severity="$(jq -r '.properties.severity' <<< "${body}")"
  expected_workload="$(jq -r '.tags.workload' <<< "${body}")"

  local attempt
  for attempt in {1..5}; do
    if output="$(az rest \
      --method put \
      --url "$(scheduled_alert_url "${alert_id}")" \
      --headers "Content-Type=application/json" \
      --body "${body}" \
      --output none 2>&1)"; then
      break
    fi
    if [[ "${attempt}" == "5" ]]; then
      echo "${output}" >&2
      return 1
    fi
    sleep "$((attempt * 2))"
  done

  actual="$(az rest \
    --method get \
    --url "$(scheduled_alert_url "${alert_id}")" \
    -o json)"
  jq -e \
    --arg scope "${scope}" \
    --arg action_group_id "${action_group_id}" \
    --arg location "${location}" \
    --arg expected_query "${expected_query}" \
    --arg expected_workload "${expected_workload}" \
    --argjson expected_severity "${expected_severity}" \
    --argjson expected_enabled "${enabled}" \
    '
      def lower: ascii_downcase;
      (.location | lower) == ($location | lower)
      and .kind == "LogAlert"
      and .tags.managedBy == "deploy-backend"
      and .tags.workload == $expected_workload
      and .properties.enabled == $expected_enabled
      and .properties.severity == $expected_severity
      and .properties.evaluationFrequency == "PT15M"
      and .properties.windowSize == "PT15M"
      and (.properties.scopes | length) == 1
      and (.properties.scopes[0] | lower) == ($scope | lower)
      and (.properties.actions.actionGroups | length) == 1
      and (.properties.actions.actionGroups[0] | lower)
          == ($action_group_id | lower)
      and .properties.criteria.allOf[0].query == $expected_query
      and .properties.criteria.allOf[0].operator == "GreaterThan"
      and .properties.criteria.allOf[0].threshold == 0
    ' <<< "${actual}" >/dev/null ||
    fail "managed-plan alert verification failed: ${alert_name}"
}

ensure_managed_plan_alerts() {
  local telemetry_scope="$1"
  local action_group_json action_group_id resource_group_id location
  local alert_name alert_id
  action_group_json="$(az monitor action-group show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${OPERATIONS_ACTION_GROUP}" \
    -o json)"
  jq -e \
    --arg receiver "${OPERATIONS_EMAIL_RECEIVER}" \
    '
      .enabled == true
      and any(
        .emailReceivers[]?;
        ((.emailAddress // "") | ascii_downcase)
            == ($receiver | ascii_downcase)
        and ((.status // "") | ascii_downcase) == "enabled"
      )
    ' <<< "${action_group_json}" >/dev/null ||
    fail "${OPERATIONS_ACTION_GROUP} or its ${OPERATIONS_EMAIL_RECEIVER} receiver is disabled"
  action_group_id="$(jq -r '.id // empty' <<< "${action_group_json}")"
  resource_group_id="$(az group show \
    --name "${AZURE_RESOURCE_GROUP}" \
    --query id -o tsv)"
  location="$(az resource show \
    --ids "${telemetry_scope}" \
    --query location -o tsv)"
  [[ -n "${action_group_id}" && -n "${resource_group_id}" && -n "${location}" ]] ||
    fail "managed-plan alert resources could not be resolved"

  for alert_name in \
    "${MANAGED_PLAN_PROVIDER_ALERT}" \
    "${MANAGED_PLAN_DEFECT_ALERT}"; do
    alert_id="${resource_group_id}/providers/Microsoft.Insights/scheduledQueryRules/${alert_name}"
    upsert_managed_plan_alert \
      "${alert_name}" \
      "${alert_id}" \
      "${telemetry_scope}" \
      "${action_group_id}" \
      "${location}"
  done
}

ensure_feedback_publication_alerts() {
  local backend_scope="$1"
  local action_group_json action_group_id resource_group_id location
  local alert_name alert_id
  action_group_json="$(az monitor action-group show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${OPERATIONS_ACTION_GROUP}" \
    -o json)"
  jq -e \
    --arg receiver "${OPERATIONS_EMAIL_RECEIVER}" \
    '
      .enabled == true
      and any(
        .emailReceivers[]?;
        ((.emailAddress // "") | ascii_downcase)
            == ($receiver | ascii_downcase)
        and ((.status // "") | ascii_downcase) == "enabled"
      )
    ' <<< "${action_group_json}" >/dev/null ||
    fail "${OPERATIONS_ACTION_GROUP} or its ${OPERATIONS_EMAIL_RECEIVER} receiver is disabled"
  action_group_id="$(jq -r '.id // empty' <<< "${action_group_json}")"
  resource_group_id="$(az group show \
    --name "${AZURE_RESOURCE_GROUP}" \
    --query id -o tsv)"
  location="$(az resource show \
    --ids "${backend_scope}" \
    --query location -o tsv)"
  [[ -n "${action_group_id}" && -n "${resource_group_id}" && -n "${location}" ]] ||
    fail "feedback-publication alert resources could not be resolved"

  for alert_name in \
    "${FEEDBACK_PUBLICATION_CONFIG_ALERT}" \
    "${FEEDBACK_PUBLICATION_AGING_ALERT}"; do
    alert_id="${resource_group_id}/providers/Microsoft.Insights/scheduledQueryRules/${alert_name}"
    upsert_managed_plan_alert \
      "${alert_name}" \
      "${alert_id}" \
      "${backend_scope}" \
      "${action_group_id}" \
      "${location}" \
      true
  done
}

delete_feedback_publication_alerts() {
  local alert_name alert_id lookup_status
  for alert_name in \
    "${FEEDBACK_PUBLICATION_CONFIG_ALERT}" \
    "${FEEDBACK_PUBLICATION_AGING_ALERT}"; do
    if alert_id="$(resolve_scheduled_alert_id "${alert_name}")"; then
      delete_scheduled_alert "${alert_id}"
      continue
    else
      lookup_status=$?
    fi
    if [[ "${lookup_status}" == "3" ]]; then
      echo "Skipping missing feedback-publication alert: ${alert_name}" >&2
      continue
    fi
    return "${lookup_status}"
  done
}

verify_feedback_publication_alerts_absent() {
  local alert_name alert_id lookup_status
  for alert_name in \
    "${FEEDBACK_PUBLICATION_CONFIG_ALERT}" \
    "${FEEDBACK_PUBLICATION_AGING_ALERT}"; do
    if alert_id="$(resolve_scheduled_alert_id "${alert_name}")"; then
      fail "feedback-publication alert still exists after frontend rollback: ${alert_name} (${alert_id})"
      return 1
    else
      lookup_status=$?
    fi
    if [[ "${lookup_status}" != "3" ]]; then
      return "${lookup_status}"
    fi
  done
}

backend_preflight() {
  load_boundary_resources
  verify_resource_context_access

  az monitor log-analytics workspace update \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --retention-time "${BACKEND_RETENTION_DAYS}" \
    --output none

  az resource update \
    --ids "${BACKEND_AI_ID}" \
    --set \
      properties.DisableLocalAuth=true \
      properties.DisableIpMasking=false \
      properties.RetentionInDays="${BACKEND_RETENTION_DAYS}" \
      tags.trustBoundary=backend \
      tags.managedBy=deploy-backend \
    --output none

  local disable_local_auth disable_ip_masking backend_retention
  local workspace_retention
  disable_local_auth="$(az resource show \
    --ids "${BACKEND_AI_ID}" \
    --query properties.DisableLocalAuth -o tsv)"
  [[ "${disable_local_auth,,}" == "true" ]] ||
    fail "backend Application Insights local authentication is not disabled"
  disable_ip_masking="$(az resource show \
    --ids "${BACKEND_AI_ID}" \
    --query properties.DisableIpMasking -o tsv)"
  [[ "${disable_ip_masking,,}" == "false" ]] ||
    fail "backend Application Insights IP masking is disabled"
  backend_retention="$(az resource show \
    --ids "${BACKEND_AI_ID}" \
    --query properties.RetentionInDays -o tsv)"
  [[ "${backend_retention}" == "${BACKEND_RETENTION_DAYS}" ]] ||
    fail "backend Application Insights retention is not ${BACKEND_RETENTION_DAYS} days"
  workspace_retention="$(az monitor log-analytics workspace show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --query retentionInDays -o tsv)"
  [[ "${workspace_retention}" == "${BACKEND_RETENTION_DAYS}" ]] ||
    fail "${LOG_ANALYTICS_WORKSPACE} retention is not ${BACKEND_RETENTION_DAYS} days"

  local identity_json runtime_mi_client_id backend_mi_principal
  local publisher_role_count reader_role_count
  identity_json="$(az webapp identity show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${BACKEND_APP_SERVICE}" \
    -o json)"
  runtime_mi_client_id="$(az webapp config appsettings list \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${BACKEND_APP_SERVICE}" \
    --query "[?name=='AZURE_CLIENT_ID'].value | [0]" \
    -o tsv)"
  runtime_mi_client_id="${runtime_mi_client_id//$'\r'/}"
  if [[ -n "${runtime_mi_client_id}" ]]; then
    backend_mi_principal="$(jq -r \
      --arg client_id "${runtime_mi_client_id}" \
      '[
        (.userAssignedIdentities // {} | to_entries[] | .value)
        | select((.clientId // "" | ascii_downcase) == ($client_id | ascii_downcase))
        | .principalId
      ][0] // empty' <<< "${identity_json}")"
    [[ -n "${backend_mi_principal}" ]] ||
      fail "${BACKEND_APP_SERVICE} AZURE_CLIENT_ID does not match an attached user-assigned managed identity"
  else
    backend_mi_principal="$(jq -r '.principalId // empty' <<< "${identity_json}")"
    [[ -n "${backend_mi_principal}" ]] ||
      fail "${BACKEND_APP_SERVICE} system-assigned managed identity is disabled"
  fi
  publisher_role_count="$(az role assignment list \
    --assignee-object-id "${backend_mi_principal}" \
    --scope "${BACKEND_AI_ID}" \
    --query "[?roleDefinitionName=='Monitoring Metrics Publisher'] | length(@)" \
    -o tsv)"
  [[ "${publisher_role_count:-0}" != "0" ]] ||
    fail "${BACKEND_APP_SERVICE} runtime managed identity lacks Monitoring Metrics Publisher on ${BACKEND_APPINSIGHTS_NAME}; see docs/ops/config-and-secrets.md"
  reader_role_count="$(az role assignment list \
    --assignee-object-id "${backend_mi_principal}" \
    --scope "${BACKEND_AI_ID}" \
    --query "[?roleDefinitionName=='Monitoring Reader'] | length(@)" \
    -o tsv)"
  [[ "${reader_role_count:-0}" != "0" ]] ||
    fail "${BACKEND_APP_SERVICE} runtime managed identity lacks Monitoring Reader on ${BACKEND_APPINSIGHTS_NAME}; see docs/ops/config-and-secrets.md"

  local connection_string
  connection_string="$(az resource show \
    --ids "${BACKEND_AI_ID}" \
    --query properties.ConnectionString -o tsv)"
  [[ -n "${connection_string}" ]] ||
    fail "backend Application Insights connection string is empty"

  verify_anonymous_ingestion_rejected "${connection_string}"
  ensure_feedback_publication_alerts "${BACKEND_AI_ID}"

  local current_admin_resource_id managed_alert_scope
  current_admin_resource_id="$(az webapp config appsettings list \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${BACKEND_APP_SERVICE}" \
    --query "[?name=='PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID'].value | [0]" \
    -o tsv)"
  if [[ -z "${current_admin_resource_id}" ]]; then
    managed_alert_scope="${FRONTEND_AI_ID}"
  elif ids_equal "${current_admin_resource_id}" "${FRONTEND_AI_ID}"; then
    managed_alert_scope="${FRONTEND_AI_ID}"
  elif ids_equal "${current_admin_resource_id}" "${BACKEND_AI_ID}"; then
    managed_alert_scope="${BACKEND_AI_ID}"
  else
    fail "current admin telemetry resource is outside the trusted cutover pair"
  fi
  ensure_managed_plan_alerts "${managed_alert_scope}"

  echo "::add-mask::${connection_string}"
  write_github_env "APPLICATIONINSIGHTS_CONNECTION_STRING" "${connection_string}"
  write_github_env "FRONTEND_APPINSIGHTS_RESOURCE_ID" "${FRONTEND_AI_ID}"
  write_github_env "BACKEND_APPINSIGHTS_RESOURCE_ID" "${BACKEND_AI_ID}"
}

frontend_resolve() {
  load_boundary_resources

  local frontend_local_auth backend_local_auth
  frontend_local_auth="$(az resource show \
    --ids "${FRONTEND_AI_ID}" \
    --query properties.DisableLocalAuth -o tsv)"
  backend_local_auth="$(az resource show \
    --ids "${BACKEND_AI_ID}" \
    --query properties.DisableLocalAuth -o tsv)"
  [[ "${frontend_local_auth,,}" != "true" ]] ||
    fail "frontend Application Insights must allow browser instrumentation-key ingestion"
  [[ "${backend_local_auth,,}" == "true" ]] ||
    fail "backend Application Insights must reject instrumentation-key ingestion"

  az monitor log-analytics workspace update \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --retention-time "${BACKEND_RETENTION_DAYS}" \
    --output none

  az resource update \
    --ids "${FRONTEND_AI_ID}" \
    --set \
      properties.DisableIpMasking=false \
      properties.RetentionInDays="${BACKEND_RETENTION_DAYS}" \
      tags.trustBoundary=frontend \
      tags.managedBy=deploy-frontend-appservice \
    --output none

  local disable_ip_masking frontend_retention workspace_retention
  disable_ip_masking="$(az resource show \
    --ids "${FRONTEND_AI_ID}" \
    --query properties.DisableIpMasking -o tsv)"
  [[ "${disable_ip_masking,,}" == "false" ]] ||
    fail "frontend Application Insights IP masking is disabled"
  frontend_retention="$(az resource show \
    --ids "${FRONTEND_AI_ID}" \
    --query properties.RetentionInDays -o tsv)"
  [[ "${frontend_retention}" == "${BACKEND_RETENTION_DAYS}" ]] ||
    fail "frontend Application Insights retention is not ${BACKEND_RETENTION_DAYS} days"
  workspace_retention="$(az monitor log-analytics workspace show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS_WORKSPACE}" \
    --query retentionInDays -o tsv)"
  [[ "${workspace_retention}" == "${BACKEND_RETENTION_DAYS}" ]] ||
    fail "${LOG_ANALYTICS_WORKSPACE} retention is not ${BACKEND_RETENTION_DAYS} days"

  local connection_string
  connection_string="$(az resource show \
    --ids "${FRONTEND_AI_ID}" \
    --query properties.ConnectionString -o tsv)"
  [[ -n "${connection_string}" ]] ||
    fail "frontend Application Insights connection string is empty"

  echo "::add-mask::${connection_string}"
  write_github_env "VITE_APPINSIGHTS_CONNECTION_STRING" "${connection_string}"
}

telemetry_cutover() {
  local target="$1"
  load_boundary_resources

  local target_ai_id other_ai_id target_connection_string target_name
  case "${target}" in
    backend)
      verify_resource_context_access
      require_env \
        APPLICATIONINSIGHTS_CONNECTION_STRING \
        FRONTEND_APPINSIGHTS_RESOURCE_ID \
        BACKEND_APPINSIGHTS_RESOURCE_ID
      ids_equal "${FRONTEND_AI_ID}" "${FRONTEND_APPINSIGHTS_RESOURCE_ID}" ||
        fail "frontend Application Insights resource changed after preflight"
      ids_equal "${BACKEND_AI_ID}" "${BACKEND_APPINSIGHTS_RESOURCE_ID}" ||
        fail "backend Application Insights resource changed after preflight"
      target_ai_id="${BACKEND_AI_ID}"
      other_ai_id="${FRONTEND_AI_ID}"
      target_connection_string="${APPLICATIONINSIGHTS_CONNECTION_STRING}"
      target_name="${BACKEND_APPINSIGHTS_NAME}"
      ;;
    frontend)
      target_ai_id="${FRONTEND_AI_ID}"
      other_ai_id="${BACKEND_AI_ID}"
      target_connection_string="$(az resource show \
        --ids "${FRONTEND_AI_ID}" \
        --query properties.ConnectionString -o tsv)"
      [[ -n "${target_connection_string}" ]] ||
        fail "frontend Application Insights connection string is empty"
      target_name="${FRONTEND_APPINSIGHTS_NAME}"
      echo "::add-mask::${target_connection_string}"
      ;;
    *)
      fail "unknown telemetry cutover target: ${target}"
      ;;
  esac

  local old_connection_string old_admin_resource_id
  old_connection_string="$(az webapp config appsettings list \
    --name "${BACKEND_APP_SERVICE}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].value | [0]" \
    -o tsv)"
  old_admin_resource_id="$(az webapp config appsettings list \
    --name "${BACKEND_APP_SERVICE}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --query "[?name=='PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID'].value | [0]" \
    -o tsv)"
  [[ -n "${old_connection_string}" ]] &&
    echo "::add-mask::${old_connection_string}"

  local -a active_alert_names=()
  local -a alert_ids=()
  local -a old_alert_jsons=()
  local -a old_alert_scopes=()
  local alert_name alert_id alert_json alert_scope scope_count lookup_status
  for alert_name in "${BACKEND_ALERT_NAMES[@]}"; do
    if alert_id="$(resolve_scheduled_alert_id "${alert_name}")"; then
      :
    else
      lookup_status=$?
      if [[ "${target}" == "frontend" ]]; then
        if [[ "${lookup_status}" == "3" ]] &&
           is_feedback_publication_alert "${alert_name}"; then
          echo "Skipping missing feedback-publication alert during rollback: ${alert_name}" >&2
          continue
        fi
        if [[ "${lookup_status}" == "3" ]] &&
           is_managed_plan_alert "${alert_name}"; then
          echo "Skipping missing deployment-owned managed-plan alert during rollback: ${alert_name}" >&2
          continue
        fi
      fi
      if [[ "${lookup_status}" == "3" ]]; then
        fail "required backend alert not found: ${alert_name}"
      else
        return "${lookup_status}"
      fi
    fi
    alert_json="$(az rest \
      --method get \
      --url "$(scheduled_alert_url "${alert_id}")" \
      -o json | jq -c '.')"
    scope_count="$(jq -r '.properties.scopes | length' <<< "${alert_json}")"
    alert_scope="$(jq -r '.properties.scopes[0]' <<< "${alert_json}")"
    [[ "${scope_count}" == "1" ]] ||
      fail "${alert_name} must have exactly one Application Insights scope"
    if ! ids_equal "${alert_scope}" "${FRONTEND_AI_ID}" &&
       ! ids_equal "${alert_scope}" "${BACKEND_AI_ID}"; then
      fail "${alert_name} has an unexpected scope: ${alert_scope}"
    fi
    active_alert_names+=("${alert_name}")
    alert_ids+=("${alert_id}")
    old_alert_jsons+=("${alert_json}")
    old_alert_scopes+=("${alert_scope}")
  done

  local api_webtest_id old_api_webtest_tags frontend_link_key backend_link_key
  local target_link_key other_link_key
  api_webtest_id="$(az resource show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${API_WEBTEST_NAME}" \
    --resource-type Microsoft.Insights/webtests \
    --query id -o tsv)"
  old_api_webtest_tags="$(az resource show \
    --ids "${api_webtest_id}" \
    --query tags -o json)"
  frontend_link_key="hidden-link:${FRONTEND_AI_ID}"
  backend_link_key="hidden-link:${BACKEND_AI_ID}"
  if [[ "${target}" == "backend" ]]; then
    target_link_key="${backend_link_key}"
    other_link_key="${frontend_link_key}"
  else
    target_link_key="${frontend_link_key}"
    other_link_key="${backend_link_key}"
  fi
  jq -e \
    --arg frontend "${frontend_link_key}" \
    --arg backend "${backend_link_key}" \
    '.[$frontend] == "Resource" or .[$backend] == "Resource"' \
    <<< "${old_api_webtest_tags}" >/dev/null ||
    fail "${API_WEBTEST_NAME} is not linked to either configured component"

  local api_alert_id old_api_alert_json old_api_alert_component
  local -a old_api_alert_scopes=()
  api_alert_id="$(az monitor metrics alert show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${API_WEBTEST_NAME}" \
    --query id -o tsv)"
  old_api_alert_json="$(az monitor metrics alert show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${API_WEBTEST_NAME}" \
    -o json)"
  mapfile -t old_api_alert_scopes < <(
    jq -r '.scopes[]' <<< "${old_api_alert_json}"
  )
  old_api_alert_component="$(
    jq -r '.criteria.componentId' <<< "${old_api_alert_json}"
  )"
  [[ "${#old_api_alert_scopes[@]}" == "2" ]] ||
    fail "${API_WEBTEST_NAME} alert must have exactly two scopes"
  ids_equal "$(
    jq -r '.criteria.webTestId' <<< "${old_api_alert_json}"
  )" "${api_webtest_id}" ||
    fail "${API_WEBTEST_NAME} alert criteria points to a different web test"
  if ! ids_equal "${old_api_alert_component}" "${FRONTEND_AI_ID}" &&
     ! ids_equal "${old_api_alert_component}" "${BACKEND_AI_ID}"; then
    fail "${API_WEBTEST_NAME} alert has an unexpected component"
  fi
  local found_webtest=false found_component=false scope
  for scope in "${old_api_alert_scopes[@]}"; do
    ids_equal "${scope}" "${api_webtest_id}" && found_webtest=true
    ids_equal "${scope}" "${old_api_alert_component}" && found_component=true
  done
  [[ "${found_webtest}" == "true" && "${found_component}" == "true" ]] ||
    fail "${API_WEBTEST_NAME} alert scopes do not match its criteria"

  rollback_cutover() {
    local exit_code=$?
    local rollback_failed=false
    trap - ERR
    set +e
    echo "Telemetry cutover failed; restoring the prior routing and alert scopes" >&2

    if [[ -n "${old_connection_string}" ]]; then
      if ! az webapp config appsettings set \
        --name "${BACKEND_APP_SERVICE}" \
        --resource-group "${AZURE_RESOURCE_GROUP}" \
        --settings \
          APPLICATIONINSIGHTS_CONNECTION_STRING="${old_connection_string}" \
        --output none; then
        rollback_failed=true
      fi
    else
      if ! az webapp config appsettings delete \
        --name "${BACKEND_APP_SERVICE}" \
        --resource-group "${AZURE_RESOURCE_GROUP}" \
        --setting-names APPLICATIONINSIGHTS_CONNECTION_STRING \
        --output none; then
        rollback_failed=true
      fi
    fi
    if [[ -n "${old_admin_resource_id}" ]]; then
      if ! az webapp config appsettings set \
        --name "${BACKEND_APP_SERVICE}" \
        --resource-group "${AZURE_RESOURCE_GROUP}" \
        --settings \
          PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID="${old_admin_resource_id}" \
        --output none; then
        rollback_failed=true
      fi
    else
      if ! az webapp config appsettings delete \
        --name "${BACKEND_APP_SERVICE}" \
        --resource-group "${AZURE_RESOURCE_GROUP}" \
        --setting-names PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID \
        --output none; then
        rollback_failed=true
      fi
    fi

    local index
    for index in "${!alert_ids[@]}"; do
      alert_name="${active_alert_names[$index]}"
      if is_feedback_publication_alert "${alert_name}"; then
        local old_feedback_enabled feedback_restore_action
        old_feedback_enabled="$(
          jq -r '.properties.enabled // false' \
            <<< "${old_alert_jsons[$index]}"
        )"
        feedback_restore_action="$(
          feedback_alert_action restore \
            "${old_alert_scopes[$index]}" \
            "${old_feedback_enabled}"
        )"
        if [[ "${feedback_restore_action}" == "delete" ]]; then
          if ! delete_scheduled_alert "${alert_ids[$index]}"; then
            rollback_failed=true
          fi
        elif ! recreate_scheduled_alert \
          "${alert_ids[$index]}" \
          "${old_alert_jsons[$index]}" \
          "${BACKEND_AI_ID}" \
          "${old_feedback_enabled}"; then
          rollback_failed=true
        fi
      elif ! recreate_scheduled_alert \
          "${alert_ids[$index]}" \
          "${old_alert_jsons[$index]}" \
          "${old_alert_scopes[$index]}"; then
          rollback_failed=true
      fi
    done

    if ! az rest \
      --method patch \
      --url "https://management.azure.com${api_webtest_id}?api-version=2022-06-15" \
      --headers "Content-Type=application/json" \
      --body "$(jq -cn \
        --argjson tags "${old_api_webtest_tags}" \
        '{tags: $tags}')" \
      --output none; then
      rollback_failed=true
    fi
    if ! az resource update \
      --ids "${api_alert_id}" \
      --set \
        "properties.scopes[0]=${old_api_alert_scopes[0]}" \
        "properties.scopes[1]=${old_api_alert_scopes[1]}" \
        "properties.criteria.componentId=${old_api_alert_component}" \
      --output none; then
      rollback_failed=true
    fi

    local restored_connection_string restored_admin_resource_id
    if ! restored_connection_string="$(az webapp config appsettings list \
      --name "${BACKEND_APP_SERVICE}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].value | [0]" \
      -o tsv)"; then
      rollback_failed=true
    elif [[ "${restored_connection_string}" != "${old_connection_string}" ]]; then
      echo "Rollback verification failed for backend telemetry routing" >&2
      rollback_failed=true
    fi
    if ! restored_admin_resource_id="$(az webapp config appsettings list \
      --name "${BACKEND_APP_SERVICE}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --query "[?name=='PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID'].value | [0]" \
      -o tsv)"; then
      rollback_failed=true
    elif ! ids_equal "${restored_admin_resource_id}" "${old_admin_resource_id}"; then
      echo "Rollback verification failed for admin telemetry routing" >&2
      rollback_failed=true
    fi

    local restored_webtest_tags expected_webtest_tags
    expected_webtest_tags="$(jq -S -c . <<< "${old_api_webtest_tags}")"
    if ! restored_webtest_tags="$(az resource show \
      --ids "${api_webtest_id}" \
      --query tags -o json | jq -S -c '.')"; then
      rollback_failed=true
    elif [[ "${restored_webtest_tags}" != "${expected_webtest_tags}" ]]; then
      echo "Rollback verification failed for ${API_WEBTEST_NAME} hidden-link" >&2
      rollback_failed=true
    fi

    local restored_api_alert_json restored_api_component
    local -a restored_api_scopes=()
    if ! restored_api_alert_json="$(az monitor metrics alert show \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --name "${API_WEBTEST_NAME}" \
      -o json)"; then
      rollback_failed=true
    else
      restored_api_component="$(
        jq -r '.criteria.componentId' <<< "${restored_api_alert_json}"
      )"
      mapfile -t restored_api_scopes < <(
        jq -r '.scopes[]' <<< "${restored_api_alert_json}"
      )
      if [[ "${#restored_api_scopes[@]}" != "2" ]] ||
         ! ids_equal "${restored_api_scopes[0]}" "${old_api_alert_scopes[0]}" ||
         ! ids_equal "${restored_api_scopes[1]}" "${old_api_alert_scopes[1]}" ||
         ! ids_equal "${restored_api_component}" "${old_api_alert_component}"; then
        echo "Rollback verification failed for ${API_WEBTEST_NAME} metric alert" >&2
        rollback_failed=true
      fi
    fi

    if [[ "${rollback_failed}" == "true" ]]; then
      echo "CRITICAL: telemetry rollback was incomplete; inspect App Service and alert scopes immediately" >&2
      exit 70
    fi
    exit "${exit_code}"
  }
  trap rollback_cutover ERR

  if [[ "${target}" == "backend" ]]; then
    az webapp config appsettings set \
      --name "${BACKEND_APP_SERVICE}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --settings \
        APPLICATIONINSIGHTS_CONNECTION_STRING="${target_connection_string}" \
        PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID="${target_ai_id}" \
      --output none
  else
    az webapp config appsettings set \
      --name "${BACKEND_APP_SERVICE}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --settings \
        APPLICATIONINSIGHTS_CONNECTION_STRING="${target_connection_string}" \
      --output none
    az webapp config appsettings delete \
      --name "${BACKEND_APP_SERVICE}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --setting-names PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID \
      --output none
  fi

  local feedback_transition_action
  if [[ "${target}" == "frontend" ]]; then
    feedback_transition_action="$(
      feedback_alert_action frontend "${BACKEND_AI_ID}" true
    )"
    [[ "${feedback_transition_action}" == "delete" ]] ||
      fail "frontend feedback-alert transition must delete"
    delete_feedback_publication_alerts
  fi

  local index
  for index in "${!alert_ids[@]}"; do
    alert_name="${active_alert_names[$index]}"
    if is_feedback_publication_alert "${alert_name}"; then
      if [[ "${target}" == "frontend" ]]; then
        continue
      fi
      feedback_transition_action="$(
        feedback_alert_action backend "${old_alert_scopes[$index]}" true
      )"
      [[ "${feedback_transition_action}" == "backend-enabled" ]] ||
        fail "backend feedback-alert transition must enable"
      recreate_scheduled_alert \
        "${alert_ids[$index]}" \
        "${old_alert_jsons[$index]}" \
        "${BACKEND_AI_ID}" \
        true
    else
      recreate_scheduled_alert \
        "${alert_ids[$index]}" \
        "${old_alert_jsons[$index]}" \
        "${target_ai_id}"
    fi
  done

  local new_api_webtest_tags
  new_api_webtest_tags="$(jq -c \
    --arg frontend "${frontend_link_key}" \
    --arg backend "${backend_link_key}" \
    --arg target "${target_link_key}" \
    'del(.[$frontend], .[$backend]) | .[$target] = "Resource"' \
    <<< "${old_api_webtest_tags}")"
  az rest \
    --method patch \
    --url "https://management.azure.com${api_webtest_id}?api-version=2022-06-15" \
    --headers "Content-Type=application/json" \
    --body "$(jq -cn \
      --argjson tags "${new_api_webtest_tags}" \
      '{tags: $tags}')" \
    --output none
  az resource update \
    --ids "${api_alert_id}" \
    --set \
      "properties.scopes[0]=${api_webtest_id}" \
      "properties.scopes[1]=${target_ai_id}" \
      "properties.criteria.componentId=${target_ai_id}" \
    --output none

  local live_connection_string live_admin_resource_id
  live_connection_string="$(az webapp config appsettings list \
    --name "${BACKEND_APP_SERVICE}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].value | [0]" \
    -o tsv)"
  [[ "${live_connection_string}" == "${target_connection_string}" ]] ||
    fail "backend App Service telemetry routing does not match ${target_name}"
  live_admin_resource_id="$(az webapp config appsettings list \
    --name "${BACKEND_APP_SERVICE}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --query "[?name=='PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID'].value | [0]" \
    -o tsv)"
  if [[ "${target}" == "backend" ]]; then
    ids_equal "${live_admin_resource_id}" "${target_ai_id}" ||
      fail "admin telemetry resource does not match ${target_name}"
  else
    [[ -z "${live_admin_resource_id}" ]] ||
      fail "admin telemetry resource must be unset outside the trusted backend boundary"
    verify_feedback_publication_alerts_absent
  fi

  for index in "${!alert_ids[@]}"; do
    alert_name="${active_alert_names[$index]}"
    alert_id="${alert_ids[$index]}"
    if is_feedback_publication_alert "${alert_name}"; then
      if [[ "${target}" == "frontend" ]]; then
        continue
      fi
      alert_json="$(az rest \
        --method get \
        --url "$(scheduled_alert_url "${alert_id}")" \
        -o json)"
      jq -e \
        --arg backend "${BACKEND_AI_ID}" \
        '(.properties.scopes | length) == 1
         and (.properties.scopes[0] | ascii_downcase)
             == ($backend | ascii_downcase)
         and .properties.enabled == true' \
        <<< "${alert_json}" >/dev/null ||
        fail "${alert_name} is not enabled on authenticated backend telemetry"
      continue
    fi
    alert_scope="$(az rest \
      --method get \
      --url "$(scheduled_alert_url "${alert_id}")" \
      --query "properties.scopes[0]" -o tsv)"
    ids_equal "${alert_scope}" "${target_ai_id}" ||
      fail "${alert_name} is not scoped to ${target_name}"
  done

  az resource show \
    --ids "${api_webtest_id}" \
    --query tags -o json |
    jq -e \
      --arg target "${target_link_key}" \
      --arg other "${other_link_key}" \
      '.[$target] == "Resource" and has($other) == false' >/dev/null ||
    fail "${API_WEBTEST_NAME} hidden-link did not migrate cleanly"

  local live_api_alert_json
  live_api_alert_json="$(az monitor metrics alert show \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --name "${API_WEBTEST_NAME}" \
    -o json)"
  jq -e \
    --arg webtest "${api_webtest_id}" \
    --arg target "${target_ai_id}" \
    --arg other "${other_ai_id}" \
    '
      def lower: ascii_downcase;
      (.criteria.webTestId | lower) == ($webtest | lower)
      and (.criteria.componentId | lower) == ($target | lower)
      and (.scopes | length) == 2
      and any(.scopes[]; (lower == ($webtest | lower)))
      and any(.scopes[]; (lower == ($target | lower)))
      and all(.scopes[]; (lower != ($other | lower)))
    ' <<< "${live_api_alert_json}" >/dev/null ||
    fail "${API_WEBTEST_NAME} alert did not migrate cleanly"

  trap - ERR
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  case "${1:-}" in
    backend-preflight) backend_preflight ;;
    backend-cutover) telemetry_cutover backend ;;
    rollback-to-frontend) telemetry_cutover frontend ;;
    frontend-resolve) frontend_resolve ;;
    *)
      echo "Usage: $0 {backend-preflight|backend-cutover|rollback-to-frontend|frontend-resolve}" >&2
      exit 2
      ;;
  esac
fi
