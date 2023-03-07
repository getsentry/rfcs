- Start Date: 2023-02-15
- RFC Type: feature
- RFC PR: https://github.com/getsentry/rfcs/pull/75
- RFC Status: draft

# Summary

Enrich spans with thread id and name information.

# Motivation

Connecting profiling and performance products without thread information is currently resulting in a confusing and not very accurate user experience - for example, profiling always shows the entire span tree even though the "user view" is scoped to only a single thread. Similarly, we are attempting to show functions executed during the lifetime of a span in our performance product, but without thread information, we are left at guessing the best thread to show or havign to pick a default value (main) which is inaccurate at best. This RFC outlines the changes required to add the necessary span information that would enable us to improve that experience on both products.

# Supporting Data

Inaccurate and bad user experience in profiling and performance.

Metrics:
No usage metrics, but this was requested by customers.

# Options Considered

This section outlines what data we need to collect and which field to store it under followed by possible optimizations and benchmarks at the end.

In order to accurately determine which spans were part of which thread and what code was being executed during the lifetime of a span, we need a way to accurately identify the two. An identifier that gives us sufficient accuracy is the thread identifier, a nice benefit of which is that it will remain unique across different processes which might be running our SDKs. Collecting thread id information also seems like standard practice in open telemetry (https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/semantic_conventions/span-general.md#general-thread-attributes), so we would not be inventing anything new by adopting it - if anything, it brings us closer to otel which also marks thread.id and thread.name as recommended instead of required attributes.

Marking thread id as a recommended attributes also gives us flexibility in terms of only collecting the data while there is an active profiler session - I currently do not have strong reasoning to suggest that we should be collecting it all the time, if you think it could be beneficial, please add a comment.

The common data type for a thread identifier is uint64 (also the one we currently use in profiling) and one that we likely should be using.

Suggestion:
- collect thread.id on spans regardless if profiling is enabled or not
- collect thread.id on spans only during an active profiling session


Where do we store the data?
There are two places where we could store thread information - either on the span data dict and using setData or by adding new fields to the span object. The former has the benefit of a prexisting API, we would only have to ensure the data is properly set while the later seems more involved and might have infrastructure implications. Since the data dict is public, we would probably want to ensure that users do not override the thread information or discard it if they do - it sounds like acceptable risk to me.

# Drawbacks

Spans can span (pun not intended) multiple threads and could be started or stopped by different threads than they originated from. If we wanted to be more precision, we would need to track which thread a span was ended by which thread - this seems excessive and something we can add later.

One obvious drawback is that by design, we would also be collecting some of the data twice (at least the thread ids) which is inefficient. The better solution and one optimized for payload size/performance would have probably been to create some sort of shared structure that both profiling and performance could reference, I think if we wanted to go that way it would be a part of a larger effort and should be out of scope for this proposal.

Some platforms also provide different ways of obtaining the thread id (e.g. python with get_ident and get_native_id) and we would need to ensure consistency between the different sites where we would collect this data.

Benchmarks (ran on M1 mbp)
<details><summary>Ruby 3.2.1 ~3ms (wall time)</summary>

```ruby
require 'benchmark'
 
puts Benchmark.measure {
  50_000.times do
    Thread.current.object_id
  end
}
```
</details>

<details><summary>Python3 ~20ns (wall time, get_ident seems to be 3x faster at ~7ns)</summary>

```bash
python3 -m timeit -s "from threading import get_native_id" "get_native_id()"
```
</details>

<details><summary>Cocoa 0.05ms (wall time)</summary>

```swift
(void)measureThreadHandle {
    [self measureBlock:^{
        ThreadHandle::current()->tid();
    }];
}
```
</details>

Network payload impact
- ~7 bytes for the field, depends exactly what we pick "thread_id", thread.id" or maybe the shorter version "tid"?
- 4 bytes for uint64.

Assuming constant thread.id collection, this pans out to roughly ~10 bytes per span + some for initializing the data field in case none is yet present.

I took a sample transaction from our sentry.io dashboard and and added a random tid (from a limited set of 10 random tids) to each span. The transaction had 33 spans and adding the thread.id field + in some cases also initializing the data field resulted in a raw size increase of 1.5KB. After compressing with gzip (-6 level), the difference between the two was only 230B or about 0.03% increase compared to total size.

Possible format optimization:
Since spans already include a link to their parent span via the parent_span_id field value, the tid information could be omitted as long as it matches that of the parent span. This way we could save some bytes of transfer. One pitfall of this approach is that it makes the raw format more obscure and forces everyone to construct the span tree or follow long chains of parent/child relationships to figure out what span the thread was started on. Seeing how fast the calls to get thread identifiers are, this would also be sensitive to a performance impact greater than the one of just calling the get handlers each time.

# Unresolved questions
- Should breadcrumbs also track thread ids?
