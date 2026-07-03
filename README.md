# BreachHound — Digital Identity Auditor

**BreachHound** is an enterprise-grade digital footprint auditing tool that identifies which online platforms and services are associated with a given email address. Built for identity verification teams, fraud prevention analysts, and corporate security operations, it provides rapid, automated discovery across 120+ online services.

## What does BreachHound do?

BreachHound takes an email address as input and systematically queries registration, login, and account-recovery endpoints across a wide range of online platforms. For each service, it determines whether an account associated with that email address exists, returning a structured dataset of results.

### Key use cases

| Use Case | Description |
|---|---|
| **Identity Verification** | Confirm that a user's declared digital presence matches their actual online footprint during onboarding or KYC workflows. |
| **Fraud Prevention** | Detect synthetic identities by auditing whether an email has a plausible pattern of real online registrations. |
| **Corporate Security** | Audit employee email addresses to identify shadow IT exposure — accounts on unauthorized services that may leak corporate credentials. |
| **M&A Due Diligence** | Assess the digital exposure of key personnel during mergers and acquisitions security reviews. |
| **Compliance Auditing** | Generate evidence of digital presence for regulatory compliance and risk assessments. |

### Services covered

BreachHound checks 120+ platforms across these categories:

- **Social Media** — Instagram, Twitter/X, Snapchat, Pinterest, Tumblr, and more
- **Professional** — GitHub, Atlassian, Docker, LinkedIn (via related services)
- **Productivity** — Evernote, Lastpass, Office365, WordPress
- **E-Commerce** — Amazon, eBay, Deliveroo, Nike
- **Music & Media** — Spotify, SoundCloud, Last.fm, Flickr, Imgur
- **CRM & Business** — HubSpot, Pipedrive, Zoho, Salesforce (via related services)
- **Finance** — Venmo, PayPal (via related services)
- **And many more...**

## Input configuration

The Actor accepts the following input parameters:

```json
{
    "email": "analyst@company.com",
    "proxyConfiguration": {
        "useApifyProxy": true,
        "apifyProxyGroups": ["RESIDENTIAL"]
    },
    "onlyUsed": true,
    "maxRetries": 3,
    "retryDelay": 1
}
```

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `email` | String | ✅ | — | The email address to audit for associated online accounts. |
| `proxyConfiguration` | Object | ❌ | `null` | Apify proxy configuration. Recommended for production to avoid rate limiting. |
| `onlyUsed` | Boolean | ❌ | `true` | When enabled, only services where an account was found are included in the output. |
| `maxRetries` | Integer | ❌ | `3` | Maximum number of retry attempts for checks that get rate-limited or fail due to network errors. |
| `retryDelay` | Integer | ❌ | `1` | The delay in seconds before retrying a rate-limited check (uses exponential backoff). |

> **💡 Tip:** Using Apify residential proxies (`RESIDENTIAL` group) significantly reduces rate limiting from target services and is strongly recommended for production workloads.

## Output dataset

Results are pushed to the default Apify Dataset as structured JSON objects. Each record represents one service check:

```json
{
    "email": "analyst@company.com",
    "website": "instagram.com",
    "name": "instagram",
    "status": "found"
}
```

```json
{
    "email": "analyst@company.com",
    "website": "github.com",
    "name": "github",
    "status": "not_found"
}
```

```json
{
    "email": "analyst@company.com",
    "website": "spotify.com",
    "name": "spotify",
    "status": "rate_limited"
}
```

### Status values

| Status | Meaning |
|---|---|
| `found` | An account associated with this email was positively identified on the service. |
| `not_found` | No account associated with this email was detected on the service. |
| `rate_limited` | The service rate-limited the request. Re-run with proxies or retry later. |

### Enriched fields

When available, the following additional fields may appear in the output:

| Field | Description |
|---|---|
| `emailRecovery` | Partially redacted recovery email address associated with the account. |
| `phoneNumber` | Partially redacted phone number associated with the account. |
| `others` | Additional metadata such as full name, creation date, or profile details. |

## Example full output

When `onlyUsed` is set to `true`, a typical output dataset looks like:

```json
[
    {
        "email": "analyst@company.com",
        "website": "instagram.com",
        "name": "instagram",
        "status": "found"
    },
    {
        "email": "analyst@company.com",
        "website": "spotify.com",
        "name": "spotify",
        "status": "found",
        "emailRecovery": "a*****t@gmail.com"
    },
    {
        "email": "analyst@company.com",
        "website": "github.com",
        "name": "github",
        "status": "found"
    },
    {
        "email": "analyst@company.com",
        "website": "adobe.com",
        "name": "adobe",
        "status": "found",
        "emailRecovery": "a*****t@company.com",
        "phoneNumber": "+1*****89"
    }
]
```

## Performance and reliability

- **Speed**: BreachHound runs all checks concurrently using an async execution model, completing a full audit of 120+ services in approximately 15–45 seconds depending on network conditions.
- **Error handling**: Individual module failures are isolated — a single service timeout will never crash the entire audit run. Failed checks are reported as `rate_limited` status.
- **Proxy support**: Full integration with Apify's proxy infrastructure ensures reliable, high-throughput execution suitable for batch processing.
- **Retry mechanism**: Built-in retries with exponential backoff help navigate transient rate limits and network errors automatically.

## Integrations

BreachHound works seamlessly with the Apify ecosystem:

- **Apify API** — Trigger audits programmatically via the Apify REST API or any of the official client libraries (Python, JavaScript, etc.).
- **Webhooks** — Configure webhooks to receive notifications when an audit completes.
- **Scheduled runs** — Set up recurring audits for ongoing monitoring of key email addresses.
- **Apify Storage** — Results are stored in Apify Datasets and can be exported to CSV, JSON, Excel, or integrated with external systems.

## Legal and ethical use

BreachHound is designed exclusively for **lawful and ethical purposes** including:

- Corporate security assessments with proper authorization
- Identity verification during legitimate onboarding processes
- Fraud prevention and detection within regulated frameworks
- Authorized penetration testing and security auditing

Users are responsible for ensuring their use of this tool complies with all applicable laws, regulations, and organizational policies. This tool should only be used on email addresses that you are authorized to investigate.

## Technical details

- **Runtime**: Python 3.11 on Apify Actor platform
- **Concurrency model**: Trio async nurseries for parallel service checks
- **HTTP client**: HTTPX with configurable proxy and timeout support
- **Base engine**: [Holehe](https://github.com/megadose/holehe) by Megadose (GPLv3)

## Creator
Created and maintained by **[Blukaze.com](https://blukaze.com)**.

## Support

If you encounter issues or have feature requests, please open an issue on the Actor's GitHub repository or contact the maintainer through the Apify Store.
