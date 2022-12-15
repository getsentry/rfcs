* Start Date: 2022-10-27
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/31

# Summary

Sentry supports GitHub and Gitlab Code Owners files for auto-assigning Issues. However, Sentry only supports 100K characters as the file size limit for Code Owners. GitHub supports a 3Mb file size for Code Owners.

This is increasingly becoming a pain point for Enterprise customers who want to use their Code Owners files as is.

# Motivation

There are two reasons behind the importance of this change

### Pain Point for Enterprise Customers

Enterprise Customers want to use their existing Code Owners files and do not want to reduce their file sizes using wild cards just because Sentry cannot handle the same size as Github. In the past, we already made an exception for select orgs and support a 200K char file size for them.

### Code Owners Increases Auto Assignment

As we make efforts to increase the signal-to-noise ratio in our notifications and Issue stream - Being able to answer “Who is this Issue important for?” is a necessary opinion that Sentry needs to build. Code Owners enables auto assignment of Issues which is one of the clearest signals of issue ownership we have today. We want more auto assignment of Issues in Sentry and thus we need more Orgs to use Code Owners

# Goals:

1. Users can upload a Code Owners File Size that's up to 3Mb in size
2. The processing time to calculate assignments should not increase significantly. 

# How it Works (simplified)

We have Code Mappings that map the transformation of the source code to the production build. Code Mappings help us reverse-engineer the file paths from an error’s stacktrace to source code file paths. 

A customer can apply a Code Mapping to a CODEOWNERS file to get the file paths that should match against the stacktrace file paths. The transformed output is stored in `sentry_projectcodeowners` and is what Sentry will use to determine assignments.

When Sentry ingests a new event, we go through each line in our transformed CODEOWNERS and see if each line has a match across any of the frames in the stacktrace. We only use the last matching line for the assignment.

# Current System Constraints

- We store the original and transformed CODEOWNERS file in a `sentry_projectcodeowners` row. However to prevent overloading Postgres from queries on every event, we cache the row in Memcache. Memcache can only support 1mb. Rows larger than 1mb will hit the database directly. Since we store the original and transformed CODEOWNERS in the same row, files larger than 500k chars will exceed this limitation.
- On each event, the assignment calculation is currently O((m*l + o)*n) time complexity, where *m* is the # of lines in the CODEOWNERS file, *l* is the number of code mappings mapped to the project, *o* is the number of lines in the Ownership Rules and n is the number of lines in the stacktrace. Essentially quadratic.
- We recalculate the assignment for each event, even if the Ownership Rules and CODEOWNERS file has not been updated.

# Proposal

First we need baseline metrics. We need to know how long it currently takes a worker to calculate the assignments with a 100k file.

> Memcache can only support 1mb.

To handle Memcache’s 1mb limit, we can zip to compress the rows and store that. However, we need to consider the memory limits of our workers during the unzip process. We need to consider the impact of (3mb CODEOWNERS raw file  + 3mb CODEOWNERS transformed file)* x number of code mappings applied to that file for a project is potentially unbounded. Two options:

- We can implement a limit on the number of codemappings per (repository, project)
- We can run the calculation in batches
 

> The calculation is currently O((m*l + o)*n) time complexity

To handle the quadratic time complexity, we can use Aho-Corasick Algorithm to bring the time complexity down to O(n). [https://pyahocorasick.readthedocs.io/en/latest/](https://pyahocorasick.readthedocs.io/en/latest/) Open to better algorithm suggestions.

A simple optimization is to only try to find matches on the first `in_app` frame of a stacktrace, similar to Commit Context. This would bring the time complexity down to O(n).


> We recalculate the assignment for each event

We can store the assignments and skip the calculations for new events. We already started storing the Code Owners assignments in the `sentry_groupowner` table as a part of the Commit Context project. Since we currently make the assumption that our grouping algorithm is accurate, we can assume that the stacktrace for each event in a group will be the same. Currently, we store the Suspect Committer assignment for 7 days before we re-calculate on new events. And we can follow the precedent set by Commit Context.
