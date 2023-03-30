# RFCs

This repository contains RFCs and DACIs. Lost?

- For creating a new RFC see [workflow](text/0001-workflow.md).
- For the list of open RFCs have a look [at the open pull requests](https://github.com/getsentry/rfcs/pulls).
- For the list of all accepted and live RFCs refer [to the index](#index).

## Index

- [0001-workflow](text/0001-workflow.md): The workflow RFC
- [0002-new-architecture](text/0002-new-architecture.md): Aspirational goals for a new Sentry internal architecture
- [0003-browser-js-built-in-metrics](text/0003-browser-js-built-in-metrics.md): Expanding Built-In Performance Metrics for Browser JavaScript
- [0004-import-reorg](text/0004-import-reorg.md): Sentry import reorganization
- [0005-symbolicator-caching](text/0005-symbolicator-caching.md): Detailed description of the internal caching architecture of symbolicator
- [0012-keep-job-retrying-off](text/0012-keep-job-retrying-off.md): Remove job retrying in CI for getsentry
- [0013-portable-pdb](text/0013-portable-pdb.md): New protocol fields to allow symbolicating of portable PDBs
- [0015-expose-handeled-property](text/0015-expose-handeled-property.md): Expose handeled property
- [0016-auto-code-mappings](text/0016-auto-code-mappings.md): Automatic code mappings
- [0022-response-context](text/0022-response-context.md): Response context
- [0033-view-hierarchy](text/0033-view-hierarchy.md): View Hierarchy
- [0027-manual-disabling-of-flaky-tests](text/0027-manual-disabling-of-flaky-tests.md): Processes for manually disabling flaky tests in `sentry` and `getsentry`
- [00034-sdk-lifecycle](text/0034-sdk-lifecycle-hooks.md): SDK Lifecycle hooks
- [0036-auto-instrumentation-ui-thread](text/0036-auto-instrumentation-ui-thread.md): auto-instrumentation UI thread
- [0037-anr-rates](text/0037-anr-rates.md): Calculating accurate ANR rates
- [0038-scrubbing-sensitive-data](text/0038-scrubbing-sensitive-data.md): Scrubbing sensitive data - how to improve
- [0039-sdks-report-file-IO-on-main-thread](text/0039-sdks-report-file-IO-on-main-thread.md): SDKs report file I/O on the main thread
- [0042-gocd-succeeds-freight-as-our-cd-solution](text/0042-gocd-succeeds-freight-as-our-cd-solution.md): Plan to replace freight with GoCD
- [0043-instruction-addr-adjustment](text/0043-instruction-addr-adjustment.md): new StackTrace Protocol field that controls adjustment of the `instruction_addr` for symbolication
- [0044-heartbeat](text/0044-heartbeat.md): Heartbeat monitoring
- [0046-ttfd-automatic-transaction-span](text/0046-ttfd-automatic-transaction-span.md): Provide a new `time-to-full-display` span to the automatic UI transactions
- [0047-introduce-profile-context](text/0047-introduce-profile-context.md): Add Profile Context
- [0048-move-replayid-out-of-tags](text/0048-move-replayid-out-of-tags.md): Plan to replace freight with GoCD
- [0062-controlling-pii-and-credentials-in-sd-ks](text/0062-controlling-pii-and-credentials-in-sd-ks.md): Controlling PII and Credentials in SDKs
- [0063-sdk-crash-monitoring](text/0063-sdk-crash-monitoring.md): SDK Crash Monitoring
- [0070-document-sensitive-data-collected](text/0070-document-sensitive-data-collected.md): Document sensitive data collected
- [0071-continue-trace-over-process-boundaries](text/0071-continue-trace-over-process-boundaries.md): Continue trace over process boundaries
- [0072-kafka-schema-registry](text/0072-kafka-schema-registry.md): Kafka Schema Registry
- [0073-usage-of-transaction-types](text/0073-usage-of-transaction-types.md): Usage of transaction types
- [0074-source-context-via-links](text/0074-source-context-via-links.md): Source context via links
- [0078-escalating-issues](text/0078-escalating-issues.md): Escalating Issues
- [0080-issue-states](text/0080-issue-states.md): Issue States
