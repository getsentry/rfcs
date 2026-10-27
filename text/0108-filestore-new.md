- Start Date: 2023-07-13
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/108
- RFC Status: draft

# Summary

One of the systems that Sentry internally operates today is an abstract concept referred
to as "file store".  It consists of a postgres level infrastructure to refer to blobs and
a go service also called "file store" which acts as a stateful proxy in front of GCS to
deal with latency spikes, write throughput and caching.

This RFC summarizes issues with the current approach, the changed requirements that go
into this system and proposes a path forward.

# Motivation

Various issues have occurred over the years with this system so that some decisions were
made that over time have resulted in new requirements for filestore and alternative
implementations.  Replay for instance operates seperate infrastructure that goes
straight to GCS but is running into write throughput issues that file store the Go service
solves.  On the other hand race conditions and complex blob book-keeping in Sentry itself
prevent expiring of debug files and source maps after a period of time.

The motivation of this RFC is to summarize the current state of affairs, work streams that
are currently planned are are in motion to come to a better conclusion about what should be
done with the internal abstractions and how they should be used.

# Background

The primary internal abstraction in Sentry today is the `filestore` service which itself
is built on top of Django's `files` system.  At this level "files" have names and they
are stored on a specific GCS bucket (or an alternative backend).  On top of that the `files`
models are built.  There each file is created out of blobs where each blob is stored
(deduplicated) just once in the backend of `filestore`.

For this purpose each blob is given a unique filename (a UUID).  Blobs are deduplicated
by content hash and only stored once.  This causes some challenge to the system as it
means that the deletion of blobs has to be driven by the system as auto-expiration is
thus no longer possible.

# Supporting Data

We currently store petabytes of file assets we would like to delete.

# Possible Changes

These are some plans about what can be done to improve the system:

## Removal of Blob Deduplication

Today it's not possible for us to use GCS side expiration.  That's because without the
knowledge of the usage of blobs from the database it's not safe to delete blobs.  This
can be resolved by removing deduplication.  Blobs thus would be written more than once.
This works on the `filestore` level, but it does not work on the `FileBlob` level.
However `FileBlob` itself is rather well abstracted away from most users.  A new model
could be added to replace the current one.  One area where `FileBlob` leaks out is the
data export system which would need to be considered.

`FileBlobOwner` itself could be fully removed, same with `FileBlobIndex` as once
deduplication is removed the need of the owner info no longer exists, and the index
info itself can be stored on the blob itself.

```python
class FileBlob2(Model):
    organization_id = BoundedBigIntegerField(db_index=True)
    path = TextField(null=True)
    offset = BoundedPositiveIntegerField()
    size = BoundedPositiveIntegerField()
    checksum = CharField(max_length=40, unique=True)
    timestamp = DateTimeField(default=timezone.now, db_index=True)
```

## TTL Awareness

The abstractions in place today do have any support for storage classes.  Once however
blobs are deduplicated it would be possible to fully rely on GCS to clean up on it's own.
Because certain operations are going via our filestore proxy service, it would be preferrable
if the policies were encoded into the URL in one form or another.

## Assemble Staging Area

The chunk upload today depends on the ability to place blob by blob somewhere.  Once blobs are
stored regularly in GCS there is no significant reason to slice them up into small pieces as
range requests are possible.  This means that the assembly of the file needs to be reconsidered.

The easiest solution here would be to allow chunks to be uploaded to a per-org staging area where
they linger for up to two hours per blob.  That gives plenty of time to use these blobs for
assembly.  A cleanup job (or TTL policy if placed in GCS) would then collect the leftovers
automatically.  This also detaches the coupling of external blob sizes from internal blob
storage which gives us the ability to change blob sizes as we see fit.

# Unresolved questions

TBD
