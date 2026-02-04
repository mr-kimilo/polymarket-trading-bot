# KANBAN Workflow 

Unified Kanban Columns (Project Level):

* **Backlog** (Requirement Pool)
* **To Do** (Sprint/Current Week To-Do)
* **In Progress** (Development in Progress)
* **In Review** (Code Review)
* **Testing / QA** (QA Testing in Progress)
* **Blocked** (Blocked)
* **Done** (Accepted)

> Each task card must include: Objective, Subtask, Developer, Estimated Complexity (S/M/L), Acceptance Criteria, Test Cases, Related Documents/Designs, and Dependent Tasks.

## Task Status Definition (Strict)

* **Development (In Progress)**: In addition to completing the task, unit tests (if applicable) must also be included.
* **Code Review (In Review)**: The PR description must clearly state the changes, how they will be implemented, the impact, and the risk of regression. Approved by at least one reviewer (you can switch roles). * **QA (Testing):** QA executes test cases, records bugs, and classifies them into P0/P1/P2. All P0 issues must be resolved, and P1 issues require evaluation. After completion, the QA writes "QA Passed" on the card (you switch roles).
* **Acceptance/Done**: The product manager or maintainer performs final acceptance of the acceptance criteria. If passed, the card is moved to Done. (You switch roles)

Kanban data is recorded in the `./kanban/` directory (Markdown format).
- `./kanban/board.md` maintains the Kanban board status.
- The `./kanban/issues/` directory stores detailed Markdown descriptions of each task. Each task has a file named with the task ID, such as `A-1-initialize-repo.md`. This file should not only record the task description, but also issues encountered during development and their solutions, bug records, and review comments.