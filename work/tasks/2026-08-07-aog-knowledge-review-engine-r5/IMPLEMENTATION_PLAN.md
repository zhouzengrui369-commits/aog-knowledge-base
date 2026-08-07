# R5 Implementation Plan

## Backend

Add an authenticated read-only review router:

- `GET /api/review/cities`
- `GET /api/review/city/{code}`

The review router reads decoded SQLite records before `apply_city_release_policy` blanks non-VERIFIED fields. Existing SQLite contact decoding remains in force so non-public phone/email/role/scope stay redacted.

The router exposes review metadata (`review_visible`, `operational_eligible`, `ai_eligible`, stable `review_id`) but does not expose any mutation endpoint.

## Frontend

Add:

- `/review` pending knowledge queue;
- `/review/city/[code]` read-only review detail;
- navigation entry `知识审核`;
- CTA from a non-VERIFIED operational city page to the review detail.

Review detail must clearly say:

- candidate content is visible for review;
- it is not verified and cannot be used for actual AOG handling;
- AI will not use it as VERIFIED context;
- status changes are not performed in R5.

## Security

- review API requires a valid existing AOG session cookie or bearer token;
- normal city API remains unchanged and fail closed;
- AI remains strict VERIFIED-only;
- no new source write or review-status mutation endpoint;
- no cloud write.

## Tests

Backend tests:

- unauthenticated review list/detail rejected;
- authenticated pending detail includes candidate content;
- non-public contacts remain REDACTED;
- review metadata says `operational_eligible=false`, `ai_eligible=false`;
- public operational endpoint still hides the same pending content.

Frontend contracts:

- review route exists;
- pending detail renders read-only warning and candidate content;
- no tel/mailto actions in review-mode contacts;
- normal city warning links to review surface.

Existing R4 strict-AI tests remain mandatory.