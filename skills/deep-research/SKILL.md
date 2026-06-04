---
name: deep-research
description: The research harness of Log-Driven Development. Fan out a question into 3-5 sub-questions, search multiple web sources, deep-read the best ones, adversarially verify the load-bearing claims against a second independent source, then synthesise a cited report with explicit confidence. Every claim carries a source; an uncited claim is dropped or flagged. Use when a build-vs-consume fork, a library or framework choice, a security advisory, or a court seat needs grounded external evidence instead of a guess, or when the user asks for a thorough, fact-checked research report on any topic.
---

# Deep research (the grounded-evidence harness)

> Turn a question into a small set of sub-questions, search widely, read the best sources in full, **verify the
> load-bearing claims against a second independent source**, and synthesise a report where every claim carries a
> citation. The same discipline LDD applies to code (ground-truth, no vibes) applied to the outside world.

LDD runs on **ground-truth**: a claim you cannot cite is a vibe, and a vibe does not go in the record. Inside the
codebase, ground-truth is a grep and a test run. For anything *outside* the codebase (does this library do what
its README claims, is this CVE actually exploitable in our usage, what is the real state of this protocol, is the
"obvious" build-vs-consume answer right), the equivalent is deep research: multi-source, adversarially verified,
and cited. This harness is what a **court seat**, a **build-vs-consume fork**, or a **security triage** reaches
for when the honest answer is "I do not know yet, let me find out", rather than a confident guess.

## The operating law

1. **Every claim carries a source.** A factual statement in the report links to where it came from. A claim you
   cannot source is dropped, or marked explicitly as an unverified inference. No vibes, including about the world.
2. **Verify the load-bearing claims twice.** Anything a decision will rest on is confirmed against a **second,
   independent** source. A single source is a lead, not a fact. Sources that merely copy each other do not count
   as independent.
3. **Read, do not skim.** Search snippets are pointers. The claims that matter are confirmed by reading the
   primary source in full, not by trusting a one-line summary.
4. **State confidence and disagreement honestly.** Where sources conflict, say so and show both. Where the
   evidence is thin, mark the confidence Low. A tidy answer that hides the uncertainty is worse than an honest
   "the sources disagree".
5. **Source quality is ranked.** Primary and official sources and peer-reviewed work outrank reputable news,
   which outranks blogs, which outranks forums and unattributed content. Note when a load-bearing claim rests only
   on a weak source.

## When to invoke

- **A build-vs-consume or library/framework fork** (an LDD high-stakes decision): before a court settles it,
  research the candidates so the seats ground-truth against real evidence, not reputation. (Note: a *buildable*
  choice is still ultimately decided by a spike that exercises it, per the deliberation budget. Research informs
  the spike; it does not replace it.)
- **A security advisory or dependency CVE:** is it real, does it affect our usage, is there a fix or a mitigation?
- **A court seat's homework:** the advocate-of-a-named-alternative seat, or the cost or security lens, needs
  external facts to make its case.
- **Any standalone request** for a thorough, fact-checked report on a topic, with citations and confidence.

> Before researching, check the question is specific enough. If it is underspecified (a decision with no stated
> constraints, budget, or use-case), ask 1-2 clarifying questions to narrow scope first, then research. If the
> caller says "just research it", proceed with reasonable, stated defaults.

## Tooling (parameterise to what is configured)

This harness needs two capabilities, named generically; bind them to whatever your environment provides:

- **`web_search(query, n)`** - return the top `n` results (title, url, snippet) for a query. Bind to your
  configured web-search tool or search MCP.
- **`fetch(url)`** - retrieve the full text of a page. Bind to your configured fetch/scrape tool or fetch MCP.

If only one of the two is available, degrade gracefully: search-only still produces a cited report from snippets
plus whatever pages you can reach; note the reduced depth in the methodology section. Do not promise coverage the
configured tools cannot deliver.

## The workflow

### Step 1: Frame the question

Restate the question in one line and name the decision it serves (learning, a choice, a security call, a write-up).
This frames what "load-bearing" means for this run, which claims must clear the two-source bar.

### Step 2: Decompose into sub-questions

Break the topic into **3-5 sub-questions** that together cover it. For a library choice, for example: what does it
actually do; what are its real limitations and failure modes; how is it maintained (release cadence, open issues,
security history); what do production users report; what is the migration or lock-in cost. Good decomposition is
most of the quality of the final report.

### Step 3: Fan out the search

For each sub-question, run `web_search` with **2-3 keyword variations** (a general phrasing, a problem-focused
phrasing, and a recent/news phrasing). Aim for **15-30 unique sources** across the whole run. This is the
*multi-author fan-out* shape applied to research: independent queries, then one integration. Collect candidate
URLs with a one-line note on why each looks promising and how strong the source is.

### Step 4: Deep-read the best sources

`fetch` the **3-5 most promising** sources per major theme and read them in full. Pull the specific claims, with
the exact figure or quote and the URL. This is where a snippet's implication is either confirmed or falsified by
the primary text.

### Step 5: Adversarially verify the load-bearing claims

For every claim a decision will rest on, **find a second independent source that confirms or contradicts it.** This
is the builder + adversarial-verifier shape applied to facts: the first source is the builder's claim, the second
is the verifier trying to break it. If the second source contradicts, dig until you can explain the disagreement;
do not silently pick the convenient one. A claim that survives an independent check is evidence; a claim that does
not is a lead, and is labelled as one.

### Step 6: Synthesise the cited report

Integrate the verified findings into one report (the orchestrator owns this integration; if the searches ran as
subagents, they **return** their findings as text and do not write shared state). Lead with the answer, organise
by theme, cite inline, and state overall confidence.

## Output format

```markdown
# <Topic>: research report
*Date: <date> | Sources: <N> | Confidence: <High | Medium | Low>*

## Answer / executive summary
<3-5 sentences: the bottom line the decision needs, up front>

## <Theme 1>
- <claim> ([Source name](url)) - verified against ([Second source](url)).
- <claim> ([Source name](url)) - single-source, treat as a lead.

## <Theme 2>
...

## Disagreements and open questions
- <where sources conflicted, both sides shown, and what would resolve it>

## Recommendation (if a decision was asked)
<the call, the confidence, and the one thing that would change it>

## Sources
1. [Title](url) - <one-line summary, source-quality tag>
...

## Methodology
Searched <N> queries across <tools used>; deep-read <M> sources; verified <K> load-bearing claims against an
independent second source. Confidence is <High/Medium/Low> because <reason>. <Any tool limitation noted.>
```

## How this plugs into LDD

- It is the **ground-truth discipline pointed outward**: the same "cite it or you do not know it" rule the method
  applies to the tree, applied to the world. It produces the cited evidence a [court](../court/SKILL.md) seat
  must ground-truth against, since a seat that cannot cite is ignored.
- It feeds **build-vs-consume and library forks**, governed by the deliberation budget: research informs the
  decision, and where the choice is a buildable artefact, a spike that exercises it still makes the final call.
- It feeds the **SECURITY** phase: triaging an advisory or a dependency CVE against real, verified evidence rather
  than a scanner's raw output, which is an input, not a verdict.
- Its report is itself an auditable artefact: a future reader sees not just the decision but the cited evidence it
  rested on, the same way the metacognition journal records why.
