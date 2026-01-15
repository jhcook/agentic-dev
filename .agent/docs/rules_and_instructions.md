# Rules & Instructions

## Instructions

Each role has a specific instruction file in `.agent/instructions/`.
- `architect.md`: Directives for system design.
- `security.md`: Directives for vulnerability scanning.

## Rules

Rules are global constraints located in `.agent/rules/`.
Common rules:
- `tech-stack.mdc`: Defines allowed languages and frameworks.
- `colours.mdc`: Defines the design system palette.
- `test.mdc`: Testing requirements.

## Creating New Rules

1.  Create a markdown file in `.agent/rules/`.
2.  Use the `.mdc` extension.
3.  Write clear, imperative constraints.
