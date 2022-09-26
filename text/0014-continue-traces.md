* Start Date: 2022-09-26
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/14

# Summary

This RFC proposes a new way to continue a trace when creating nested transactions.

# Motivation

The current way we propagate `sentry-trace` and `baggage`, is to pass a correctly populated `TransactionContext` as the first argument to `startTransaction()`.

```php
use Sentry\Tracing\TransactionContext;
use function Sentry\startTransaction;

$transactionContext = TransactionContext::continueFromHeaders($sentryTraceHeader, $baggageHeader);
$transaction = startTransaction($transactionContext);

```

In case someone starts another nested transaction without passing in any context, a new trace will be started and the Dynamic Sampling Context is lost as well.

# Options Considered

## Add TransactionContext::fromParent()

```php
use Sentry\Tracing\TransactionContext;
use function Sentry\startTransaction;

$transactionContext = TransactionContext::fromParent($transaction);
$transaction = startTransaction($transactionContext);

public static function fromParent(Transaction $transaction)
{
    $context = new self();
    $context->traceId = $transaction->getTraceId();
    $context->parentSpanId = $transaction->getParentSpanId();
    $context->sampled = $transaction->getSampled();
    $context->getMetadata()->setBaggage($transaction->getBaggage());

    return $context;
}
```

## Add a third argument to `startTransaction()`

```php
use Sentry\Tracing\TransactionContext;
use function Sentry\startTransaction;

$transactionContext = new TransactionContext();
$transaction = startTransaction($transactionContext, [], bool $continueTrace = true);
```

This would require making the SDKs aware of the current request.
In PHP, we could rely on `$_SERVER['HTTP_SENTRY_TRACE]` and `$_SERVER['HTTP_BAGGAGE]`, but this is not possible in all languages.

# Unresolved questions

* Can we rely on `SentrySdk::getCurrentHub()->getTransaction()` to fetch the current transaction to be passed into `TransactionContext::fromParent()` ?
* How would we make `TransactionContext::__construct()` aware of the current request?
