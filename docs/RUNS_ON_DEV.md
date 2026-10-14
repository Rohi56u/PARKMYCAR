# ParkMyCar — runs-on.dev deployment

Release preparation: 19 October 2026.

## Current status

The user requested a `runs-on.dev` subdomain instead of the default hosted URL. The 1.1 India-search source, database migration and production build are prepared. No 1.1 publication or domain claim is claimed in this source export. The previous application deployment has not been replaced.

The desired first-choice name is `parkmycar`; ownership and availability must be checked in the user's authenticated runs-on.dev account. If that account already owns a name, use its actual registered hostname after confirming it is the intended destination. Do not invent a domain ownership record, deployment identifier or DNS target.

## Domain and hosting

The official [quickstart](https://runs-on.dev/docs/quickstart) describes GitHub OAuth login, one name per account, and the account eligibility checks: at least 30 days old with at least one public repository. A newly claimed name initially serves a GitHub profile card. This is not a ParkMyCar deployment.

ParkMyCar includes server routes, authorization, a D1 database and moderation workflows. Uploading only its client files to static storage does not deploy this application. The intended approach is to connect the claimed hostname to the existing backend through the hosting provider's native custom-domain feature, preserving the current access policy and database. If the provider cannot support this hostname with its authentication gateway, stop before publication and select a supported backend/authentication deployment; do not enable trusted identity headers on an arbitrary host.

## Complete the connection

1. Sign in at [runs-on.dev/manage](https://runs-on.dev/manage) using the owner's GitHub account. Confirm or claim the actual intended hostname.
2. Register that hostname with the existing application's hosting provider. Obtain the exact returned CNAME target and every ownership/TLS validation record. These values are provider-generated and cannot be filled in before registration.
3. Set those DNS records through the runs-on.dev Manage form. The registry supports a CNAME at the claimed name and TXT/CNAME validation entries at child labels. Preserve unrelated existing records. Check compatibility if the host requests multiple-label nested validation names: the registry's documented child labels are one level deep.
4. Use the provider's validation/status operation until both routing and TLS are active. Keep the current private audience. Do not use a URL redirect to the previous default hostname: the requested domain must serve the application itself.
5. Publish the exact tested source and additive migration through the backend's supported deployment workflow only after the requested domain configuration is ready.
6. Verify the new hostname directly: HTTPS, private access, real destination search, selected map position, driving/walking links, operator sign-in, and a read-only API check. Verify that requests do not redirect visitors to the old default hostname. Recheck cookies, origin checks and the authentication callback on the new origin.

The source archive does not contain passwords, API tokens or domain-account cookies. Authentication should be completed through the provider's secure sign-in flow.

## Official references

- [Claim and configure a name](https://runs-on.dev/docs/quickstart)
- [DNS record types and validation rules](https://runs-on.dev/docs/records)
- [Hosting guides](https://runs-on.dev/docs/guides)
- [Registry architecture and static hosting limitations](https://github.com/zordhalo/runs-on.dev/blob/main/docs/architecture.md)

These references were checked during preparation. A successful file upload, profile card, or pending DNS record is not evidence that ParkMyCar is live.
