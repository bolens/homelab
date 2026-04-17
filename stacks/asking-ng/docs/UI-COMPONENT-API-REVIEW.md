# UI Component API Review

Scope: `stacks/asking-ng/client`

## 1) Polymorphic button/link strategy

Decision: keep the current split (`Button` component + styled links) for now.

Rationale:

- The app already uses router links (`Link`) and anchor links in many places with route-specific props.
- A single polymorphic API (`as='a' | Link`) would add type complexity and likely require generics or runtime branching.
- Existing `ui-button` class coverage already supports visual parity across button and link affordances.

Follow-up direction:

- Revisit only if repeated accessibility or prop-forwarding bugs appear.
- If revisited, prefer a dedicated `ButtonLink` wrapper first, not a full polymorphic primitive.

## 2) Card sub-structure (`Card.Header`, `Card.Body`, `Card.Footer`)

Decision: defer introducing sub-components.

Rationale:

- Current usage patterns are already readable with existing primitives (`Card`, `SectionPanel`, `ActionRow`, `FormSection`).
- Most remaining layout variance is page-specific; enforcing a rigid Card anatomy now would create churn with low gain.
- Incremental page-shell standardization delivered consistency without needing nested Card APIs.

Follow-up direction:

- Reconsider if 3+ repeated card internals emerge with identical heading/body/footer patterns.

## 3) Dialog action/footer primitives

Decision: do not add global dialog action/footer primitives yet.

Rationale:

- Current dialog implementations are limited and still vary by context (admin modals vs. inline disclosure flows).
- Existing `ui-dialog` base styles plus local action rows are sufficient for current scope.
- Introducing shared dialog action primitives now would likely be speculative.

Follow-up direction:

- Add `DialogActions`/`DialogFooter` only after another modal-heavy feature pass creates stable shared patterns.
