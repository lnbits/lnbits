# Feature Spec: [FEAT-XXX] - Short Descriptive Title

**Milestone:** [e.g. MVP Core / Performance & Polish / Extension Framework]
**Priority:** Must-have / Should-have / Nice-to-have
**Spec Owner:** [Your Name / AI Agent Name]
**Status:** Draft → Under Review → Approved → Implemented → Verified

## 1. Purpose & User Story

As a [user type], I want [goal] so that [benefit].

_(One clear sentence. Keep it concise.)_

## 2. Functional Requirements

- [ ] REQ-1: [Clear, testable description]
- [ ] REQ-2: ...
- [ ] REQ-3: ...

_(List what the feature must do. Make each item verifiable.)_

## 3. Non-Functional Requirements

- **Performance:** [e.g. Latency < 800ms at p95, max 5k tokens, etc.]
- **Security / Safety:** [e.g. Input validation, no raw errors to user, etc.]
- **Compatibility:** [e.g. Works with all existing wallet backends, no breaking changes for extensions]
- **UI/UX:** [e.g. Follows existing Quasar/Vue patterns in wallet.js]
- **Other:** [cost, scalability, accessibility, etc.]

## 4. Technical Approach (Optional – recommended for complex features)

- Proposed solution: [e.g. Extend existing CRUD in lnbits/core/, new extension, middleware change, etc.]
- Key files to modify: [list expected files]
- New dependencies: [none / specific package + version]
- Migration / Database changes: [yes/no + description]

## 5. Success Criteria & Verification

**Must pass all of these to be accepted:**

- [ ] All functional requirements (REQ-\*) implemented and tested
- [ ] Non-functional requirements met (performance, security, etc.)
- [ ] Relevant tests pass: `make test-unit`, `make test-api`, `make test-regtest` (as applicable)
- [ ] `make check` passes (ruff, mypy, pyright, prettier, checkbundle)
- [ ] Constitution compliance: All changes respect CONSTITUTION.md
- [ ] Backward compatibility: No breakage for existing extensions or wallet backends
- [ ] Documentation updated (if applicable: README, OpenAPI, inline comments)

**Additional Tests / Edge Cases:**

- [ ] Test invalid inputs / error paths
- [ ] Test with FakeWallet and at least one real backend
- [ ] Test with multiple extensions installed

## 6. Safety & Risk Assessment

- Potential risks: [e.g. Payment flow impact, key exposure, extension conflicts]
- Mitigation: [how addressed]
- Security review needed: [yes/no]

## 7. Implementation Notes (for AI / Developer)

- Style to match: Existing code patterns in `lnbits/core/` and `wallet.js`
- Surgical changes only (per AGENTS.md)
- Any known gotchas or dependencies on other features:

## 8. Acceptance Checklist (Sign-off)

- [ ] Spec reviewed and approved by project owner
- [ ] Implementation completed
- [ ] Verification steps passed
- [ ] PR created with link to this spec
- [ ] Constitution & AGENTS.md compliance confirmed

---

**Created:** [Date]
**Last Updated:** [Date]
**Approved By:** [Name / "Approved"]
