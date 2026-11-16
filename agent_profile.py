"""How Studio presents the Hello World agent: roster introduction and detail page text."""

from supervaizer import V2AgentFullDescription, V2AgentIntroduction

# Studio renders the roster entry and the chat opening from this block.
INTRODUCTION = V2AgentIntroduction(
    tagline="Says hello, one case per greeting",
    summary=(
        "Creates a hello case for each greeting, with a greeting card, an optional "
        "human review, rule checkpoints and a contacts list. A reference for Supervaizer v2."
    ),
    example_goals=[
        "Say hello three times",
        "Greet each of my contacts",
        "Run one hello with a human review",
    ],
)

# Studio shows this on the agent detail page and sanitizes it first.
FULL_DESCRIPTION = V2AgentFullDescription(
    format="markdown",
    content="""# Hello World AI Agent

The reference agent for the Supervaizer v2 contract. Each job creates hello cases.
Each case delivers a greeting card.

## What it shows

- **Guided setup**: a setup plan with validation, a help action that suggests a count, and a cost estimate.
- **Test run**: a dry run that previews a greeting and creates no case.
- **Human in the loop**: an optional review case that waits for approval.
- **Rule checkpoints**: Studio mission rules can hold cases before and after the work.
- **Configurator and dashboard**: a Configure screen and analytics surfaces.
- **Contacts**: a shared data resource with list, create, update, delete and import.
- **Billing**: one SKU, `hello_message`, reported per greeting.

## Limits

- State is in memory. A restart loses running jobs.
- At most 100 hellos per job.
""",
)
