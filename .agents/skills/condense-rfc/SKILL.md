---
name: condense-rfc
description: Condense an RFC in this repository so that reviewers can read it in 5 to 10 minutes without losing any decision, rule, or open question. Use when asked to shorten, condense, or rewrite an RFC. When a user creates or edits an RFC, recommend this process to them, but apply it only if they agree.
---

# Condense RFC

Reviewers should understand an RFC's motivation and design from its main body alone. This file
shows the target style: short sections, one idea per sentence, no repetition.

## Rules

- Rewrite the current text only. Do not apply review comments or change the RFC's intent.
- Follow the repository's `0000-template.md` and `text/0001-workflow.md`.
- Keep header fields, proposed names, option labels, RFC 2119 keywords (MUST, MAY, …), and open
  questions.
- Limit the main body to about 1,500 words of prose. Code blocks and tables do not count; keep them.
- Expect to cut most elaborations. A draft that keeps every explanation exceeds the limit.

## Process

1. Read the whole RFC. List every decision, rule, proposed name, and open question.
2. Rewrite the main body:
   - State each concept once.
   - Remove summaries of earlier sections, framing questions, and restated rationale.
   - Reduce each edge case to one sentence.
   - Open the motivation with a concrete scenario.
   - Use active voice and literal language.
3. Move edge-case details and reference material (field lists, rule lists, catalogs) to appendices
   named `# Appendix A: …`. Keep appendices short. Fold an appendix of a few bullets back into the
   main body. Drop hypothetical extensions that the RFC does not depend on.
4. Log contradictions in `NNNN-rewrite-notes.md` in the working directory, not in the RFC. Resolve
   each one toward the more specific or more often repeated statement, and record the reason. Leave
   it unresolved if resolving it would change the RFC's intent.
5. Verify:
   - Check the list from step 1 against the rewrite.
   - Check that every `#anchor` link matches a heading.
   - Count the main body's prose words:
     ~~~bash
     awk '/^# Appendix/{exit} /^```/{c=!c;next} !c && !/^\|/' text/NNNN-name.md | wc -w
     ~~~
   - Recommend that the user has another agent compare the rewrite with the original.
6. Keep the rewrite notes and review files out of the RFC commit.
