"""
Footprint — Digital Identity Auditor
Apify Actor entrypoint that wraps the Holehe OSINT engine.

Bridges Holehe's trio-based async concurrency model into the Apify Actor
lifecycle. Proxy configuration from Apify is injected into the HTTPX
AsyncClient that Holehe modules consume, ensuring all outbound requests
are routed through the configured proxy infrastructure.
"""

import asyncio
import importlib
import pkgutil
import re
import time

import httpx
import trio
from apify import Actor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMAIL_FORMAT = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
DEFAULT_TIMEOUT = 15  # seconds per HTTP request


# ---------------------------------------------------------------------------
# Holehe module discovery (mirrors holehe.core.import_submodules)
# ---------------------------------------------------------------------------
def import_submodules(package_name: str) -> dict:
    """Recursively import all submodules under *package_name*."""
    package = importlib.import_module(package_name)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = f"{package.__name__}.{name}"
        results[full_name] = importlib.import_module(full_name)
        if is_pkg:
            results.update(import_submodules(full_name))
    return results


def get_check_functions(modules: dict) -> list:
    """Extract the callable check functions from discovered modules."""
    functions = []
    for module_path, module_obj in modules.items():
        parts = module_path.split(".")
        if len(parts) > 3:
            func_name = parts[-1]
            if hasattr(module_obj, func_name):
                functions.append(module_obj.__dict__[func_name])
    return functions


# ---------------------------------------------------------------------------
# Trio ↔ asyncio bridge
# ---------------------------------------------------------------------------
def _run_holehe_checks_in_trio(email: str, websites: list, proxy_url: str | None, timeout: int) -> list:
    """
    Synchronously execute all Holehe checks inside a ``trio.run()`` context.
    Returns the aggregated list of raw result dicts.

    This function is designed to be called from within an asyncio event loop
    via ``asyncio.to_thread()``, which offloads it onto a worker thread so
    the blocking ``trio.run()`` does not stall the Actor's main loop.
    """

    async def _trio_main() -> list:
        client_kwargs: dict = {"timeout": timeout}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            out: list = []

            async with trio.open_nursery() as nursery:
                for website_fn in websites:
                    nursery.start_soon(_launch_module, website_fn, email, client, out)

            return out

    return trio.run(_trio_main)


async def _launch_module(module_fn, email: str, client: httpx.AsyncClient, out: list):
    """
    Wrapper around each Holehe site-check module.
    Mirrors ``holehe.core.launch_module`` but with broader exception handling.
    """
    # Build a name→domain lookup identical to holehe.core.launch_module
    _domain_map = {
        "aboutme": "about.me", "adobe": "adobe.com", "amazon": "amazon.com",
        "anydo": "any.do", "archive": "archive.org", "atlassian": "atlassian.com",
        "bitmoji": "bitmoji.com", "blablacar": "blablacar.com",
        "bodybuilding": "bodybuilding.com", "buymeacoffee": "buymeacoffee.com",
        "codecademy": "codecademy.com", "codepen": "codepen.io",
        "deliveroo": "deliveroo.com", "discord": "discord.com",
        "docker": "docker.com", "ebay": "ebay.com", "envato": "envato.com",
        "eventbrite": "eventbrite.com", "evernote": "evernote.com",
        "firefox": "firefox.com", "flickr": "flickr.com",
        "freelancer": "freelancer.com", "garmin": "garmin.com",
        "github": "github.com", "google": "google.com", "gravatar": "gravatar.com",
        "imgur": "imgur.com", "instagram": "instagram.com", "issuu": "issuu.com",
        "komoot": "komoot.com", "lastfm": "last.fm", "lastpass": "lastpass.com",
        "myspace": "myspace.com", "nike": "nike.com", "office365": "office365.com",
        "patreon": "patreon.com", "pinterest": "pinterest.com",
        "pornhub": "pornhub.com", "protonmail": "protonmail.ch",
        "quora": "quora.com", "replit": "replit.com", "samsung": "samsung.com",
        "snapchat": "snapchat.com", "soundcloud": "soundcloud.com",
        "spotify": "spotify.com", "strava": "strava.com",
        "tumblr": "tumblr.com", "twitter": "twitter.com", "venmo": "venmo.com",
        "vivino": "vivino.com", "wordpress": "wordpress.com",
        "xing": "xing.com", "yahoo": "yahoo.com", "hubspot": "hubspot.com",
        "pipedrive": "pipedrive.com", "zoho": "zoho.com",
    }

    try:
        await module_fn(email, client, out)
    except Exception:
        name = str(module_fn).split("<function ")[1].split(" ")[0] if "<function " in str(module_fn) else "unknown"
        domain = _domain_map.get(name, "unknown")
        out.append({
            "name": name,
            "domain": domain,
            "rateLimit": True,
            "exists": False,
            "error": True,
            "emailrecovery": None,
            "phoneNumber": None,
            "others": None,
        })


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------
def format_result(email: str, raw: dict) -> dict:
    """Normalise a raw Holehe result dict into a clean output record."""
    if raw.get("rateLimit"):
        status = "rate_limited"
    elif raw.get("exists"):
        status = "found"
    else:
        status = "not_found"

    record = {
        "email": email,
        "website": raw.get("domain", "unknown"),
        "name": raw.get("name", "unknown"),
        "status": status,
    }

    # Attach any extra intelligence the module surfaced
    if raw.get("emailrecovery"):
        record["emailRecovery"] = raw["emailrecovery"]
    if raw.get("phoneNumber"):
        record["phoneNumber"] = raw["phoneNumber"]
    if raw.get("others"):
        record["others"] = raw["others"]

    return record


# ---------------------------------------------------------------------------
# Proxy resolution
# ---------------------------------------------------------------------------
def resolve_proxy_url(proxy_config: dict | None) -> str | None:
    """
    Extract a usable proxy URL from an Apify proxy configuration object.
    Falls back to the standard Apify residential proxy endpoint when no
    explicit URL is provided.
    """
    if not proxy_config:
        return None

    # If the SDK already resolved a proxyUrl, use it directly
    if proxy_config.get("proxyUrl"):
        return proxy_config["proxyUrl"]

    # Build the Apify proxy URL from group configuration
    password = proxy_config.get("password") or ""
    groups = proxy_config.get("apifyProxyGroups") or []
    if password:
        group_part = "+".join(groups) if groups else "RESIDENTIAL"
        return f"http://auto:{password}@proxy.apify.com:8000"

    return None


# ---------------------------------------------------------------------------
# Main Actor logic
# ---------------------------------------------------------------------------
async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        # ── Validate input ──────────────────────────────────────────────
        email: str = actor_input.get("email", "").strip()
        if not email or not re.fullmatch(EMAIL_FORMAT, email):
            await Actor.fail(
                status_message=f"Invalid or missing email address: '{email}'. "
                               "Please provide a valid email in the input."
            )
            return

        proxy_config = actor_input.get("proxyConfiguration")
        only_used: bool = actor_input.get("onlyUsed", True)
        proxy_url = resolve_proxy_url(proxy_config)

        Actor.log.info(f"🔍 Auditing digital footprint for: {email}")
        Actor.log.info(f"   Proxy: {'enabled' if proxy_url else 'direct (no proxy)'}")
        Actor.log.info(f"   Filter: {'only found accounts' if only_used else 'all results'}")

        # ── Discover Holehe site modules ────────────────────────────────
        try:
            modules = import_submodules("holehe.modules")
            websites = get_check_functions(modules)
        except Exception as exc:
            await Actor.fail(
                status_message=f"Failed to load Holehe modules: {exc}"
            )
            return

        Actor.log.info(f"   Loaded {len(websites)} website check modules.")

        # ── Execute checks via trio bridge ──────────────────────────────
        start_time = time.time()
        try:
            raw_results = await asyncio.to_thread(
                _run_holehe_checks_in_trio,
                email,
                websites,
                proxy_url,
                DEFAULT_TIMEOUT,
            )
        except Exception as exc:
            Actor.log.error(f"Holehe execution error: {exc}")
            await Actor.fail(status_message=f"Execution failed: {exc}")
            return

        elapsed = round(time.time() - start_time, 2)
        Actor.log.info(f"✅ Completed {len(raw_results)} checks in {elapsed}s")

        # ── Format & push results ───────────────────────────────────────
        raw_results.sort(key=lambda r: r.get("name", ""))

        pushed = 0
        for raw in raw_results:
            record = format_result(email, raw)

            if only_used and record["status"] != "found":
                continue

            await Actor.push_data(record)
            pushed += 1

        # ── Summary statistics ──────────────────────────────────────────
        found = sum(1 for r in raw_results if r.get("exists"))
        not_found = sum(1 for r in raw_results if not r.get("exists") and not r.get("rateLimit"))
        rate_limited = sum(1 for r in raw_results if r.get("rateLimit"))

        summary = (
            f"Footprint audit complete for {email} — "
            f"{found} found, {not_found} not found, {rate_limited} rate-limited "
            f"({len(raw_results)} total, {elapsed}s)"
        )
        Actor.log.info(summary)

        await Actor.set_status_message(summary)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
