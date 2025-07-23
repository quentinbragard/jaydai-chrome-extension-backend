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
