- Start Date: 2022-09-01
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/5

# Summary

This is a detailed description of the internal caching architecture of symbolicator.

# Motivation

We want to have a place where the high level infrastructure is written down in detail.
It should have a description of the intended workflow and the requirements that the solution should satisfy.

# Background

This document should inform any future changes to the underlying code, which right now is a bit convoluted.

# Supporting Data

We have seen that having long-lived caches is crucial to the performance and stability of our symbolication pipeline.
There were incidents related to not having enough caches available.

On the other hand we want to be confident to roll out changes that refresh caches in a timely fashion.

# Current architecture

The following diagram should highlight the current architecture for fetching files and computing caches based on those,
as well as highlight all the control flow related to request coalescing.

```mermaid
graph TD
    subgraph computation [Compute Cache File]
        compute([Compute Cache File])
        run-computation[Run Computation]
        save-cache[Save Cache to File]
        compute --> run-computation
        run-computation --> save-cache
        save-cache --> complete-task

        complete-task([Computation Finished])
    end

    subgraph get-cached [Get Cached File]
        get-cached-file([Get Cached File])
        get-cached-file --> cache-exists
        cache-exists{{Current Cache Exists?}}
        old-exists{{Old Version Exists?}}
        computation-running{{Computation Running?}}
        use-old-version[/Use Old Cache Version/]
        compute-new[/Compute New Cache/]
        spawn-computation[/Spawn Computation/]
        await-computation[/Wait for Computation/]

        cache-exists -- yes --> load-cache
        cache-exists -- no --> old-exists

        old-exists -- yes --> use-old-version
        old-exists -- no --> compute-new

        use-old-version -. lazily .-> spawn-computation
        use-old-version --> load-cache

        compute-new -- eagerly --> spawn-computation
        compute-new --> await-computation

        spawn-computation --> computation-running

        computation-running -- yes --> wait-task
        computation-running -- no --> spawn-task

        spawn-task{.}
        wait-task{.}

        wait-task -. waits for .-> complete-task
        spawn-task -. spawn .-> compute

        complete-task -. completes .-> await-computation

        await-computation --> load-cache

        load-cache([Load Cached File])
    end

    subgraph get-file-graph [Get File]
        get-file([Get File])

        construct-candidates[Construct Candidates list]
        fetch-candidates[Fetch all Candidates]
        pick-candidate([Pick best Candidate])

        get-file --> construct-candidates --> fetch-candidates

        fetch-candidates -. for each candidate .-> get-cached-file

        fetch-candidates --> pick-candidate
    end

    subgraph get-symcache [Get SymCache]
        find-object[Find Object]

        get-bcsymbolmap[Fetch BCSymbolMap]
        get-il2cpp-map[Fetch Il2Cpp Mapping]

        compute-symcache[Compute SymCache]

        find-object --> get-bcsymbolmap --> compute-symcache
        find-object --> get-il2cpp-map --> compute-symcache

        find-object -..-> get-file
        pick-candidate -..-> find-object
        compute-symcache -..-> get-cached-file
        load-cache -..-> compute-symcache
    end
```

# Drawbacks of current Design

There is currently one main drawback in particular related to "lazy cache computation": The lazy computations have a
concurrency limit, but no queue. This currently works well to limit the impact of cache refreshes on the infrastructure,
but it can potentially lead to very long tails until a refresh was fully rolled out.

This also has customer visible impact, as we cannot say for certain when a targeted fix was indeed rolled out.
