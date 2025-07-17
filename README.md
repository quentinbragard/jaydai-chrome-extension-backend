# Jaydai Chrome Extension Backend

This repository contains the FastAPI backend used by the Jaydai Chrome extension.

## Environment Variables

The API relies on several environment variables for Supabase and Stripe.
For local development copy `.env.example` to `.env` and adjust the values.

```
SUPABASE_URL=<your-supabase-url>
SUPABASE_SERVICE_ROLE_KEY=<your-supabase-service-role-key>
STRIPE_SECRET_KEY=<your-stripe-secret-key>
STRIPE_WEBHOOK_SECRET=<your-stripe-webhook-secret>
STRIPE_PLUS_MONTHLY_PRICE_ID=<your-stripe-monthly-price-id>
STRIPE_PLUS_YEARLY_PRICE_ID=<your-stripe-yearly-price-id>
```

The Chrome extension's frontend also requires Stripe URLs that integrate with
`chrome.identity.getRedirectURL()`. The following variables **must only contain
pathnames**, not the full URL:

```
VITE_STRIPE_SUCCESS_URL=/stripe/success
VITE_STRIPE_CANCEL_URL=/stripe/cancel
```

When building the redirect URL in the extension, use
`chrome.identity.getRedirectURL()` to obtain the extension specific origin and
append these paths. The resulting URL will look like:

```
https://<extension-id>.chromiumapp.org/stripe/success
```

This HTTPS URL should then be provided to Stripe as the return URL.

## Stripe Integration

The code handling Stripe resides in the `services/stripe/` directory:

```
services/
    stripe/
        __init__.py
        stripe_config.py
        stripe_service.py
```

`stripe_config.py` loads the Stripe keys and pricing IDs from environment
variables. `stripe_service.py` contains the higher level logic for creating
checkout sessions and processing webhooks. When `routes/stripe/webhook.py`
receives an event, it delegates to
`StripeService.handle_webhook_event`, which updates the `stripe_subscriptions`
and `users_metadata` tables so the user model reflects the latest subscription
state.

## Running Tests

Install the dependencies and run the tests with `pytest`:

```bash
pip install -r requirements.txt
pytest tests/ --cov=./ --cov-report=term
```

The test suite expects the environment variables from `.env.example` to be
available. Copy that file to `.env` and adjust the values or export the
variables before running the tests.
