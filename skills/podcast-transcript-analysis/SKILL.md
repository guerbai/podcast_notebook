---
name: podcast-transcript-analysis
description: Use when summarizing a long podcast episode from a full transcript, especially when the transcript contains ASR errors and the summary must be grounded in the whole episode and cross-checked with official episode metadata such as title, show notes, or timeline.
---

# Podcast Transcript Analysis

## Overview

Use this skill for long-form podcast analysis when a full transcript exists but contains transcription noise, speaker confusion, or missing punctuation.

Core principle: **full transcript first, official metadata second, inference last.**

## When to Use

Use this skill when:

- the user wants a summary based on the **entire episode**, not just the show notes
- the transcript is long and likely contains ASR mistakes
- the podcast page has a title, intro, chapter list, or timeline that can help correct interpretation
- the user wants structured extraction such as `projects mentioned`, `core arguments`, `methods`, `takeaways`, or `who said what`

Do not use this skill when:

- the user only wants a summary of text they already pasted and no external validation is needed
- there is no transcript and no way to access the episode contents

## Workflow

### 1. Treat the transcript as the primary source

- Read enough of the full transcript to cover the whole episode.
- For very long transcripts, scan the whole file and then re-read the densest sections around the target topic.
- Do not summarize from the opening segment alone.

### 2. Use official episode metadata to correct interpretation

Cross-check with official or platform metadata when available:

- episode title
- episode intro/description
- chapter markers or timeline
- guest names
- platform show notes

Use metadata to:

- resolve obvious ASR mistakes in product names, people, companies, and project names
- verify which topics are central versus incidental
- avoid missing a major thread that the transcript rendered badly

Do **not** let the metadata replace the transcript. It is only for correction and framing.

### 3. Build an extraction table before writing the final summary

Before summarizing, explicitly list:

- major topics discussed
- concrete projects/examples mentioned
- repeated arguments or claims
- specific tools/products named
- advice or predictions
- unclear items that may be ASR artifacts

If the user asks for something narrow, such as `Codex projects`, extract a candidate list first and check it against the full transcript before drafting.

### 4. Separate facts from interpretation

Always distinguish between:

- **explicitly stated in the episode**
- **reasonable inference from multiple passages**

Do not present your own synthesis as if it were a direct claim from the speakers.

### 5. Handle ASR noise systematically

When the transcript is noisy:

- use repeated mentions to recover the intended term
- use surrounding context to normalize names
- prefer the official title or show note spelling when available
- mark uncertain interpretations instead of forcing confidence

Common failure mode:

- extracting a plausible project or conclusion from one noisy paragraph and missing another clearer mention later in the transcript

### 6. Write the answer in two passes

Pass 1:

- write a high-confidence inventory of the requested items

Pass 2:

- summarize the logic, arguments, or methodology behind each item

This prevents “good prose, incomplete coverage” errors.

## Output Patterns

### A. Episode summary

Use:

- one paragraph for the main thesis
- a short list of the core threads
- a short list of actionable takeaways if relevant

### B. Projects or examples mentioned

For each project/example, include:

- what it is
- what problem it tries to solve
- how they approached it
- what broader method it illustrates

### C. Methods / methodology

When the user asks for methodology, focus on recurring patterns, for example:

- workflow decomposition
- role/agent splitting
- standardization and repeatability
- memory/logging/recording process
- choosing problems that match current model strengths

## Anti-Mistake Checklist

Before sending the answer, verify:

- Did I cover the **whole transcript**, not just the beginning?
- Did I check the episode title and show notes/timeline?
- Did I make a project list before summarizing?
- Did I separate explicit claims from my inferences?
- Did I avoid dropping a project/example that was mentioned later in the episode?

## Good Default Phrasing

Use wording like:

- “The episode explicitly mentions…”
- “A recurring method they use is…”
- “My reading, based on multiple passages, is…”
- “This appears to refer to X, likely corrected from ASR noise using the episode title/show notes.”
