# R5 Product Decision

Owner requirement update is interpreted as:

> Pending-review knowledge must be visible enough to review and manage; it must not be treated as operationally verified merely because it is visible.

Therefore R5 introduces an authenticated read-only review plane while preserving the existing fail-closed operational plane and VERIFIED-only AI plane.

This replaces the previous product behavior where `UNVERIFIED` caused the review candidate body itself to disappear from the only local UI.