# Automatic code mappings

* Start Date: 2022-09-26
* RFC Type: decision
* RFC PR: <https://github.com/getsentry/rfcs/pull/15>

## Summary

We are looking into creating code mappings automatically for organizations that have code source management installed.

We will initially target orgs with Github installations with Python and JS projects (when source maps are available) that do *not* have code mappings already in place.
Other source code management integrations and projects will be considered in the future.

## Motivation

There are various features not available to customers when code mappings are not in place for projects that have stacktraces (see background section for more details). Reducing the number of projects without code mappings will increase the value provided to customers. Those features are also required in order to reduce the "notify everyone" problem that Sentry currently suffers from.

## Background

Sentry wants developers to have context in issue details that allows them to easily identify and fix issues. Context includes the following:

* Code Context
  * Stack Trace Links ([link](https://docs.sentry.io/product/integrations/source-code-mgmt/github/#stack-trace-linking) to docs)
  * Commit Context (Suspect Commits) ([link](https://docs.sentry.io/product/releases/suspect-commits/) to docs)
* Assignee Context
  * Code owners/Ownership rules

Properly set up code mappings is required in order to enable the proper functioning of the features listed above.

## Supporting Data

About 20% of repos connected to Sentry have code mappings and very few have both the stack trace and source code root values set which can lead to improper stack trace linking and code assignments. For complete data follow [link for staff](https://www.notion.so/sentry/Deriving-Code-Mappings-9086faaf3fed4faca69e8b35f8f70e26#bae13a87214d4f52b936e0e1aa6829ec).

## Details

A code mapping allows going from a stackframe module path to a source file in the preferred source code management tool:

<img src="0013-code-mapping-logic.png" width="500px" />

The process is quite simple. Give a stacktrace frame, we look for the file name in all of the repos we have access for a customer's Github org. For instance, given the stacktrace path `sentry/integrations/gitlab/client.py` look for `integrations/gitlab/client.py` and if there is a unique match we have determined all the values for the code mapping. For the curious, a rudimentary POC (only for Python atm) can be viewed and tested [here](https://gist.github.com/armenzg/40ba48fff217815842c4fe16047d0835).

Our initial thoughts are to run a **scheduled task** that will look for projects without code mappings. For each of those projects look at analyzing various stack traces and add code mappings for the modules that there are exact matches.

Alternatively, we could analyze stack traces when new issues are generated when there are no code mappings for a project. I believe this approach would be wasteful.

NOTES:

* POC for JS still need to be completed
* POC testing of a different API approach than the Search API is still needed
  * Rated at 30 requests per minute; not scalable
  * Only default branch; limiting our potential options
  * Inaccurate at times (as per @asottile-sentry)

### Considerations

* Not all projects have a platform set (e.g. other), thus, we will need to look at file extensions
* There are some orgs that have more than one Github org associated to their Sentry org
  * I don't think this is a problem
* There are some projects that have code from more than one repository
* Some projects have more than one code mapping per repository for a given project
  * For instance, Sentry has `sentry` and `sentry_plugins` code mappings
* In the stack traces we will have frame for projects that are 3rd party libraries (e.g. `requests`)
  * If the org vendors the package in at least one repo we may end up creating a code mapping to it
    * Potential for a bug since it may be pointing to an old vendored version
    * Issues come with info about packages. I wonder if in some cases we may be able to detect this.
* Not all orgs will have granted us access to All their Github repositories upon installation (or modified it later)
  * This will reduce the number of exact matches
* As part of the automation we will be creating Repository objects
  * If we end up adding a lot of repos for the org we may be indirectly causing UI issues when there’s no proper pagination including dropdowns
* Available APIs
  * Search API (proven to work in POC)
    * The [Search API](https://docs.github.com/en/rest/search#rate-limit) has a rate limit of 30 requests per minute, thus, at best we could create 30 code mappings per minute
      * **UNKNOWN** We may be able to create multiple tokens to increase the capacity 
  * [Repositories](https://docs.github.com/en/rest/repos/repos#list-organization-repositories) + [Trees API](https://docs.github.com/en/rest/git/trees#get-a-tree)
    * To be investigated in current sprint (**UNKNOWN**)
    * Using the `recursive` parameter returns all objects in the repo (almost 12k)
* Code map derivation has not yet been tested against JS stack traces (**UNKNOWN**)
  * Scheduled to be tackled in current sprint

## Drawbacks

None I can think of.

## Unresolved questions

* We are leaning toward not notifying users that code mappings were added to a project that did not have code mappings since they didn't even know there were missing out in any features. In the future, in cases where code mappings are already in place for a project, we will need to re-evaluate and discuss it since we may cause workflow regressions for ownership rules.
