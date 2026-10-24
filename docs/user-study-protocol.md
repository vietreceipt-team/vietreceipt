# VietReceipt human-review pilot protocol

**Status:** protocol draft only. No participants have been recruited and no user-study result exists. Obtain the supervisor's approval and follow the university's applicable participant/privacy process before recruitment or data collection.

## Research question

RQ3 asks whether VietReceipt-assisted review changes task time, final correctness and correction effort compared with manual processing of the same class of fictional invoice task. This is a usability/workflow pilot; it does not measure machine extraction accuracy.

## Design

Use a counterbalanced, within-participant comparison with two conditions:

- **A — Manual:** participant reads the fictional invoice and enters the required structured result into the agreed manual form/spreadsheet without seeing machine predictions.
- **B — Assisted:** the same participant reviews a separate, matched fictional invoice in VietReceipt, sees the frozen machine output and source evidence, corrects/acknowledges values, verifies and exports.

Each participant completes both conditions. Do not show the same invoice in both conditions; use different but matched invoices to limit memory and copying. Randomize/order-counterbalance A→B and B→A before the session; record assignment and task order. If recruitment does not allow balance, report the actual order and treat learning/order effects as a limitation.

Use only fictional documents created for this study. Include at least one deliberate extraction error and one unreadable/ambiguous cell in the assisted set so that source review is tested. Keep invoice difficulty, number of header fields, line count and quality reasonably matched across conditions. Freeze task packets before recruitment; do not tune the model using pilot outcomes.

## Pre-registration fields to complete before approval

| Item | Value to record before the first session |
|---|---|
| Supervisor approval and date | Pending |
| Participant eligibility and recruitment method | Pending |
| Number of participants and rationale | Pending; small pilot only |
| Task packet IDs, file hashes and matched-pair mapping | Pending |
| Required fields/rows and source-gold version | Pending |
| Manual form and VietReceipt build/commit | Pending |
| Time limit and timeout behavior | Pending; choose before sessions |
| Order assignment method and random seed | Pending |
| Primary descriptive outcomes and analysis | Paired task time, final exactness, corrections; no population-effect claim |
| Consent and data-retention plan | Pending supervisor/institution review |

Do not collect actual customer invoices, names, contact information, account credentials, screen recordings or audio. Do not record participant names in analysis files. Use anonymous participant codes such as P01 and retain only task-level timing and counts. If the approved process requires other records, store them separately under its approved access/retention rules.

## Session procedure

1. Explain both workflows, the synthetic-only data, the tasks, what is timed and what is recorded. Obtain informed agreement using the supervisor-approved process; allow withdrawal without penalty.
2. Give a short standardized orientation to the manual form and VietReceipt. Keep instructions and practice time the same for all participants; practice documents do not appear in scored task packets.
3. Assign the preregistered condition order and matched invoice packet. Start the task timer when the participant receives the source document and task instructions.
4. In A, record only the participant's final manual structured result. In B, save an immutable machine snapshot before any edits, then record every correction, status acknowledgement, row add/delete, final reviewed result, verification and export.
5. Stop timing when the participant finishes the required structured output and export, or at the preregistered time limit. Record incomplete/abandoned tasks as such; do not discard them.
6. A scorer who did not conduct the session compares both final outputs with source gold while blind to condition and participant identity. Resolve annotation disagreements before calculating correctness.
7. Ask the same short post-task questions in both conditions. Treat subjective ratings as descriptive feedback, not proof of accuracy or time savings.

## Measures and definitions

- **Task time:** elapsed time from task handoff to completed required output/export. If the task reaches the preregistered time limit or participant stops, record the limit/elapsed time and incomplete=true; never treat it as a successful fast task.
- **Final exactness:** fraction of known source-gold cells whose final status and canonical value are exact. UNKNOWN source labels are excluded and counted. Report header and line cells separately.
- **Correction count:** number of value edits plus line-row additions/deletions. Count status acknowledgements separately from value corrections. Preserve the original machine snapshot and count machine-to-human changes separately.
- **Unresolved count:** required known cells still missing, unreadable or ambiguous in the final result. Do not convert an unresolved value to zero or NOT_PRESENT.
- **Completion:** whether all required, scoreable fields/rows are present in the final structured output and an export was created.
- **Machine accuracy:** scored only from the immutable pre-edit machine snapshot against source gold. Reported separately from final correctness.

Summarize participant-paired differences, medians/ranges, completion and failures, correction counts, and per-condition final exactness. With 2–4 participants, results are descriptive and exploratory only; do not claim statistically reliable or population-level time savings. Report when the assisted workflow is slower, less accurate or not completed.

## Acceptance and stop rules

Run the pilot only when:

- supervisor approval and the applicable participant/privacy process are complete;
- TV1/TV2 have frozen source gold and task packet hashes;
- TV5/TV6 can preserve the machine snapshot separately from reviewed corrections;
- verification and export are repeatable on the designated demo build;
- the preregistration fields above are complete.

If any condition fails, postpone the study and report “not conducted.” Never substitute synthetic dry-run logs, unit tests, a demonstration, or post-review exports for participant outcomes.
