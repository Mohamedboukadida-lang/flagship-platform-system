# 0003: Keycloak and OIDC instead of built-in login

Status: accepted, 2026-11-16 (M0)

## Decision

Keycloak is the identity provider. The API never sees a password: it validates RS256 access tokens against Keycloak's published keys (signature, issuer, audience `lotse-api`, expiry), maps `sub` to a `users` row, and resolves the membership for the tenant named in the `X-Tenant` header. Authorisation comes from the database, not from token claims.

## Why

A standard protocol, self-hostable, with password policy, MFA and federation already built. Hand-rolled login is a liability.

## Alternatives

- Built-in username and password: more code to get wrong.
- A hosted identity service: conflicts with the self-hosted, EU-only goal.

## Details worth knowing

- Realm definition: `deploy/helm/lotse/files/lotse-realm.json`, imported at start by both compose and the chart. Secrets in it are environment placeholders.
- `lotse-console` is a public client with PKCE (S256) and the authorization code flow only.
- `lotse-cli` allows the password grant. It exists for smoke tests and local `curl`; remove it before real users exist.
- Access tokens live 5 minutes; refresh tokens rotate; sessions end after 8 hours.
- Keys are cached, so the API keeps validating if Keycloak is briefly down. Anything that is not a valid token is a 401.
- An unknown tenant, a malformed tenant slug and a tenant the caller is not a member of all return the same 403, so the API never confirms that a tenant exists.
- The ingress exposes only `/auth/realms` and `/auth/resources`. The admin console is reachable through a port-forward only.

## Consequences

Local development needs a running Keycloak (`make up`). Tests do not: they run their own JWKS endpoint and sign their own tokens.
