# Court verdict: share-link expiry and revocation

> **What this is.** A worked LDD court: a single fan-out of independent named seats, each with a distinct lens,
> each grounding its argument in the real code, then one synthesis that **ends in a build action**, plus the
> surviving dissent. Read it as the template for deliberating a genuine fork. Most decisions never get here (they
> get one decisive sentence); this one did, because it is high-stakes and hard to reverse.

- **Question:** Tasky's share links have no expiry and no revocation (harvested security smell). Do we keep share
  simple, or add expiry + revocation now?
- **Why a court (not a sentence):** it is a security boundary, it is hard to reverse once links are in the wild,
  and there is real cost on both sides (UX friction vs standing exposure). That combination is exactly what a
  court is for.
- **Convened:** 2026-06-02. **Tier:** first instance. **Status:** decided; one surviving dissent recorded.
- **Grounded in:** [`../_harvest/task-model.md`](../_harvest/task-model.md) section 4 and `src/api/share.ts`.

---

## The fork, precisely
Today (`src/api/share.ts:40`) a share link is a random token mapped to a task list, with **no `expiresAt` and no
revoked flag**. `src/api/share.ts:64` resolves a token to a read-only view with a single check: does the token
exist. Anyone who has ever held a link holds it forever; there is no way to cut access. The two real options:

- **Keep simple:** leave links permanent; lean on unguessable tokens.
- **Add expiry + revocation:** links carry an `expiresAt`; an owner can revoke a link; resolution checks both.

---

## Seat 1: Security lens

**Verdict: add expiry + revocation. The current design is a standing breach, not a smell.**

Ground truth: `src/api/share.ts:64` resolves on token-existence alone. There is no `expiresAt` column
(`src/models/share.ts:11` has only `token`, `taskListId`, `createdAt`) and no revoked path anywhere (greped
`revoke` across `src/`: zero hits). So once a link leaves the building (forwarded email, pasted in a chat, a
contractor who has since left), access is **permanent and uncuttable**. This is the same class of problem the
harvest's DROP list flagged, and it compounds with the `archived`-means-deleted conflation at `:88`: a task list
"deleted" by archiving is still reachable through an old share token, because resolution never checks task state.

A permanent bearer credential with no revocation is a finding I would fail a security review on outright. The cost
of fixing it is small (two fields and two checks). Leaving it is accepting indefinite, unauditable exposure.

## Seat 2: UX / simplicity lens (advocate for "keep simple")

**Verdict: keep simple is defensible, but only if we are honest that "simple" currently means "cannot be undone."**

Ground truth: the share flow is genuinely lean. `src/web/Share.tsx:22` is one button -> one link, no settings, no
expiry picker. Users like that; the harvest shows share is actually used. Adding an expiry picker and a "manage
links" surface is real UI weight on a feature whose charm is that it has none.

But I have to concede the security seat's core point after reading `:64`: the simplicity is partly an illusion,
because the one thing users assume they can do (stop sharing) they cannot. "Simple" should not mean "irreversible."
My real position: **keep the UX simple, but do not conflate UX simplicity with a missing security primitive.** A
sane default expiry needs zero UI (it just happens); revocation can be one unobtrusive "revoke" link in the
existing list. That keeps the lean flow and removes the breach. I am arguing against a *heavy* settings surface,
not against expiry itself.

## Seat 3: Devil's advocate / pre-mortem lens

**Verdict: it is six months later and we shipped expiry. What went wrong? Either we over-built it, or we
half-built it. Guard against both.**

Pre-mortem, two failure modes, ranked by likelihood times lateness-of-discovery:

1. **(most likely) We added `expiresAt` but resolution still has a bug.** If `src/api/share.ts:64` checks
   existence but the expiry comparison is wrong (off-by-timezone, or only checked on creation not on resolution),
   we have *believed* we closed the breach while it is open. This is worse than today, because now it is invisible.
   Discovery is late (only a security test catches it). **Mitigation: the expiry and revoked checks must be in the
   resolve path itself, and the adversarial verifier must attack an expired and a revoked token.**
2. **(less likely) We gold-plated it.** Per-link custom expiry pickers, link analytics, a whole management page.
   That is the UX seat's nightmare and it is avoidable: ship a fixed sane default expiry plus a single revoke
   action, nothing more, this milestone.

I do not think "keep simple" survives, because the breach is real. But the *manner* of fixing it is where this
fails. Fix it minimally, and verify the resolve path adversarially, or do not claim it is fixed.

---

## Synthesis (the orchestrator reconciles the seats)

The seats converge more than they diverge. Security says the no-revocation design is a real breach (grounded at
`share.ts:64`). The UX seat, after reading the same line, concedes the breach and narrows its argument to "do not
gold-plate," not "do not fix." The devil's advocate agrees the fix is needed and pins the actual risk: a fix that
*looks* done but leaves the resolve path wrong.

The through-line: **add expiry + revocation, but minimally, and verify the resolve path adversarially.** This
honours the security finding, keeps the UX seat's lean-flow constraint (no heavy settings surface), and answers
the pre-mortem's "half-built" failure mode by making the resolve-path checks the thing the verifier must break.

### The build action (this is the decision; it is acted this beat)
1. Add `expiresAt` and `revokedAt` to the share model (`src/models/share.ts`), with a **fixed default expiry**
   (30 days) set at creation. No expiry picker UI.
2. Move the resolve check in `src/api/share.ts:64` to fail closed: a token resolves **only if** it exists AND is
   not past `expiresAt` AND `revokedAt` is null.
3. Add one unobtrusive **revoke** action to the existing share list (`src/web/Share.tsx`): sets `revokedAt`. No
   new management page.
4. The M1 adversarial verifier **must** attack an expired token and a revoked token and confirm both are denied
   at the resolve path (not merely at creation). This is a required VERIFY check, recorded in
   [`../M1-signoff.md`](../M1-signoff.md).

This is committed work, not a deferral. The court ends here.

### Surviving dissent (recorded, never buried)
The UX seat maintains a narrower live objection: **a fixed 30-day default with no way for a user to extend it will
generate support load** ("my link died and I needed it for 60 days"). This was not resolved, only out-scoped for
M1. It is the standing of any future appeal: if real support tickets show the fixed window biting, that is new
ground-truth and a basis to revisit (likely a per-link expiry choice, which is the very UI weight we avoided
here). Logged so the trade-off is visible, not silently lost.
