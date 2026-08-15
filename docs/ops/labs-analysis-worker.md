# Labs analysis worker

> **Summary:** Provision, enable, verify, and roll back the isolated Labs
> analysis pipeline introduced for issue #619.
> **Use when:** Deploying or diagnosing the PostgreSQL outbox, Service Bus
> queue, or Container Apps Job that computes Labs environmental response.

## Architecture and safety boundary

Production uses:

```text
API -> PostgreSQL job/outbox -> Service Bus -> Container Apps Job -> PostgreSQL
```

The queue carries one opaque job UUID, never athlete data. The worker runs at
most one 1-vCPU/2-GiB execution globally, processes one message, and exits.
Source revision, consent, correlation, and deletion-tombstone fences are
rechecked before a result is written.

`PRAXYS_LABS_EXECUTION_MODE=service_bus` never falls back to API-process
compute. Dispatch failures remain in the transactional outbox for retry.

## Prerequisites

- The change containing `alembic/versions/d95e6f7a8b9c_add_labs_analysis_jobs.py`
  is deployed, and the backend has applied that migration.
- Azure CLI, GitHub CLI, `psql`, and access to `rg-trainsight`.
- GitHub package-admin access for the one-time GHCR visibility change.
- The repository `STATSIG_SDK_KEY` secret and `STATSIG_ENV=production`
  variable used by the backend. The worker reuses them for authoritative
  per-account eligibility.
- The existing action group `praxys-feedback-ag`, Log Analytics workspace
  `log-trainsight`, and backend Application Insights component
  `appi-praxys-backend`.
- An operator session that can manage PostgreSQL Entra administrators. The
  worker principal itself is deliberately non-admin.

## Steps

### 1. Register the deployment controls

The worker DSN contains no password. Its username must exactly match the
user-assigned identity name:

```bash
gh secret set PRAXYS_LABS_DATABASE_URL \
  --body "postgresql://id-praxys-labs-worker@praxys-pg.postgres.database.azure.com:5432/praxys?sslmode=require"
gh variable set PRAXYS_LABS_WORKER_DEPLOY_ENABLED --body "false"
```

Keep `PRAXYS_LABS_EXECUTION_MODE` absent or `inline` at this stage. The queue
and worker must be healthy before the API publishes production jobs.

### 2. Provision the Azure resources

The GitHub OIDC principal remains resource-group Contributor and cannot
register providers or create role assignments. It does need one subscription
read action so the workflow can fail before Bicep when a required provider is
unregistered. Before the first deployment, sign in as a subscription Owner or
another principal with provider-registration, custom-role, and role-assignment
authority:

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
CICD_CLIENT_ID="<value stored in the GitHub AZURE_CLIENT_ID secret>"
CICD_OID=$(az ad sp show --id "$CICD_CLIENT_ID" --query id -o tsv)

ROLE_NAME="Praxys Provider Registration Reader"
ROLE_FILE=$(mktemp)
jq -n \
  --arg role_name "$ROLE_NAME" \
  --arg scope "/subscriptions/$SUBSCRIPTION_ID" \
  '{
    Name: $role_name,
    IsCustom: true,
    Description: "Read Azure resource-provider registration state only.",
    Actions: ["Microsoft.Resources/subscriptions/providers/read"],
    NotActions: [],
    DataActions: [],
    NotDataActions: [],
    AssignableScopes: [$scope]
  }' >"$ROLE_FILE"
if [ "$(az role definition list --name "$ROLE_NAME" \
  --query 'length(@)' -o tsv)" = "0" ]; then
  az role definition create --role-definition "$ROLE_FILE"
fi
rm -f "$ROLE_FILE"
az role assignment create \
  --assignee-object-id "$CICD_OID" \
  --assignee-principal-type ServicePrincipal \
  --role "$ROLE_NAME" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"

for provider in \
  Microsoft.ServiceBus \
  Microsoft.App \
  Microsoft.ManagedIdentity; do
  az provider register --namespace "$provider" --wait
  test "$(az provider show --namespace "$provider" \
    --query registrationState -o tsv)" = "Registered"
done
```

The workflow checks all three providers before Bicep runs and fails with no
partial deployment if any is not registered.

Run the dedicated workflow once after its commit is on `main`. With deployment
disabled, this first run publishes the GHCR package without touching Azure:

```bash
gh workflow run deploy-labs-worker.yml --ref main
RUN_ID=$(gh run list --workflow=deploy-labs-worker.yml --limit 1 \
  --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

GitHub creates new container packages as private. Open
`github.com/orgs/praxys-run/packages/container/praxys-labs-worker/settings`,
choose **Change visibility**, and set the package to **Public**. This is a
one-time GitHub UI operation; the supported Packages REST API exposes package
visibility but does not provide an update endpoint. Verify the result:

```bash
gh api /orgs/praxys-run/packages/container/praxys-labs-worker \
  --jq .visibility
```

The command must print `public`. Enable deployment and rerun the workflow:

```bash
gh variable set PRAXYS_LABS_WORKER_DEPLOY_ENABLED --body "true"
gh workflow run deploy-labs-worker.yml --ref main
RUN_ID=$(gh run list --workflow=deploy-labs-worker.yml --limit 1 \
  --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

The workflow logs out of GHCR and pulls the exact SHA tag anonymously before
the Azure deployment job can start.

The Bicep deployment creates or reconciles:

- one Basic Service Bus namespace tagged `praxysComponent=labs-analysis`;
- queue `labs-environment-response`;
- Container Apps environment `cae-praxys-jobs`;
- job `praxys-labs-environment-worker`;
- user-assigned identity `id-praxys-labs-worker`;
- `praxys-labs-queue-backlog` and `praxys-labs-dead-lettered` alerts.

RBAC remains an explicit privileged bootstrap rather than making the GitHub
deployment principal an effective resource-group Owner. The first enabled run
creates the resources and then fails closed at `Verify runtime RBAC` until an
authorized operator applies these exact-scope grants:

```bash
RG="rg-trainsight"
QUEUE_ID=$(az servicebus queue show -g "$RG" \
  --namespace-name "$(az servicebus namespace list -g "$RG" \
    --query "[?tags.praxysComponent=='labs-analysis'].name | [0]" -o tsv)" \
  -n labs-environment-response --query id -o tsv)
WORKER_OID=$(az identity show -g "$RG" -n id-praxys-labs-worker \
  --query principalId -o tsv)
APPINSIGHTS_ID=$(az resource show -g "$RG" -n appi-praxys-backend \
  --resource-type Microsoft.Insights/components --query id -o tsv)

BACKEND_IDENTITY=$(az webapp identity show -g "$RG" -n trainsight-app -o json)
BACKEND_SB_CLIENT_ID=$(gh variable get PRAXYS_LABS_SERVICE_BUS_CLIENT_ID \
  --json value --jq .value 2>/dev/null || true)
if [ -n "$BACKEND_SB_CLIENT_ID" ]; then
  BACKEND_SENDER_OID=$(jq -r --arg client_id "$BACKEND_SB_CLIENT_ID" \
    '(.userAssignedIdentities // {}) | to_entries[]
     | select(.value.clientId == $client_id) | .value.principalId' \
    <<<"$BACKEND_IDENTITY" | head -1)
else
  BACKEND_SENDER_OID=$(jq -r '.principalId // empty' <<<"$BACKEND_IDENTITY")
fi
test -n "$BACKEND_SENDER_OID"

az role assignment create \
  --assignee-object-id "$BACKEND_SENDER_OID" \
  --assignee-principal-type ServicePrincipal \
  --role "Azure Service Bus Data Sender" \
  --scope "$QUEUE_ID"
az role assignment create \
  --assignee-object-id "$WORKER_OID" \
  --assignee-principal-type ServicePrincipal \
  --role "Azure Service Bus Data Receiver" \
  --scope "$QUEUE_ID"
az role assignment create \
  --assignee-object-id "$WORKER_OID" \
  --assignee-principal-type ServicePrincipal \
  --role "Monitoring Metrics Publisher" \
  --scope "$APPINSIGHTS_ID"
```

Leave `PRAXYS_LABS_SERVICE_BUS_CLIENT_ID` absent to use the backend
system-assigned identity. If a dedicated user-assigned sender is required,
attach it to `trainsight-app`, set that GitHub variable to its client ID, deploy
the backend setting, and run the same bootstrap. Rerun the worker workflow
after the grants; it resolves the same effective identity as runtime and
requires all three exact-scope assignments before continuing. The public GHCR
image contains no deployment secret.

After cutover, `deploy-backend.yml` waits up to 15 minutes for the Container
Apps Job to report the exact `ghcr.io/praxys-run/praxys-labs-worker:<commit>`
image before deploying that backend commit. The worker workflow mirrors every
backend trigger, including science-only changes and API release tags. A failed
or delayed worker deployment therefore blocks the newer backend instead of
letting an older worker cancel a future-model job.

### 3. Create the least-privilege PostgreSQL principal

Get the worker identity object ID:

```bash
IDENTITY_NAME="id-praxys-labs-worker"
IDENTITY_OID=$(az identity show -g rg-trainsight -n "$IDENTITY_NAME" \
  --query principalId -o tsv)
test -n "$IDENTITY_OID"
```

Principal mapping and object grants require two different authorities:

1. a PostgreSQL Microsoft Entra administrator creates or verifies the managed
   identity mapping; and
2. the backend App Service identity, which owns the Alembic-created tables,
   grants the table and column privileges.

Do not run the grants as the Entra administrator. Azure PostgreSQL Entra
administrators are not superusers and cannot grant privileges on tables owned
by the backend migration identity.

If the signed-in operator is not already an Entra administrator, add that exact
operator temporarily:

```bash
OPERATOR_NAME=$(az ad signed-in-user show --query userPrincipalName -o tsv)
OPERATOR_OID=$(az ad signed-in-user show --query id -o tsv)

az postgres flexible-server microsoft-entra-admin list \
  -g rg-trainsight -s praxys-pg -o table
az postgres flexible-server microsoft-entra-admin create \
  -g rg-trainsight -s praxys-pg \
  -u "$OPERATOR_NAME" -i "$OPERATOR_OID" -t User
```

Add a temporary client-IP firewall rule if the current machine is not already
allowed, acquire an OSS RDBMS token, and create or verify the identity mapping:

```bash
RULE="labs-worker-provision-$(date +%s)"
MY_IP="<operator-public-ipv4>"
az postgres flexible-server firewall-rule create \
  -g rg-trainsight -n praxys-pg -r "$RULE" \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP"

PGPASSWORD=$(az account get-access-token --resource-type oss-rdbms \
  --query accessToken -o tsv) \
psql "host=praxys-pg.postgres.database.azure.com port=5432 dbname=praxys user=$OPERATOR_NAME sslmode=require" \
  -v identity_name="$IDENTITY_NAME" \
  -v identity_object_id="$IDENTITY_OID" \
  -f scripts/provision_labs_worker_principal.sql

az postgres flexible-server firewall-rule delete \
  -g rg-trainsight -n praxys-pg -r "$RULE" --yes
```

The principal script compares the existing `pgaadauth` mapping with the current
managed-identity object ID. It fails instead of silently reusing a same-named
role mapped to a deleted identity. If the identity was intentionally recreated,
confirm the new object ID, update the mapping as the Entra administrator, and
rerun the script:

```sql
SECURITY LABEL FOR "pgaadauth"
ON ROLE "id-praxys-labs-worker"
IS 'aadauth,oid=<confirmed-managed-identity-object-id>,type=service';
```

After the matching principal exists and the backend deployment for this commit
is healthy, open an SSH session to the backend. The command runs under the
backend managed identity, which is the table owner because it applies Alembic
migrations:

```bash
az webapp ssh -g rg-trainsight -n trainsight-app
cd /home/site/wwwroot
python -m scripts.provision_labs_worker_db \
  --identity-name id-praxys-labs-worker
exit
```

The owner-side script refuses to proceed if any required table has a different
owner. It first revokes stale privileges on the required tables, then grants
only the source reads and Labs result/job writes needed by
`api/labs_worker.py` and verifies both the required grants and denied
columns. In particular:

- `activity_samples` is restricted to owner/activity IDs, provider, time,
  power, heart rate, and pace; GPS, altitude, temperature, and running-dynamics
  columns are denied;
- `labs_experiment_enrollments` can update only processing state and timestamps,
  never consent, attestation, source revision, or correlation fields;
- `labs_analysis_jobs` can update only attempt/processing state and timestamps;
- `user_connections` is restricted to provider status/preferences, never
  encrypted credentials or token bundles; and
- `users` is restricted to ID, email, active/admin/demo flags needed for
  Statsig targeting, never password hashes or other account metadata; and
- `training_plans` is not granted because the research worker constructs its
  request context with plan loading disabled.

Database
`CONNECT` and public-schema `USAGE` must already be available through the
server's baseline role policy, and are verified without trying to override
database or schema ownership.

If the operator was added only for this task, remove that exact temporary
administrator:

```bash
az postgres flexible-server microsoft-entra-admin delete \
  -g rg-trainsight -s praxys-pg -i "$OPERATOR_OID" --yes
```

Do not remove a pre-existing permanent administrator.

### 4. Smoke-test the idle worker

Start one manual execution while the API is still in `inline` mode:

```bash
python scripts/start_labs_worker_check.py \
  --resource-group rg-trainsight \
  --job-name praxys-labs-environment-worker
```

In `log-trainsight`, query the last 15 minutes of
`ContainerAppConsoleLogs_CL` for
`ContainerJobName_s == "praxys-labs-environment-worker"`. Confirm:

- `Database startup check OK (postgresql)`;
- `Labs worker feature-gate client ready`;
- `Labs worker startup check completed`; and
- no authentication, permission, or image-pull error.

The helper copies the live execution template, preserving its image, secrets,
environment, and resources, then overrides only the one execution's command.
It checks Statsig readiness, the worker identity, and exact table/column grants
without receiving or settling a Service Bus delivery. A missing key or Statsig
initialization failure exits before Service Bus receive, preserving queued jobs
instead of misclassifying eligible users as revoked.

### 5. Cut over the backend

```bash
gh variable set PRAXYS_LABS_EXECUTION_MODE --body "service_bus"
gh workflow run deploy-backend.yml --ref main
RUN_ID=$(gh run list --workflow=deploy-backend.yml --limit 1 \
  --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

The backend workflow discovers the namespace by its
`praxysComponent=labs-analysis` tag and writes the FQDN and queue name to App
Service. It fails before changing settings if the namespace is absent.

## Verify

1. Enroll or request a Labs recompute from an authenticated non-demo account.
2. Confirm the API reports `queued` or `processing` without request latency
   remaining open for the analysis duration.
3. Confirm Service Bus `ActiveMessages` returns to zero and the Container Apps
   job never exceeds one concurrent execution.
4. Confirm the Labs result becomes `available` or a bounded scientific
   `unavailable` state.
5. Query `praxys.labs_job` in `appi-praxys-backend`; expect
   `enqueued -> dispatched -> started -> completed` for the same pseudonymous
   user, with queue delay and duration on completion.
6. Confirm both metric alerts are enabled, Sev 2, and attached to
   `praxys-feedback-ag`.

```bash
az monitor metrics alert show -g rg-trainsight \
  -n praxys-labs-queue-backlog \
  --query '{enabled:enabled,severity:severity,actions:actions}' -o json
az monitor metrics alert show -g rg-trainsight \
  -n praxys-labs-dead-lettered \
  --query '{enabled:enabled,severity:severity,actions:actions}' -o json
```

## Failure handling

- **Outbox pending:** inspect backend logs and Service Bus sender RBAC. Do not
  run the analysis inline while `service_bus` is configured; the reconciler
  retries with bounded backoff.
- **Message retried:** transient DB/network failures are abandoned and retried
  up to three analysis attempts. The queue allows ten transport deliveries so
  temporary claim/settlement failures do not prematurely consume that analysis
  budget.
- **Dead-letter alert:** diagnose the bounded `failure_class` in
  `praxys.labs_job` and inspect the durable job state. Do not blindly replay the
  DLQ message. A terminal job rejects duplicate delivery; after fixing that
  cause, use a new user recompute. If the job is still `queued` or `retrying`,
  the reconciler republishes only the oldest globally runnable dispatch after
  the 30-minute lease window. This head-of-line fence recovers a lost delivery
  without multiplying messages during legitimate queue backlog. Let that
  active generation finish, then remove the obsolete DLQ copy.
- **Scientific unavailable/stale:** this is a successful terminal execution,
  not infrastructure failure, and must not be retried automatically.

## Rollback / Recovery

Stop new dispatch first so an inline API worker cannot overlap a still-running
Container Apps execution:

```bash
gh variable set PRAXYS_LABS_EXECUTION_MODE --body "disabled"
gh workflow run deploy-backend.yml --ref main
```

Wait for that backend deploy to finish, then confirm the Service Bus queue has
no active messages and the Container Apps Job has no running execution. After
the isolated lane is drained, return compute to the API:

```bash
gh variable set PRAXYS_LABS_EXECUTION_MODE --body "inline"
gh workflow run deploy-backend.yml --ref main
```

Wait for the inline backend deploy to finish. Then set
`PRAXYS_LABS_WORKER_DEPLOY_ENABLED=false` to stop future infrastructure
reconciliation. Leaving the scale-to-zero resources in place is the safest
rollback and has negligible idle compute cost.

For an emergency queue stop without restoring inline compute, leave
`PRAXYS_LABS_EXECUTION_MODE=disabled`; new jobs remain durable but do not
dispatch. This is a maintenance mode, not a normal production state.

## Related

- [ADR](../dev/adr-labs-analysis-isolation.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- [cost-and-scaling.md](./cost-and-scaling.md)
- `.github/workflows/deploy-labs-worker.yml` · `infra/labs-worker.bicep`

---
_Last reviewed: 2026-08-09 · Owner: @dddtc2005_
