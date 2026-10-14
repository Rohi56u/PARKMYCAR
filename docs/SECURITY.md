# Security and privacy notes

The hosted gateway owns authentication. `PARKMYCAR_TRUSTED_SITES_GATEWAY=1` is valid only behind that trusted gateway. On another host, leave it off until a verified identity adapter exists. Never accept arbitrary public identity headers as proof of an operator or administrator.

The new Site is owner-private. Bootstrap allows its signed-in owner to claim the first administrator role. The SQL owner record prevents later ownership claims. After setup, set `PARKMYCAR_ALLOW_BOOTSTRAP=0` and deploy that environment revision before broader sharing. Team membership is separate from Site access: a visitor needs both Site access and an assigned application role for protected work.

Authorization runs server-side on every operation. Operators can update only assigned facilities. Reviewers cannot change listings/team membership. Admins cannot impersonate operator occupancy observations. Owner role cannot be edited or removed through team routes. Revoking a membership takes effect on the next request.

Writes use strict Zod contracts, a bounded streaming JSON reader, same-origin mutation checks, parameterized SQL and atomic batches. Listing publication checks the submitted version; competing writes fail rather than overwrite unseen edits. Moderation applies observation/audit/state atomically. Driver reports are untrusted until reviewed.

Sources are HTTPS reference links, rendered through React escaping. The server does not fetch arbitrary submitted URLs. A source declaration is not automatically verified evidence; the administrator must check its contents and reuse rights.

No payment, bank, plate or persistent trip-history data is collected. Precise trip origin/destination are not logged by application code. Place lookup deliberately sends submitted text to Photon; the UI explains this in Data & privacy. The database caches public result objects under hashed keys without user association for up to seven days, not a user-linked journey history. The provider URL is server configuration only; user inputs cannot choose endpoints, credentials or redirect targets. A secret salt and UTC day are combined with the caller identifier before hashing for public limits. Use a cryptographically random `RATE_LIMIT_SALT`, configure it only in runtime secrets and rotate if compromised. Do not include `.dev.vars`, environment secrets, service tokens or runtime databases in archives.

Residual risks: anonymous reports need human review; named sources can be wrong or stale; public links can change; hosting logging/access policies need separate operational review. Tests are not a penetration test or security certification. Review dependency updates, backups, operator identity checks and incident handling before a public rollout.
