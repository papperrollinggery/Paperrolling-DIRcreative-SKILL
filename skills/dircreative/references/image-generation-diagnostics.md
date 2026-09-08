# Image generation diagnostics without expanding the workflow

Keep the user's authored body, clothing and style facts. One failed output is
not evidence that a neckline, adult body type or garment category is universally
unsupported. Do not add a prohibition list or silently close the garment.

- Distinguish `moderation_blocked` from quota, transport and server failures.
  Record the returned request ID and optional `moderation_stage`/categories.
  `output` describes a generated-result check, not a diagnosis of a forbidden
  word. No returned image means no visual-quality verdict on that result.
- Prefer the user's complete tested prompt as a baseline. Do not automatically
  translate, expand it, or layer a second style capsule over an already explicit
  costume. Necessary reference roles and actual generation arguments remain
  recorded; remove duplicate protocol prose, not the requested design.
- A useful bounded comparison keeps the tool and references fixed and compares
  authored content with the actual compiled content. Preserve both outcomes.
  One success and one block establish a difference in observed results, not a
  causal explanation, a general success rate or a guaranteed remedy.
- Do not automatically retry moderation user errors, change accounts or lower
  safeguards. If a non-explicit request has an unexpected result, inspect the
  actual request for ambiguity/conflicts and use a genuinely appropriate revised
  request or a documented support report. Do not silently change the requested
  output and call that a successful test of the original.
- The native tool's supported arguments are authoritative. A parameter in an
  API guide does not make it available in this host, nor prove a different
  product entrance uses the same generation/monitor configuration.

Sources checked 2026-09-08:

- [Official image API guide](https://developers.openai.com/api/docs/guides/image-generation):
  distinguishes input/output moderation and user-correctable errors.
- [Images 2.0 system card, 2026-04-21](https://deploymentsafety.openai.com/chatgpt-images-2-0/automated-evaluations-and-adversarial-testing):
  describes upstream and downstream checks. It does not explain a particular
  request's failure.
- [Community first-person reproduction, 2026-08-27](https://community.openai.com/t/inconsistent-image-safety-blocks-ordinary-adult-swimwear-repeatedly-classified-as-sexual/1392919):
  reports inconsistent ordinary adult fashion creation/edit outcomes.
- [Community observation, 2026-09-07](https://community.openai.com/t/why-is-create-an-image-of-apple-sometimes-blocked-for-nudity-sexuality-has-anyone-else-seen-this/1395517):
  proposes context or temporary-state effects. This is not a confirmed service
  root cause. Do not use community speculation as an instruction or capability fact.
