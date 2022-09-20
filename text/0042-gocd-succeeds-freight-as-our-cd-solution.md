* Start Date: 2022-09-20
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/11
* RFC Status: draft

# Summary

To meet the growing demands of continuous deployment (CD) at Sentry, this RFC proposes [gocd](https://www.gocd.org/) as [Freight’s](https://www.notion.so/Freight-and-the-Deployment-Pipeline-7a7541decb8c4c1a8fb3741f49d3018b) successor and the foundation upon which scalable pipelines for CD are built internally. Freight can only run one sequential pipeline per deployment, and has over many years accumulated enough complexity hindering feature development, maintenance, and scaling. While the ability to customize the UI is greatly limited with an out-of-the-box solution, we (the Dev Infra team) believe gocd’s UI will meet the majority of needs with minimal workarounds.

# Motivation

In its current state Freight represents very primitive pipelining technology. Deployment of a service (e.g. sentry, snuba, relay) is limited to a single, sequential pipeline. Pipelines, and tasks within pipelines can’t execute asynchronously and with dependency relationships. There isn’t even functionality to pass values throughout tasks in a pipeline. Further, as Freight is not a task scheduler and instead is designed to run on a single host, CD cannot be horizontally scaled.

Freight has been around for many years, and as primary contributors are no longer here it has been in maintenance mode for a long time. In short, it’s a collection of docker containers running outdated software tied to a lot of messy disk state on an outdated host machine. The bespoke software and processes that support it, from `dockerctl` to `freight-cli` to `getsentry-deploy` to `fab`, represent a lot of brittle and error-prone tech debt.

A more specific example among many: Freight uses postgres extensively and alembic as its SQL driver at the app-level - no one knows what alembic is and this actually resulted in some downtime as a recent Freight migration had to be figured out adhoc. As you can imagine, working on Freight locally (so as to not incur downtime) is difficult as well.

Here’s a non-exhausative list of some recent feature requests as the engineering organization grows:

- canary deployments
- gradual/slower/segmented rolling deploys
- in-flight and rapid rollbacks
- self-service customization of sensitive deploy configurations
- adaptation to single-tenant and future hybrid cloud deployment CD workflows (deploying to GKE clusters in separate google projects)

The general-purpose pipelining tech that would be suitable for supporting such workflows exists today, and instead of reinventing the wheel we could just start using it. Pipeline composition  would unlock a realm of possibility - a 1% canary deploy could block a 10% deploy, could block 100%. Work like checking CI for a particular sha of a service could only be done once, the result cached as a prerequisite for all relevant dependent pipelines. A Single Tenant s4s deploy could block the other Single Tenant deploy pipelines, so deploy verification can actually be enforced and only vetted deploys and rollbacks would ever go out - in parallel.

# Background

This proposal came out of the burgeoning increase in Freight feature requests, and general pressure from a growing engineering headcount. After numerous attempts to improve upon Freight and refactor out its worst tech debt proved difficult, [alternatives were researched](https://www.notion.so/Freight-Alternatives-599df0a3143b4ea387cd7f90657c81e6) and gocd emerged as a candidate worth exploring further. During Hackweek 2022, Josh [worked on a PoC](https://hackweek.getsentry.net/projects/-N9ly7zt7AJ8104Q4UGF/partial-implementation-of-freight-in-gocd) which showed a representative subset of Freight functionality successfully implemented in gocd.

# Options Considered

**Continue building Freight.** See *Motivation*. A few recent efforts have improved the frontend to keep things going, but fundamentally Freight is just not a sufficient foundation on the backend of things to build future pipelines.

1. **ArgoCD.** Jason (ex-Sentry) on Operations worked briefly on a PoC for this, but there is little documentation as to why it was chosen before. It is not general-purpose pipelining technology, which is what we want. It can be summarized as what Josh likes to describe as “an airplane cockpit for k8s”; a detailed visualization of rollout progress of k8s cluster(s). It does not provide the ability to construct custom deployment pipelines at all, it is mostly a k8s controller with a web UI that is concerned exclusively with syncing k8s cluster(s) to the desired state.
2. **[gocd](http://gocd.org)**. General-purpose, mature (2007) pipelining tech. Provides server software responsible for managing pipelines (controlled by a Web UI) and scheduling tasks onto agents. A very simple system, and easy to understand. Generic; if you wanted agent hosts to interact with k8s clusters, you would have to put k8s client software on those agents. [The pipelining model](https://docs.gocd.org/current/introduction/concepts_in_go.html) connects pipelines to pipelines, whereas pipelines are the top-level execution construct in other systems I’ve seen.
3. **[Tekton](https://tekton.dev/)**. Like gocd, Tekton is general-purpose pipelining tech. It’s a young project (2018) donated by Google to cd.foundation. Tekton is deployed in a k8s cluster, and as such Tekton executors have k8s abilities builtin, but are generic otherwise; it is not strictly a k8s controller like ArgoCD. Compared to gocd, it’s a complex system with moving parts in k8s. The UI, Tekton Dashboard, isn’t particularly purposeful or focused and feels like a thin CRUD layer on top of Tekton’s k8s CRDs (don’t think normal users would want to edit something like ClusterTriggerBindings).
4. Argo Workflows. The same company that made ArgoCD, also made this. It’s pretty much analogous to Tekton except the UI is more confusing and hard to navigate.
5. We also surveyed general task running systems (most of which are in the data science realm), but in the end wanted a more CD-focused solution, as the system we’ll be building should exclusively be used for CD and not running unrelated tasks.

# Rollout Plan

We’re aiming for gocd to first reach feature parity with Freight’s getsentry and snuba deployments (as this would represent most of overall feature parity - relay-pop deployments would involve figuring out multiple gke clusters), then a cutover period will be introduced where gocd is the place for those deployments and Freight the rest.

In the first frictionful days following the release, we’ll:

- provide education and support in internal comms channels
- port over the remaining deployments
- begin to adapt gocd to Single Tenant deploys and beyond (hybrid cloud)

When deployment parity with Freight is reached, [freight.getsentry.net](http://freight.getsentry.net) will redirect to an internal doc describing how to use gocd.

# Drawbacks

There would be some initial delayed gratification since feature parity with Freight would have to be reached first before making it internally available, and naturally some friction as engineers onboard to the new way of CD. However, note that these drawbacks would apply to any Freight alternative.

# Unresolved questions

This RFC does not take the needs of the upcoming Hybrid Cloud initiative into account as they are still in flux at the time of writing. However, gocd is more than customizable enough that we would be confident in being able to meet those needs. Much more confident than if we were to extend Freight.

Note that Hybrid Cloud will most likely resemble Single Tenant from an architectural standpoint, and so gocd for Single Tenant will have already laid down much of the groundwork.
