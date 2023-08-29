- Start Date: 2023-05-24
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/98
- RFC Status: draft

# Summary

Small files are more expensive to upload than larger files. Larger files are better able to ammortize the costs of an upload on a byte-for-byte basis. When considering the latency cost of uploading one large file versus many small files, the single large file can be up to 300x faster in workloads commonly experienced by the Sentry org. When considering total network utilization larger files can utilize up to 5000x more networking resources than smaller files over some interval.

Batching is a common feature of high-performance, network-oriented software. As an example, we utilize this behavior every day when publishing with Kafka producers.

This RFC seeks to codify a system of batching and addressing files.

# Creating Batched Files

A process listens for a tuple of (key, file) and records them in a buffer on accept().

```python
buffer = []
for (key, file_part) in listener.accept():
   buffer.append((key, file_part))
```

This buffer collects messages until any number of the following conditions are met:

- The deadline expires (e.g. the process must commit every 5 seconds).
- The total size of the batched-file exceeds the limit (e.g. 10MB).
- The total number of file-parts exceeds the limit (e.g. 5000 file-parts accumulated).
- The consumer has forced a commit operation.
  - Presumably to gracefully shutdown the process.

When a commit has been requested the file-parts are merged and the metadata is recorded in the database.

```python
def create_batch(parts):
   # All files expire 90-days from insert regardless of the actual retention period. It is
   # cheaper to store the data than to split the parts into bucketed files.
   expiration_date = datetime.now() + timedelta(days=90)

   # Filename is randomly generated with 90 day retention.
   filename = f"90/{uuid.uuid4().hex}"

   # Two buffers are initialized.  One for the file and one for the rows.
   batched_file = b""
   rows = []

   # The parts are iterated.  The buffers are appended to with their appropriate
   # metadata entries.
   for part in parts:
      start = len(batched_file)
      batched_file += part["message"]
      end = len(batched_file) - 1

      rows.append(
         {
               "end": end,
               "filename": filename,
               "key": part["key"],
               "start": start,
               "is_archived": False,
               "expiration_date": expiration_date,
         }
      )

   upload_file(filename=filename, file_bytes=batched_file)
   record_metadata_rows(rows)
```

Failure to record the metadata rows will lead to a new batch being created from the prior buffer once the consumer recovers. The orphaned file will still exist in GCS. This presents a risk for accidental PII leaks. Idea: we could store an "is_committed" flag on the row. If the rows are inserted first in an "un-committed" state and the transition to the committed state never occurs we delete the file from GCS and prune the rows (e.g. bulk-insert, upload, bulk-update; if no bulk-update delete blob and uncommitted rows).

# Tracking Byte-Ranges

Byte-ranges are tracked in a database (presumably Postgres).

```SQL
CREATE TABLE file_part
(
   `created_at` DATETIME,
   `expiration_date` DATETIME,
   `key` VARCHAR(64),
   `filename` VARCHAR(64),
   `start` INTEGER,
   `end` INTEGER,
   `is_archived` BOOLEAN
)
```

- `created_at`: The date the row was inserted.
- `expiration_date`: The date the row expires and should be deleted.
- `key`: A unique reference to an external business object.
- `filename`: The name of the batched-file in storage.
- `start`: The starting byte of the file-part.
- `end`: The ending byte of the file-part (inclusive).
- `is_archived`: Boolean indicated whether the file has been soft-deleted or not.

`created_at`, `expiration_date`, `filename`, `start`, `end` are internal to the batched-file system and are not exposed to third-parties.

`key` allows third-parties to lookup their file-range by a value they know how to generate. `key` has no meaning to the batched-file system.

`is_archived` allows customers to remove file-parts from view and must be exposed.

# Reading Byte-Ranges

GCS and S3 expose ranged reads natively. Local filesystem reads will use typical FileIO operations to return the range. A filename, start-byte, and end-byte are required to range-read data from storage.

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

# Retention Period Deletion

When the retention-period expires the life-cycle policy in GCS will automatically expire the blob. To clean-up the database, an async process must delete all file-part rows once their retention-period has expired.

```SQL
DELETE FROM file_part WHERE expiration_date < now()
```

Queries for rows past their `expiration_date` must return the empty set.

# Soft-Deleting Byte-Ranges

User deletes or otherwise non-urgent deletion semantics can archive the file-part to prevent it from being displayed to the user. The file-part must not be deleted. It is necessary to perform a "hard-delete" should future circumstances require that.

```python
def archive_file_part(file_part: FilePartModel) -> None:
    file_part.is_archived = True
    file_part.save()
```

# Hard-Deleting Byte-Ranges

A byte-range can be hard-deleted by downloading the remote file, replacing the offending bytes, and re-uploading to the same location as the file was download from. This replaces the file (and its TTL). The file-part rows do not need to be updated.

TTL refresh means the maximum retention-period for the file is the retention-period \* 2.

```python
def delete_and_zero_file_part(file_part: FilePartModel) -> None:
    message = "File-parts must be archived prior to deletion to prevent concurrent access."
    assert file_part.is_archived, message

    blob = io.BytesIO(download_blob(file_part.filename))
    zero_bytes_in_range(blob, start=file_part.start, length=(file_part.end - file_part.start) + 1)
    upload_blob(file_part.filename, blob)

    file_part.delete()


def zero_bytes_in_range(blob: io.BytesIO, start: int, length: int) -> None:
    blob.seek(start)
    blob.write(b"\x00" * length)
    blob.seek(0)
```

# Conclusion

Buffering files can provide significant throughput and cost advantages and poses minimal downside. Kafka is the suggested implementation mechanism for batching files. It has strong client support for batched network-operations and is a well understood software-system within Sentry.
