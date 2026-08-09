\set ON_ERROR_STOP on

\if :{?identity_name}
\else
  \echo 'identity_name is required'
  \quit 2
\endif

\if :{?identity_object_id}
\else
  \echo 'identity_object_id is required'
  \quit 2
\endif

SELECT
  EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles
    WHERE rolname = :'identity_name'
  ) AS role_exists,
  EXISTS (
    SELECT 1
    FROM pg_catalog.pgaadauth_list_principals(false)
    WHERE rolename::text = :'identity_name'
  ) AS mapping_exists,
  EXISTS (
    SELECT 1
    FROM pg_catalog.pgaadauth_list_principals(false)
    WHERE rolename::text = :'identity_name'
      AND objectid::text = :'identity_object_id'
      AND principaltype::text = 'service'
  ) AS mapping_matches
\gset

\if :role_exists
  \if :mapping_matches
    \echo 'Labs worker Microsoft Entra principal mapping already matches'
  \else
    \echo 'Existing PostgreSQL role does not match the requested managed identity object ID'
    SELECT
      rolename,
      principaltype,
      objectid,
      tenantid
    FROM pg_catalog.pgaadauth_list_principals(false)
    WHERE rolename::text = :'identity_name';
    \quit 3
  \endif
\else
SELECT format(
  'SELECT * FROM pg_catalog.pgaadauth_create_principal_with_oid(%L, %L, %L, false, false);',
  :'identity_name',
  :'identity_object_id',
  'service'
)
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_catalog.pg_roles
  WHERE rolname = :'identity_name'
)
\gexec
\endif

SELECT
  EXISTS (
    SELECT 1
    FROM pg_catalog.pgaadauth_list_principals(false)
    WHERE rolename::text = :'identity_name'
      AND objectid::text = :'identity_object_id'
      AND principaltype::text = 'service'
  ) AS mapping_verified
\gset

\if :mapping_verified
  \echo 'Labs worker Microsoft Entra principal mapping verified'
\else
  \echo 'Labs worker Microsoft Entra principal mapping is missing'
  \quit 4
\endif
