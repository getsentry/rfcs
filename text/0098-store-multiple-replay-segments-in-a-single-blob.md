- Start Date: 2023-05-24
- RFC Type: decision
- RFC PR: https://github.com/getsentry/rfcs/pull/98
- RFC Status: draft

# Summary

Recording data is sent in segments. Currently each segment is written to its own file. Writing files is the most expensive component of our GCS usage. It is also the most expensive component, in terms of time, in our processing pipeline. By merging many segment files together into a single file we can minimize our costs and maximize our Kafka consumer's throughput.

# Motivation

1. Minimize costs.
2. Improve throughput.

# Background

This document exists to inform all relevant stakeholders of our proposal and seek feedback prior to implementation.

# Supporting Data

Google Cloud Storage lists the costs for writing and storing data as two separate categories. Writing a file costs $0.005 per 1000 files. Storing that file costs $0.02 per gigabyte. For the average file this works out to: $0.000000012 for storage and $0.00000005 for the write.

In practical terms, this means 75% of our spend is allocated to writing new files.

# Proposal

First, a new table called "recording_byte_range" with the following structure is created:

| replay_id | segment_id | filename | start | stop  |
| --------- | ---------- | -------- | ----- | ----- |
| A         | 0          | file.txt | 0     | 6241  |
| B         | 0          | file.txt | 6242  | 8213  |
| A         | 1          | file.txt | 8214  | 12457 |

This table will need to support, at a minimum, one write per segment. Currently, we recieve ~350 segments per second at peak load.

Second, the Session Replay recording consumer will not _commit_ blob data to GCS for each segment. Instead it will buffer many segments and flush them all together as a single blob to GCS. In this step it will also make a bulk insertion into the database.

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

Third, when a client requests recording data we will look it up in the "recording_byte_range" table. From it's response, we will issue as many fetch requests as there are rows in the response. These requests may target a single file or many files. The files will be fetched with a special header that instructs the service provider to only respond with a subset of the bytes. Specifically, the bytes that related to our replay.

The response bytes will be decompressed, merged into a single payload, and returned to the user as they are now.

# Drawbacks

- Deleting recording data from a GDPR request, project deletion, or a user delete request will require downloading the file, overwriting the bytes within the deleted range with null bytes (`\x00`) before re-uploading the file.
  - This will reset the retention period.
  - This is an expensive operation and depending on the size of the project being deleted a very time consuming operation.

# Unresolved Questions

1. Can we keep the data in GCS but make it inaccessible?

   - User and project deletes could leave their data orphaned in GCS.
     - We would remove all capability to access it making it functionally deleted.
   - GDPR deletes will likely require overwriting the range but if they're limited in scope that should be acceptable.
     - Single replays, small projects, or if the mechanism is infrequently used should make this a valid deletion mechanism.
     - The data could be encrypted, with its key stored on the metadata row, making it unreadable upon delete.

2. What datastore should we use to store the byte range information?

   - Cassandra, Postgres, AlloyDB?
   - Postgres likely won't be able to keep up long-term.
     - Especially if we write multiple byte ranges per segment.
   - Cassandra could be a good choice but its not clear what operational burden this imposes on SnS and Ops.
   - AlloyDB seems popular among the SnS team and could be a good choice.
     - It can likely interface with the Django ORM. But its not clear to me at the time of writing.
   - Whatever database we use must support deletes.

# Extensions

By extending the schema of the "recording_byte_range" table to include a "type" column we can further reduce the number of bytes returned to the client. The client has different requirements for different sets of data. The player may only need the next `n` seconds worth of data, the console and network tabs may paginate their events, and the timeline will always fetch a simplified view of the entire recording.

With the byte range pattern in place these behaviors are possible and can be exposed to the client. The ultimate outcome of this change is faster loading times and the elimination of browser freezes and crashes from large replays.

This will increase the number of rows written to our database table. We would write four rows whereas with the original proposal we were only writing one. Therefore we should select our database carefully to ensure it can handle this level of write intensity.