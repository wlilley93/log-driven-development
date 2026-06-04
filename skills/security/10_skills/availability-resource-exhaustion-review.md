# Skill: availability / resource-exhaustion review

**Surface:** any network service  -  especially thread/connection-per-request
servers, file-upload paths, long-lived streams (SSE/WS), and anything behind a
CDN/tunnel. DoS-via-resource-exhaustion is in scope for security review even
though pure volumetric DDoS is an edge/infra concern.

## Checks
1. **Concurrency model.** Thread/process-per-connection (e.g. stdlib
   `ThreadingHTTPServer`) caps out under load and is slowloris-prone. Long-lived
   **SSE/WebSocket** streams that hold a thread for their lifetime compound it.
   → request read timeouts (`read_header`/`read_body`), an idle timeout set ABOVE
   the stream heartbeat (so it can't kill active streams), and a per-IP
   connection / concurrent-stream cap.
2. **Unbounded body reads.** Bodies read fully into memory (`read(content_length)`)
   let N concurrent large requests = N×size RAM → OOM. → a tight per-content-type
   cap (JSON ≪ multipart), reject BEFORE reading; stream uploads to disk / object
   storage (presigned PUTs) rather than through the app.
3. **Rate limiting that actually limits.** A single global counter is both a
   shared-budget DoS (one caller starves everyone) AND fails per-caller. → key on
   the acting principal (user, else client IP). (See the distributed-bypass note
   in `auth-session-review`: per-IP alone is defeated by IP rotation → needs
   per-target + challenge + edge.)
4. **Edge DDoS posture.** Is there a public origin IP an attacker can flood, or is
   ingress outbound-only (tunnel) + host-firewalled (no direct-to-origin)? Are L7
   rate-limit rules + bot management + a human-challenge configured at the edge?
5. **Unbounded growth.** Append-only logs/ledgers/queues with no rotation or size
   cap; `readlines()` of a whole file in a hot path. → size-based rotation +
   bounded tail reads.
6. **Amplification / quotas.** Unbounded fan-out (one request → many backend
   calls), missing per-tenant resource caps (CPU/mem/PIDs), recursive/zip-bomb
   parsing without depth/size guards.

## Verification
Load/spike test the hot endpoints + the stream endpoints to find the concurrency
ceiling; confirm read timeouts + body caps reject before resource commit; confirm
the rate limiter is per-principal; confirm logs rotate. Record any silent caps.

## Note
Some of this is availability not confidentiality/integrity  -  but a DoS that takes
the auth/control plane down IS a security incident. Pair with the edge config
(rate-limit rules, challenge) which is operator, not code.
