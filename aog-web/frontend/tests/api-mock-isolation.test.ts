/**
 * Targeted frontend CI entry.
 *
 * The existing workflow invokes this exact file, so it must register both the
 * production mock-isolation suite and the current P0-1 regression suite.
 */
import "./api-mock-isolation.cases";
import "./p0-experience-content-integrity.test";
