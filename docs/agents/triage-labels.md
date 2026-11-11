# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Lifecycle state

The five roles above describe the *triage queue*: an issue in one of those
states is waiting on someone. A ticket leaves the queue when its work is done,
and that state is recorded separately:

| Status string | Meaning                                                       |
| ------------- | ------------------------------------------------------------- |
| `closed`      | Every acceptance criterion is met and verified                |

`closed` is not a triage role, so it does not belong in the table above. A
ticket is only moved to `closed` when each of its acceptance criteria has been
checked off against working behaviour — a ticket whose criteria are unbuilt is
`ready-for-agent`, not `closed`.

## Format

A ticket records its state on a `Status:` line near the top, with the string in
backticks:

```
Status: `ready-for-agent`
```

The spec file uses the same line and the same vocabulary.

## GitHub labels

On the public repository, these strings are the label names: the same five
triage roles plus `closed`. This file is the source of truth, so creating or
renaming a label on GitHub without editing this table leaves triage writing
labels that do not exist.
