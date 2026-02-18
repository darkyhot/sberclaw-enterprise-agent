---
name: skill-creator
description: Create or update Agent Skills in skills/<skill-name>/SKILL.md format. Use when user asks to create a new skill, fix broken SKILL.md formatting, or make skills compatible with https://agentskills.io/specification. Always keep strict Markdown structure and YAML frontmatter.
---

# Skill Creator

Use this skill when a task is about creating or fixing skills.

## Rules

1. Always create skills as directories: `skills/<skill-name>/`.
2. Always create `SKILL.md` with valid YAML frontmatter + Markdown body.
3. Keep frontmatter limited to:
   - `name`
   - `description`
4. When generating a new skill, only write the user-specific text into `description`.
5. Keep the Markdown body in standard template structure from `references/skill_template.md`.
6. If deterministic generation is needed, run:
   - `run_skill_script` with `script_path="skill-creator/scripts/render_skill_md.py"`

## Output Contract

For generated skill documents:

1. Start with YAML frontmatter delimited by `---`.
2. Include required fields:
   - `name: <skill-name>`
   - `description: <user-specific description>`
3. Then include Markdown headings and sections from the template.
4. Never output plain text without Markdown structure.

## Procedure

1. Determine `skill-name` from user request.
2. Write one clear description sentence or short paragraph.
3. Render `SKILL.md` using template:
   - Prefer `scripts/render_skill_md.py` for consistency.
4. Save file to:
   - `skills/<skill-name>/SKILL.md`
5. If needed, add optional folders:
   - `scripts/`
   - `references/`
   - `assets/`
