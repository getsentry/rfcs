- Start Date: 2026-03-27
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/157
- RFC Status: draft

# Summary

This RFC proposes adopting distroless (minimal) base Docker images across Sentry's containerized applications, replacing the standard Debian-based images currently in use. A distroless image contains only the application and its runtime dependencies — no shell, no package manager, no standard Linux utilities. This significantly reduces image size and the number of OS-level packages that can be exploited or need to be tracked for vulnerabilities.

We had an internal TSC talk about this, see [Notion](https://www.notion.so/sentry/3208b10e4b5d8086a18ff52013025b3a).

# Motivation

Standard base images (e.g. `python:3.x-slim`, `node:24-slim`) ship with hundreds of OS packages that the application itself never uses. These packages:

- Expand the attack surface — each package is a potential vulnerability vector.
- Add ongoing maintenance burden — every new CVE in an unused package still requires triage and remediation.
- Increase image size — more packages mean more storage, more bandwidth to pull images, and slower deployments.

Switching to distroless addresses all three problems at once. The security benefit is structural: there are simply fewer things that can go wrong, regardless of whether any given CVE is actually exploitable in our environment.

# Background

A **distroless** image is a Docker image stripped down to the bare minimum needed to run a specific language runtime. The concept was introduced by Google and has since been adopted broadly. Key properties:

- No shell (`/bin/sh`, `bash`, etc.)
- No package manager (`apt`, `pip` system-wide, etc.)
- No standard Linux utilities (`curl`, `wget`, `ls`, etc.)
- Only the application binary/runtime and its direct OS-level dependencies

This makes the image unsuitable as a general-purpose Linux environment, which is exactly the point: an attacker who finds a way in cannot easily pivot or execute arbitrary commands.

Note that Alpine Linux, while smaller than Debian, is not distroless — it still ships a shell, a package manager (`apk`), and general-purpose utilities. It reduces image size but does not meaningfully reduce the attack surface in the same way.

There are several providers of distroless-style images. The main options evaluated are covered in [Options Considered](#options-considered).

# Supporting Data

## Chartcuterie (Node.js)

| Base image | Uncompressed size | OS packages | OS vulns (C/H/M/L) |
|---|---|---|---|
| `node:24.14.0-slim` | 1.47 GB | 288 | 1455 (3/148/659/644) |
| `dhi.io/node:24-debian13` | 287 MB | 12 | 10 (0/1/2/7) |

**5× smaller image, 99% fewer OS vulnerabilities.**

See: https://github.com/getsentry/chartcuterie/pull/216

## Snuba (Python)

| Base image | Uncompressed size | OS vulns |
|---|---|---|
| Debian slim | 2.96 GB | 949 |
| Google Distroless | 517 MB | 114 |
| Docker Hardened Images | 528 MB | 20 |

See: https://github.com/getsentry/snuba/pull/7753, https://github.com/getsentry/snuba/pull/7821

## Completed migrations

Several services have already been successfully migrated:

**Rust:**
- Conduit: https://github.com/getsentry/conduit/pull/12, https://github.com/getsentry/conduit/pull/17
- Objectstore: https://github.com/getsentry/objectstore/pull/65
- Relay: https://github.com/getsentry/relay/pull/4940
- Symbolicator: https://github.com/getsentry/symbolicator/pull/1791
- Tempest: https://github.com/getsentry/tempest/pull/166

**Python:**
- Reload: https://github.com/getsentry/reload/pull/340
- other smaller internal services

**Node.js:**
- Chartcuterie: https://github.com/getsentry/chartcuterie/pull/216

# Options Considered

## Option 1: Docker Hardened Images (dhi.io) — recommended

Docker Hardened Images (DHI) are minimal, hardened base images published by Docker Inc.

**Pros:**
- Apache 2.0 license — no restrictions for self-hosted use
- Full tag support (pinnable versions, not just `:latest`)
- Fast updates: e.g. `dhi.io/python:3.13-debian13` tracks `3.13.x` with regular patch releases
- Available for Python, Node.js, and other runtimes we use

**Cons:**
- Requires Docker login to pull from `dhi.io` directly (mitigated by our mirroring approach)
- Some build systems (e.g. CloudBuild) have issues with hard links in the images — affected workloads should be migrated to GitHub Actions

## Option 2: Google Distroless

Google's original distroless images at `gcr.io/distroless/`.

**Pros:**
- Apache 2.0 license
- Well-established, widely used

**Cons:**
- Slower upstream updates: e.g. `distroless/python3-debian13` lagged behind the latest Python patch release
- Limited tag granularity for some runtimes

This is still a valid option for Rust (cc-debian12), and was used in the first wave of migrations (Relay, Objectstore, Conduit, Symbolicator, Tempest).

## Option 3: Chainguard Images

**Pros:**
- Very minimal and hardened

**Cons:**
- Free tier only supports `:latest` tag — pinning specific versions requires a paid subscription
- Licensing restrictions affect self-hosted deployments

Not suitable given our self-hosted distribution requirements.

## Option 4: Wiz OS

**Pros:**
- Hardened base images

**Cons:**
- Vendor lock-in
- Licensing issues for self-hosted

Not suitable for the same reasons as Chainguard.

## Option 5: Do nothing

Keep using standard slim images, continue triaging CVEs in packages we do not use.

This is not a good use of engineering time and leaves unnecessary attack surface in place.

# Drawbacks

## Debugging is harder

Distroless containers have no shell. You cannot `exec` into a running container and run arbitrary commands. Debugging requires:

- Attaching an ephemeral debug container with a shell to the running pod (e.g. [`sentry-kube debug`](https://github.com/getsentry/sentry-infra-tools/blob/main/sentry_kube/cli/debug.py))
- Using application-level tooling (e.g. interactive shells provided by the framework) rather than OS-level tools, e.g. `getsentry shell`
- Investing in proper observability (logs, metrics, tracing) instead of ad-hoc inspection

## Runtime dependencies can be surprising

Applications sometimes rely on OS-level packages in ways that are not obvious from the code — fonts, shared libraries, locale data, CA certificates, etc. These need to be identified before or during migration.

**Example:** A migration surfaced a missing fonts dependency that caused a runtime failure. The fix was straightforward once identified, but it required a production incident to discover it. Smoke tests on the built image, or comprehensive self-hosted test runs, would catch these earlier.

## Build system compatibility

Some CI/CD build systems have compatibility issues with certain distroless image formats (e.g. hard links). Services affected should migrate to GitHub Actions before or alongside the distroless migration.

# Unresolved questions

- **Long-term commitment to DHI:** Despite Docker Inc having a history of unexpected licensing and policy changes (Hub rate limiting, Desktop licensing, etc.), DHI was recently made public under Apache 2.0, and a rollback of that decision seems unlikely. If needed, Google Distroless is a practical drop-in fallback — it lags a few patch versions behind but is otherwise compatible. Other solutions may also emerge over time.
- **Smoke tests / image validation in CI:** Should we require a standard CI step that runs basic smoke tests against a newly built distroless image before publishing? This would catch missing runtime dependencies (like the fonts incident) before they reach production.
- **Snuba and getsentry:** These are the largest remaining Python services. The Snuba PoC (https://github.com/getsentry/snuba/pull/7753, https://github.com/getsentry/snuba/pull/7821, https://github.com/getsentry/snuba/pull/7829, https://github.com/getsentry/ops/pull/19824) showed it is feasible. What is the sequencing and who owns driving this to completion?
- **Local development compatibility:** Are there any blockers that might disrupt local development workflows when switching to distroless? So far this appears to be a non-issue — for example, Snuba distroless containers work fine in `sentry devservices` (https://github.com/getsentry/snuba/pull/7829).
- **Services with non-trivial runtime deps:** Some services (e.g. uptime-checker with OpenSSL for certificate validation, or services using external libraries) may need extra work. Are there any blockers that make distroless infeasible for them?
- **Standardizing the dev variant:** The `-dev` variant of DHI images (which includes a shell and debugging tools) is useful for development builds and troubleshooting. Should we define a standard pattern for multi-stage Dockerfiles that use `-dev` at build time and the minimal image at runtime?
