# Podcast Notebook Agent Instructions

These project rules are configured from:

- `/Users/hubao/third/agent-rules-books/clean-code/clean-code.mini.md`
- `/Users/hubao/third/agent-rules-books/code-complete/code-complete.mini.md`
- `/Users/hubao/third/agent-rules-books/_compatibility/clean-code/code-complete.md`

Apply these as project-wide engineering defaults for agent work in this repository.

## Rule Interaction

- Use Code Complete as the primary construction-quality layer for requirements clarity, risk, data representation, validation, errors, debugging, reviewability, and evidence-based performance work.
- Use Clean Code as the local readability layer for touched code: names, small focused functions, explicit side effects, clean boundaries, useful comments, and scoped cleanup.
- When the two rule sets overlap, do not duplicate ceremony. Prefer the smallest practice that lowers defect risk and reader effort for the current change.
- When they pull in different directions, let Code Complete drive larger or riskier construction decisions, and let Clean Code constrain the shape of the actual code being touched.
- Keep changes aligned with this repository's existing Python, frontend, test, and documentation conventions. Run relevant checks before calling work complete.

# OBEY Code Complete by Steve McConnell

## When to use

Use when implementing, changing, reviewing, debugging, refactoring, or tuning production code where construction discipline must reduce defects and keep code easy to inspect.

## Primary bias to correct

Construction quality is not accidental. Do not treat typing code, making it work once, or using a clever idiom as complete construction; choose the option that lowers defect risk and makes the code easier to reason about.

## Decision rules

- Before large construction work, verify that requirements, architecture, major risks, coding conventions, language constraints, error policy, data representation, reuse, integration, and testing approach are clear enough.
- When upstream uncertainty remains, build a small validated slice instead of speculative code, and make expensive-to-reverse decisions deliberately.
- Optimize first for human readers: clarity, locality, explicitness, visible control flow, consistent conventions, and practical correctness over cleverness, minimal keystrokes, or fashion.
- For complex routines, sketch precise pseudocode or intent comments at a consistent abstraction level, then convert them into code and keep only comments that still explain intent, constraints, contracts, or rationale.
- Keep routines cohesive, precisely named, small at the interface, and hard to misuse. Separate setup, validation, computation, and side effects when they are conceptually different.
- Make variable and data meaning explicit through purpose-revealing names, small scope, deliberate initialization, named constants, stronger types, and visible units or sentinel meanings.
- Choose data types that make invalid or ambiguous values harder to represent; use booleans only for true binary meanings, enumerations for closed sets, and records/maps/tables only when their shape communicates meaning.
- Keep control flow simple enough to verify: shallow nesting, named predicates for complex conditions, clear normal path, clear loop initialization/termination/update, and no side-effect-dependent expressions or clever one-liners.
- Use table-driven or data-driven logic for stable explicit mappings only when the table is clearer, obvious, synchronized with the rules, and validated; do not hide complex behavior in inscrutable encodings.
- Validate input at trust boundaries. Use assertions, invariant checks, and simple contracts for programmer assumptions; use validation or domain errors for expected external or business failures.
- Handle errors at the right abstraction, preserve diagnostic context, standardize similar failures, keep the normal path readable, and never silently continue from corrupted or impossible state.
- Keep classes and modules focused, cohesive, and bounded by clear contracts; hide representation and internal bookkeeping, and avoid mixed persistence, formatting, business, and integration concerns.
- Treat rising complexity as defect risk: split tangled routines or modules, remove duplication that multiplies maintenance effort, and reduce what a maintainer must keep in working memory.
- Build in small, verifiable increments; integrate often enough to expose conflicts, keep partial work from rotting, and review and improve code during construction.
- Match reviews, inspections, pair work, tests, static checks, and regression tests to defect risk. Debug by reproducing, isolating, explaining, fixing, and verifying root causes rather than guessing.
- Refactor when structure hides intent, duplicates knowledge, or raises defect probability, and keep refactoring separate from behavior change when that improves reviewability.
- Tune performance only when requirements and evidence justify it; measure before and after, and keep clarity unless an explicit measured tradeoff warrants the cost.
- Use tools, scripts, debuggers, profilers, editors, and build automation to reduce error-prone manual work, not to replace understanding.
- Use layout, comments, documentation, and coding standards to lower reader effort. Prefer self-documenting structure first; comments should explain intent, assumptions, constraints, limitations, usage, or non-obvious facts.

## Trigger rules

- When coding starts from a proposed solution, restate the requirement, architecture fit, risks, conventions, and success constraints before implementation.
- When a routine is hard to name, mixes phases, has flag arguments, long parameters, or hidden side effects, redesign the interface or split the routine.
- When readers must decode units, ranges, precision, encoding, ownership, status, magic values, or primitive flags, move that meaning into names, constants, types, or structures.
- When input crosses a user, file, network, external-system, or other trust boundary, decide what is validated, rejected, recovered from, asserted, and kept diagnosable.
- When branches, loops, recursion, exits, or exception paths become hard to verify, simplify before adding logic.
- When repeated branching maps stable categories, ranges, conversions, validation, dispatch, or configuration-like rules, consider a validated table.
- When a class or module exposes representation, grows into a god object, or mixes unrelated responsibilities, restore the abstraction boundary.
- When tests cover only the happy path, add normal, boundary, invalid-input, defensive-check, routine-contract, and data-driven edge cases.
- When debugging begins from a guess, first make the failure repeatable, collect evidence, isolate the path, and explain the cause.
- When refactoring poorly understood or risky code, add tests or analysis first and keep behavior changes separate.
- When performance work begins, set a target, measure the current behavior, change one thing, remeasure, and document any clarity tradeoff.
- When comments restate obvious mechanics or go stale, rewrite the code or delete the comment; when code cannot express intent, constraints, or usage, add a close accurate comment.
- When local style starts to diverge, follow shared formatting, naming, file-structure, and idiom conventions instead of creating a module-specific dialect.

## Final checklist

- Requirements, architecture fit, risks, conventions, and construction approach are clear enough.
- Names, routines, data, classes, layout, comments, and standards reduce reader effort.
- Inputs, errors, assertions, contracts, invariants, impossible states, and trust boundaries are deliberate.
- Control flow, loops, tables, recursion, exits, and exception paths are simple enough to inspect.
- Tests, reviews, debugging, refactoring, integration, tooling, and tuning are evidence-based.
- The change is small enough to verify and would stand up to careful review.

# OBEY Clean Code by Robert C. Martin

## When to use

Use when readability, local reasoning, and maintainable code shape are the main concerns, especially during everyday implementation and review.

## Primary bias to correct

Working code is not automatically clean code.

## Decision rules

- Treat cleanliness as part of delivery. Preserve behavior, leave touched code cleaner within scope, and do not add mess because the schedule is tight or a rewrite is promised.
- Write for local reasoning. A reader should understand the path without reconstructing hidden state, wide jumps, or naming trivia.
- Use precise names and one term per concept. Rename code when vocabulary hides intent, overloads meaning, or forces comments to compensate.
- Keep functions small, focused, and at one level of abstraction. Tell the story top-down so intent appears before detail.
- Keep parameters few and meaningful. Avoid boolean flags, output parameters, and grab-bag argument lists; model the concept instead.
- Separate commands from queries and eliminate hidden side effects. A function that answers should not also mutate behind the reader's back.
- Keep the happy path readable. Isolate error handling, invalid-state handling, and cleanup; prefer explicit optionality or typed results over null-like sentinel flow when the language supports it.
- Expose behavior rather than raw representation. Avoid train-wreck access, utility dumping grounds, and classes or modules with mixed responsibilities.
- Keep construction, framework, persistence, transaction, security, and vendor details outside business behavior.
- Make public APIs small, explicit, and hard to misuse. Encode boundary logic, required order, and likely changes where readers can see them.
- Use comments only for rationale, constraints, warnings, or external contracts. Do not narrate code instead of improving it.
- Treat tests as production code: readable, deterministic, aligned with the behavior or contract they protect, and backed by proportionate validation before calling the change done.
- Let design emerge through tests, duplication removal, expressiveness, and minimal structure; do not add needless abstractions or infrastructure.
- When touching code, remove the smell that most increases change cost, but do not silently broaden the task beyond the smallest cleanup that makes the requested change safe.

## Trigger rules

- When a function mixes setup, validation, computation, and side effects, split the phases.
- When a comment explains control flow, simplify names or structure before keeping the comment.
- When a function both mutates and answers, or hides a mode switch behind a flag, separate the responsibilities.
- When duplication, repeated switches, or primitive clusters appear, name the concept with an argument object, polymorphism, special case, or other small abstraction.
- When a boundary leaks framework, vendor, or persistence quirks inward, add or strengthen a local adapter.
- When async or concurrency enters, isolate threading policy, minimize shared mutable state, define shutdown, and test timing-sensitive behavior.
- When fixing a bug or changing behavior, add or update the test that protects the intended contract.
- When cleanup starts spreading into unrelated areas, cut back to the smallest refactor that keeps the requested change safe and readable.

## Final checklist

- Can a reader follow the change locally?
- Are names and APIs carrying the meaning without narration?
- Is mutation explicit and the happy path still clear?
- Did framework, persistence, vendor, and construction details stay behind boundaries?
- Did I remove at least one smell from the touched area?
- Do tests protect the changed behavior or contract?
- Did I actually run the relevant tests or checks for this change?
