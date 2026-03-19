---
name: skill-template
description: Template for defining GROOT skills
version: "1.0"
trigger: manual
agent: any
input: { query: string }
output: { result: string }
---

# Skill Template

This is the base template for GROOT skills. Each skill is a reusable LLM workflow
that can be triggered by agents during the ACT phase of the cognitive loop.

## Format

Skills are defined as markdown files with YAML frontmatter:

```yaml
---
name: skill-name
description: One-line description (loaded into context as Layer 4)
version: "1.0"
trigger: manual | auto | event_pattern
agent: agent-archetype-name | any
input: { param: type }
output: { field: type }
---
```

## Body

The body of the SKILL.md contains the prompt template that the agent
uses when executing this skill. Variables from the input schema are
injected using `{variable_name}` syntax.
