* Start Date: 2022-09-26
* RFC Type: feature
* RFC PR: https://github.com/getsentry/rfcs/pull/15
* RFC Status: approved
* RFC Driver: [Michi Hoffmann](https://github.com/cleptric)

# Summary

Allow a user to decide if an exception/error is considered `handled: true` or `handled: false`.

# Motivation

A common way to integrate Sentry into a PHP framework is to utilize the framework's error handler stack.

```php
use Psr\Http\Message\ServerRequestInterface;
use Throwable;
use function Sentry\captureException;

public function logException(
    Throwable $exception,
    ?ServerRequestInterface $request = null,
    bool $includeTrace = false
): void {
    captureException($exception);

    parent::logException($exception, $request, $includeTrace);
}
``` 

This creates the problem, that all exceptions/errors are now considered `handled: true`.

# Proposal

## Expose the handled property through the  `EventHint`

Allow a user to set the `handled` property through the `EventHint`.

Instead of calling `captureException()`, people can access the `handeled` property by manually creating an event and passing in the desired `mechansim` to the `EventHint`, which then gets passed to `captureEvent()`.


```php
$hint = EventHint::fromArray([
    'exception' => $exception,
    'mechanism' => new ExceptionMechanism(ExceptionMechanism::TYPE_GENERIC, false),
]);

captureEvent(Event::createEvent(), $hint);
```

# Other Options Considered

## Add `captureUnhandledException()`

Add a new global method to allow a user to capture unhandled exceptions explicitly.

## Add `bool $handled = true` as an optional parameter to `captureException()`

Add a fourth argument to `captureException()` to allow a user to set the `handled` property.
