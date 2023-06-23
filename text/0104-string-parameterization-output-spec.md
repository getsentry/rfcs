- Start Date: 2023-06-20
- RFC Type: informational
- RFC PR: https://github.com/getsentry/rfcs/pull/104
- RFC Status: draft

# String Parameterization Output Spec

## Summary

This RFC describes a spec for the output of a string parameterizer. A parameterizer is a system that accepts text strings, detects dynamic parameters in those strings, and replaces those parameters with placeholders. A parameter can be a value in a SQL query, a path segment in a URL, or any value interpolated into a string. A successful parameterizer can check a string (or a set of strings), and determine whether any part of those strings corresponds to a dynamic value.

Parameterization applies to many aspects of distributed tracing, like transaction names, span description, and breadcrumbs. For example, consider a traced application that returns cities in given countries by fetching them from a SQL database. Each SQL query will create a corresponding span, and the query will be the span’s description. Over its runtime, the application might generate these descriptions:

```sql
SELECT * FROM cities WHERE country = 'CA';
```

```sql
SELECT * FROM cities WHERE country = 'US';
```

```sql
SELECT * FROM cities WHERE country = 'AU';
```

A successful parameterizer will ingest these span descriptions, and determine that `"CA"`, `"US"`, and `"AU"` were probably a parameter inserted dynamically by the application depending on some condition. The three query descriptions are examples of this parameterized query:

```sql
SELECT * FROM cities WHERE country = ?;
```

where `?` is a country code parameter that varies from query to query.

This spec outlines standards for the output of a parameterizer, including but not limited to the desired string formatting, payload structure, and character escaping. The spec is organized by data type. Parameterization methods and infrastructure are outside the scope of this spec.

## Motivation

The main goal of parameterization is to remove dynamic values from strings, in order to group “the same” strings together. “The same” loosely means that the strings represent the same underlying resource. For example, the strings `GET /users/17` and `GET /users/781` might represent accessing the web application route `/users/:id`. The strings `SCARD org:18:active` and `SCARD org:98:active` represent access to the same kind of Redis resource, and so on. When looking at application data (traces, URLs, spans, etc.) it is most useful to look at parameterized values, because they represent aggregate behaviour. In the routing example, the `/users/:id` route is a useful entity to examine, while the unparameterized URLs are not. Parameterization enables aggregation, and aggregation makes it possible to store, query, and compare data easily.

Sentry performs parameterization in many different part of the application. The SDKs, Relay, and Ingest are three examples. There is no agreement between these parts beyond conventions. As a result, the output of parameterization is inconsistent.

Here are three ways different SDKs might parameterize a SQL query:

- `SELECT * FROM countries WHERE id = ?`
- `SELECT * FROM countries WHERE id = %s`
- `SELECT * FROM countries WHERE id = $1`

As another example, the SDKs might pass the query `SELECT * FROM country WHERE code IN (?, ?)` to Ingest, which will further parameterize that as `SELECT * FROM country WHERE code IN (?)`. The string `(?, ?)` is technically only partially parameterized from the system's perspective.

This has important downstream effects on user experience. A good parameterizer will correctly group similar strings together in a way that represents the original intent. If parameterization is successful, users will see groups that make sense to them. Good parameterization will also reduce cardinality, and therefore reduce data storage costs. A bad parameterizer will fill the users’s lists of transactions and spans with noisy similar descriptions that drown out the signal.

This spec documents the desired output of a parameterizer. This makes it possible for different parameterizers to agree, conform to a standard, share code, and create consistency in the system.

## Definitions

- **Parameter**: A substring in a span description that represents a dynamic value that was substituted in by code. e.g., in the string `/users/17`, `17` is a likely parameter
- **Parameterization**: The act of determining parameters, and replacing them with a substitution character. Also sometimes called "normalization"
- **Parameterizer**: A piece of code, or a system that performs parameterization
- **Substitution character**: A character or string of characters that denote a parameter. e.g., in the string `SELECT * FROM countries WHERE id = ?;` the `?` is a substitution character

## Overall Guidelines

- Parameterize *every* parameter. If a string contains multiple parameters, parameterize each one according to the relevant rules
- Re-order unordered parameters in alphabetical order if it does not change the meaning of the string (e.g., see “Query Strings”)
- Do not alter the string in any other way (e.g., do not re-format the whitespace, quotes, or any other symbols)

## Parameterizing SQL Commands

SQL queries usually appear in descriptions of `db` spans. In a SQL query (or any SQL statement) a parameter is any value that is either generated randomly, or supplied from a variable in the code. The following symbols are *not* considered parameters, and should not be altered or re-ordered:

- column names
- table names
- aliases

### Simple Parameters

For individual parameters, **the parameterizer must replace the parameter with a single unquoted `?` character**.

Given:

```sql
SELECT "countries"."id", "countries.name"
FROM "countries"
WHERE "countries"."code" = 'CA';
```

Return:

```sql
SELECT "countries"."id", "countries.name"
FROM "countries"
WHERE "countries"."code" = ?;
```

### Parameter Lists (`IN` Clauses)

For lists of parameters, the parameterizer must replace the entire list with a single unquoted `?` character in parentheses.

Given:

```sql
SELECT "countries"."id", "countries.name"
FROM "countries"
WHERE "countries"."code" IN ("CA", "US");
```

Return:

```sql
SELECT "countries"."id", "countries.name"
FROM "countries"
WHERE "countries"."code" IN (?);
```

### `SAVEPOINT` Commands

In `SAVEPOINT` and `ROLLBACK` commands, replace the savepoint's name with a single `?` character.

Given:

```sql
ROLLBACK TO SAVEPOINT "s47890194282880_x50"'
```

Return:

```sql
ROLLBACK TO SAVEPOINT ?
```

## Parameterizing URLs

A URL might appear in the name of a transaction, in the description of a span, as data in a breadcrumb, or some other situation. URLs might correspond to known web service endpoints, or arbitrary addresses. The parameterizer must use as much information as possible to parameterize URLs. Dynamic route segments (e.g., the `18` in `/users/18/info`), and dynamic hostname segments (e.g., the `us-east` in `us-east.service.com` vs. `ca-west` in `ca-west.service.com`) are considered parameters.

### Known Route Segments

A parameterizer that has knowledge of the route structure that the URL corresponds to must replace URL parameters with the correct route segment names.

For example, the React Router SDK has knowledge of the URL structure of the app. Therefore, a parameterizer in the SDK should refer to the route structure, and supply the names of the URL segments. The same applies to web frameworks like Django. It is also in theory possible for a parameterizer to cross-reference a URL to a known service like GitHub against GitHub’s documentation, to determine whether outgoing requests match a specific API route.

**The parameterizer must replace route parameters with the name of the parameter surrounded in curly braces.**

Given:

```
GET http://someservice.com/users/tom/
```

If the parameterizer determines that `tom` is a route parameter named `:name`, it must return:

```
GET http://someservice.com/users/{name}
```

**Note:** The parameterizer should replace the smallest possible substring. e.g., the URL `/service/id-17` should be parameterized as `/service/id-{user_id}` rather than `/service/{user_id}`.

### Unknown Route Segments

If a parameterizer does not have knowledge of the route structure, but it determines that a value within a URL is a dynamic segment, **it must replace the value with a single `*` character.**

Given:

```
GET http://someservice.com/users/tom/info
```

If the parameterizer determines that `tom` is a parameter of unknown significance, it must return:

```
GET http://someservice.com/users/*/info
```

**Note:** The parameterizer must preserve the original URL structure as much as possible. e.g., the URL `https://service.io/data/sentry/frontend/info` where both `sentry` and `frontend` are dynamic route segments, the parameterizer must return `https://service.io/data/*/*/info` rather than `https://service.io/data/*/info`.

### Subdomains

Subdomain can contain parameters, too. For example, in the URL `https://company.someservice.io/` the string `company` might correspond to a client name, and is a dynamic string.

If a parameterizer determines that a section of a domain string is dynamic, **it must replace the segment with a single `*` character.**

Given:

```
GET http://host1.someservice.com/users/
```

If the parameterizer determines that `host1` is a parameter, it must return:

```
GET http://*.someservice.com/users/
```

**Note:** The parameterizer must not alter domains or hostnames in any other way.

### Port Numbers

**If the URL contains a port number, the parameterizer should not parameterize it.**

Given:

```
GET http://someservice.com:8080/
```

Return:

```
GET http://someservice.com:8080/
```

### Auth Strings

**If the URL contains authentication strings, the parameterizer must replace them with a `*` character.**

Given:

```
GET http://admin:password@someservice.com/
```

Return:

```
GET http://*:*@someservice.com/
```

## Parameterizing Key-Value Store Key Names

Key-value stores like Redis store arbitrary data, and are accessed by a “key”, which is a string. It is a common convention to namespace these keys, delimit them with a `:` or `.` character, and put parameters between the namespaces. e.g., the order IDs of a given user might be stored under the key `organizations:18:users:9982:orders`. `18` and `9982` are parameters. `organizations`, `users`, and `orders` are namespaces.

## String Keys

**For parameters in key names, the parameterizer must replace each parameter with a single `*` character.**

Given:

```
SADD orgs:17:emails jane@myorg.com
```

Return:

```
SADD orgs:*:emails jane@myorg.com
```

## Storing Parameterization Results

**Parameterizers must keep the original value as it was sent, and add the parameterized description as a separate key in the payload.** For example, when parameterizing the `description` key of a payload:

```json
{
  "description": "POST example.com/user/123456",
}
```

The parameterizer must output:

```json
{
  "description": "POST example.com/user/123456",
	"description.scrubbed": "POST example.com/user/%s"
}
```
