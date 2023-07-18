- Start Date: 2023-05-24
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/98
- RFC Status: draft

# Summary

Recording data is sent in segments. Each segment is written to its own file. Writing files is the most expensive component of our Google Cloud Storage usage. It is also the most expensive component, in terms of time, in our processing pipeline. By merging many segment files together into a single file we can minimize our costs and maximize our processing pipeline's throughput.

# Motivation

1. Increase consumer throughput.
2. Minimize costs.
3. Enable new features in a cost-effective manner.

# FAQ

**Can this idea be abstracted into a generic service?**

No. Though it was not codified in this document several of my comments and my own thinking at the time alluded to me pursuing a "generic service" concept. Where a Kafka consumer would accept file-parts and perform the buffering, encrypting, and uploading for other product-focused consumers. This seemed like a good way to abstract the problem and make everyones lives easier.

However, publishing to Kafka incurs a network cost. And that cost essentially means that you lose a huge amount of throughput potential. Possibly so much throughput that the benefits of this proposal ceases to be worth relative to the complexity it introduces.

**Is this a replacement for filestore?**

No. The primary focus is on deriving a set of tools and libraries that developers can implement on their consumers. To achieve the desired levels of throughput files must be buffered in-memory.

**Can this proposal be used with filestore?**

Yes. This is additive. Filestore does not need to implement this feature-set to achieve its mission.

**Can filestore buffer files transparently for your consumer?**

Sure but you would not achieve the efficiency numbers listed elsewhere in this document. Pushing to Kafka has some network cost. Maintaining the buffer in-memory is the only way to minimize network transit cost. Regardless of destination.

To be clear, filestore absolutely can buffer if it wants to reduce costs or achieve higher throughput _for itself_ but upsteam processes will not receive any throughput improvements from its implementation.

**How large of a throughput improvement can we expect in the replay recording consumer?**

99% of the current replays task time is spent in I/O. If we assume a buffer size of 10MB we can expect a gross throughput improvement of 222,750% (see supporting data section). This value ignores the cost new operations which have not yet been measured. Those operations include:

- Encrypting the data.
- Fetching the key encryption key.
- Bulk inserting the offsets into a database.

# Supporting Data

**Network Overhead Considerations**

Consider two files. One is one-thousand bytes in size. The other is one-million bytes in size. Assuming you want to upload these file to a remote storage provider over the open internet which file will upload faster? The answer is you don't have enough information to know. The 1MB file may finish up to twice as quickly for no reason other than it followed a happier path to the data-center.

But that's not a scenario we always face. More commonly we upload from within Google's network. Additionally, its typical for consumers and storage buckets to share the same datacenter location. This reduces cost and greatly improves network reliability and performance. With these considerations in mind which file uploads faster? The answer is still "it depends". Mostly the 1KB file will upload faster than the 1MB file but it is not guaranteed. A good estimate is the 1MB file will be 33% slower on average. In other words, a 1MB file is 750x faster to upload on a byte per byte basis than a 1KB file.

What about a 10MB file? You can expect latency to be 2 to 3 times higher than a 1KB file. This makes the 10MB file 3x faster to upload than the 1MB file and 2,250x faster than the 1KB file.

There are clearly economies of scale when submitting and fetching data from a remote storage provider. What is the exepected total throughput improvement for a Replay's consumer which buffers 10MB worth of data before submitting as a single file? About 100x.

With this level of throughput improvement the Replay's recording ingestion service can be operated by a single machine.

These figures were derived from experimentation with Google Cloud Platform. Compute and storage layers were located in the Iowa data center (us-central1).

**Cost Minimization**

Google Cloud Storage lists the costs for writing and storing data as two separate categories. Writing a file costs $0.005 per 1000 files. Storing that file costs $0.02 per gigabyte. For the average Session Replay file (with a retention period of 90 days) this works out to: $0.000000012 for storage and $0.00000005 for the write.

In practical terms, this means 75% of our spend is allocated to writing new files.

Additionally, when considering the reduction in compute power needed to upload these files, the Replay's recording ingestion service could reduce its Kafka replica count by 31. A 97% reduction in compute cost.

# High Level Overview

1. We will store multiple "parts" per file.
   - A "part" is a distinct blob of binary data.
   - It exists as a subset of bytes within a larger set of bytes (referred to as a "file").
   - A "part" could refer to a replay segment or to a sourcemap or anything that requires storage in a blob storage service.
2. Each "part" within a file will be encrypted.
   - Encryption provides instantaneous deletes (by deleting the row containing the encryption key) and removes the need to remove the byte sub-sequences from a blob.
   - We will use envelope encryption to protect the contents of every file.
     - https://cloud.google.com/kms/docs/envelope-encryption
   - Related, contiguous byte ranges will be encrypted independently of the rest of the file.
   - We will use KMS to manage our key-encryption-keys.
   - Data-encryption-keys will be generated locally and will be unique.
3. Parts will be tracked in a metadata table on an AlloyDB instance(s).
   - A full table schema is provided in the **Proposal** section.
   - AlloyDB was chosen because its a managed database with strong point-query performace.
   - The metadata table will contain the key used to decrypt the byte range.
4. On read, parts will be fetched without fetching the full file.
   - More details are provided in the **Technical Details** section.

# Proposal

First, a new table called "file_part_byte_range" with the following structure is created:

| id  | key | path     | start | stop  | dek      | kek_id | created_at          |
| --- | --- | -------- | ----- | ----- | -------- | ------ | ------------------- |
| 1   | A:0 | file.bin | 0     | 6241  | Aq3[...] | 1      | 2023-01-01T01:01:01 |
| 2   | B:0 | file.bin | 6242  | 8213  | ppT[...] | 1      | 2023-01-01T01:01:01 |
| 3   | A:1 | file.bin | 8214  | 12457 | 99M[...] | 1      | 2023-01-01T01:01:01 |

- The key field is client generated identifier.
  - It is not unique.
  - The value of the key field should be easily computable by your service.
  - In the case of Session Replay the key could be a concatenation of `replay_id` and `segment_id`.
    - Illustrated above as `replay_id:segment_id`.
    - Alternatively, a true composite key could be stored on a secondary table which contains a reference to the `id` of the `file_part_byte_range` row.
- Path is the location of the blob in our bucket.
- Start and stop are integers which represent the index positions in an inclusive range.
  - This range is a contiguous sequence of related bytes.
  - In other words, the entirety of the file part's encrypted data is contained within the range.
- The "dek" column is the **D**ata **E**ncryption **K**ey.
  - The DEK is the key that was used to encrypt the byte range.
  - The key itself is encrypted by the KEK.
    - **K**ey **E**ncryption **K**ey.
  - Encryption is explored in more detail in the following sections.
- The "kek_id" column contains the ID of the KEK used to encrypt the DEK.
  - This KEK can be fetched from a remote **K**ey **M**anagement **S**ervice or a local database table.

Notice each row in the example above points to the same file but with different start and stop locations. This implies that multiple, independent parts can be present in the same file. A single file can be shared by hundreds of different parts.

Second, the Session Replay recording consumer will not commit blob data to Google Cloud Storage for each segment. Instead it will buffer many segments and flush them together as a single blob to GCS. Next it will make a bulk insertion into the database for tracking.

```mermaid
flowchart
    A[Wait For New Message] --> B[Process];
    B --> C[Push to Buffer];
    C --> D{Buffer Full?};
    D -- No --> A;
    D -- Yes --> E[Write Single File to GCS];
    E --> F[Bulk Insert Byte Ranges];
    F --> G[Clear Buffer];
    G --> A;
```

## Writing

Writing a file part is a four step process.

First, the bytes must be encrypted with a randomly generated DEK. Second, the DEK is encrypted with a KEK. Third, the file is uploaded to the cloud storage provider. Fourth, a metadata row is written to the "file_part_byte_range" containing a key, the containing blob's filepath, start and stop offsets, and the encrypted DEK.

**A Note on Aggregating File Parts**

It is up to the implementer to determine how many parts exist in a file. An implementer may choose to store one part per file or may store an unbounded number of parts per file.

However, if you are using this system, it is recommended that more than one part be stored per file. Otherwise it is more economical to upload the file using simpler, more-direct methods.

## Reading

To read a file part the metadata row in the "file_part_byte_range" table is fetched. Using the filepath, starting byte, and ending byte we fetch the encrypted bytes from remote storage. Now that we have our encrypted bytes we can use the DEK we fetched from the "file_part_byte_range" table to decrypt the blob and return it to the user.

## Deleting

To delete a file part the metadata row in the "file_part_byte_range" table is deleted. With the removal of the DEK, the file part is no longer readable and is considered deleted.

Project deletes, user deletes, GDPR deletes, and user-access TTLs are managed by deleting the metadata row in the "file_part_byte_range" table.

File parts can be grouped into like-retention-periods and deleted manually or automatically after expiry. However, in the case of replays, storage costs are minor. We will retain our encrypted segment data for the maximum retention period of 90 days.

## Key Rotation

If a KEK is compromised and needs to be rotated we will need to follow a five step process:

1. We query for every row in the "file_part_byte_range" table whose DEK was encrypted with the old KEK.
2. We decrypt every DEK with the compromised KEK.
3. We encrypt every DEK with a new KEK.
4. We update every row in the "file_part_byte_range" table with a compromised DEK with the new DEK.
5. The compromised KEK is dropped.

DEKs are more complicated to rotate as it requires modifying the blob. However, because DEKs are unique to a byte range within a single file we have a limited surface area for a compromised key to be exploited. To rotate a DEK we follow a six step process:

1. We download the file blob of the compromised DEK (there will only be one).
2. We decrypt the subset of bytes related to the compromised DEK.
3. We generate a new DEK.
4. We encrypt the decrypted bytes with the new DEK.
5. We encrypt the new DEK with any KEK.
6. We stitch the blob back together and upload to cloud storage.
7. We re-write the metadata rows.
   - New offsets are written because encryption is not guaranteed to produce the same length of bytes.
   - The compromised DEK is overwritten during this step.

**A Word on the Necessity of Key Rotation**

What's the likelihood of a DEK or KEK leaking? Probably small but larger than you think.

What happens if an exception is raised while trying to read a file? The sentry_sdk will sweep in the `locals()` from the application state. This will include KEKs, DEKs, filenames, and byte-ranges. Everything an attacker needs to read private data. This data will be presented in a human-readable format on the Sentry.io web app. This private data may even find its way into our logs (in whole or in part) providing another vector of attack.

Now, the value of the data is very small. Its not "worth" stealing. After all, we're not encrypting this data now. We're only adopting encryption to "delete" files in clever way.

However, the security and privacy of these keys is critical for us to maintain our "deletion" guarantees to customers and to regulators. Currently, when we say a file is deleted it is in fact deleted. Going forward it will still exist but will be impossible to read. That un-readability promise _has to be maintained_. Compromised keys must be rotated and strong patterns for doing so must be maintained.

# Drawbacks

- Data is only deleted after the retention period.
  - This means customer data must be protected between the deletion date and retention expiry.

# Questions

1. If KEKs are managed in a remote service how do we manage outages?
   - We manage it in the same way we manage an outage of any other remote service.
     - We will need to backlog or otherwise 400/404.
   - KEKs have the benefit of _probably_ not blocking ingest as the key will be cached for long stretches of time (24 hours) and can be used for longer periods of time if a new key can not be fetched.
2. How will read efficiency be impacted if we rely on a remote service to decrypt blob data?
   - It will have some cost but hopefully that cost is minimized by the constraints of your system.
   - For example, Session Replay fetches multiple segment blobs in a single request. At most we will need to fetch two keys (and in the majority of cases a single key) to decrypt the segments.
   - This key fetching latency is immaterial to the total latency of the request.
3. How will key rotation work in a production system?
   - Hopefully it will be a rare event.
   - KEK rotation will require re-encrypting every DEK encrypted with the KEK (typically everything in a ~24-hour period).
   - DEK rotation will require re-encrypting a sequence of bytes in a blob.

# Extensions

By extending the schema of the "file_part_byte_range" table to include a "type" column we can further reduce the number of bytes returned to the client. The client has different requirements for different sets of data. The player may only need the next `n` seconds worth of data, the console and network tabs may paginate their events, and the timeline will always fetch a simplified view of the entire recording.

With the byte range pattern in place these behaviors are possible and can be exposed to the client. The ultimate outcome of this change is faster loading times and the elimination of browser freezes and crashes from large replays.

This will increase the number of rows written to our database table. We would write four rows whereas with the original proposal we were only writing one. Therefore we should select our database carefully to ensure it can handle this level of write intensity.

# Technical Details

## Storage Service Support

The following sections describe the psuedo-code necessary to fetch a range of bytes from a service provider and also links to the documentation where applicable.

**Google Cloud Storage**

```python
from google.cloud.storage import Blob

blob = Blob(filename, bucket)
blob.download_as_bytes(start=start, end=stop)
```

Source: https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob#google_cloud_storage_blob_Blob_download_as_bytes

**AWS S3**

```python
from boto3 import client

response = client("s3", **auth).get_object(
    Bucket=bucket,
    Key=filename,
    Range=f"bytes={start}-{stop}",
)
response["Body"].read()
```

Source: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object.html

**Filesystem**

```python
with open(filename, "r") as f:
    f.seek(start)
    f.read((stop - start) + 1)  # Range is inclusive.
```

## Consumer Buffering Mechanics

The following section is highly specific to the Session Replay product.

We will continue our approach of using _at-least once processing_. Each message we receive is guaranteed to be processed to completion regardless of error or interrupt. Duplicate messages are possible under this scheme and must be accounted for in the planning of each component.

**Buffer Location and Behavior**

The buffer is kept as an in-memory list inside the consumer process. For each message we receive we append the message to the buffer. Afterwards, we check if the buffer is full. If it is we flush. Else we wait for another message.

This is a somewhat simplified view of whats happening. In reality we will use deadline flushing in addition to a count or resource-usage based flushing. This ensures the buffer does not stay partially full indefinitely.

**Buffer Flush**

On flush the buffer will take every message in the list and merge them together into a single bytes object. This bytes object will then be uploaded to the storage service-provider. Upon successful upload the start and stop byte range values of each message are stored in a database in addition to other metadata such as their replay_id and segment_id. Finally, the last offset is committed to Kafka.

**Handling Consumer Restarts**

If the consumer restarts with a non-empty buffer, the buffer's last item's offset will not be committed. When the consumer resumes it will start processing from the last offset committed (i.e. the last item in the last successfully-flushed-buffer). The buffer will be rebuilt exactly as it was prior to restart.

**Storage Service Failure**

If we can not communicate with the storage provider we have several options.

1. Catch the exception and commit the offset anyway. This means all the segments in the buffer would be lost.
2. Do not catch the exception and let the consumer rebuild the buffer from its last saved offset.
3. Catch the exception and retry.

Option three is the preferred solution but the semantics of the retry behavior can get complicated depending on how the system is constructed. For example, how long do you retry? How do retries affect message processing? Do you communicate with the service provider in a thread? If so how do you manage resources?

A blocking approach is the simplest solution but it does not offer maximum throughput.

**Managing Effects**

With a buffered approach most of the consumer's effects are accomplished in two bulk operations. However, click search, segment-0 outcome tracking, and segment-0 project lookup are not handle-able in this way. We will address each case independently below.

1. Click Tracking.
   - Click events are published to the replay-event Kafka consumer.
   - This publishing step is asynchronous and relies on threading to free up the main process thread.
   - Because we can tolerate duplicates, we can publish click-events when we see the message or when we commit a batch.
   - Neither choice is anticipated to significantly impact message processing.
2. Outcome Tracking.
   - Outcome events are published to the outcomes Kafka consumer.
   - This publishing step is asynchronous and relies on threading to free up the main process thread.
   - This operation only occurs for segment-0 events.
   - I am unsure if this step can tolerate duplicates. It likely does but if it does not we could have to commit during the flushing step.
3. Project lookup.
   - Projects are retrieved by a cache lookup or querying PostgreSQL if it could not be found.
   - This operation typically takes >1ms to complete.
   - This operation only occurs for segment-0 events.
   - Querying this information in a tight loop is not an ideal situation.
     - Forwarding the project_id to a secondary Kafka consumer would free up resources on our main consumer and allow the secondary consumer to optimize for this type of workload.
     - Alternatively, another method for looking up the project's `has_replay` flag could be found.

**Duplicate Message Handling**

1. Google Cloud Storage.
   - Unique filename generation per buffer would mean that a segment could be present in multiple files.
   - This has COGS implications but does not impact our application.
2. "file_part_byte_range" table.
   - Duplicate replay, segment ID pairs will be recorded in the table.
   - A reader must either select distinct or group by the replay_id, segment_id pair.
   - Neither row has precendence over the other but the filename value must come from the same row as the start and stop byte range values.
3. Outcome tracking.
   - Duplicate outcomes will be recorded for a given replay.
   - The replay_id functions as an idempotency token in the outcomes consumer and prevents the customer from being charged for the same replay multiple times.
4. Click tracking.
   - Duplicate click events will be inserted for a replay, segment pair.
   - This is an acceptable outcome and will not impact search behavior.
