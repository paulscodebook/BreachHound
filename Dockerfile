# ──────────────────────────────────────────────────────────────
# Footprint — Digital Identity Auditor
# Production Dockerfile for Apify Actor deployment
# ──────────────────────────────────────────────────────────────

FROM apify/actor-python:3.11

# Copy the entire repository (holehe codebase + actor source)
COPY . ./

# Install holehe from the local source (includes httpx, trio, etc.)
# and the Apify SDK + any additional runtime dependencies
RUN pip install --no-cache-dir \
    ./  \
    apify \
    && echo "All dependencies installed successfully."

# Default command — run the Actor entrypoint
CMD ["python", "-m", "src.main"]
