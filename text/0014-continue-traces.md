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

$transactionContext = TransactionContext::fromHeaders($sentryTraceHeader, $baggageHeader);
$transaction = startTransaction($transactionContext);

```

In case someone starts another nested transaction without passing in any context, a new trace will be started and the Dynamic Sampling Context is lost as well.
Using transactions inside transactions was a workaround as the span summary view was not available back then.

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

Inside `TransactionContext::__contruct`, we could check for an ongoing transaction on the Hub and continue the trace automatically.

# Drawbacks/Impact

- This will increase the public API surface of our SDKs
- Depending on the option, it's either more complex or more magical.