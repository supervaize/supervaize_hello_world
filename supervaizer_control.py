# Copyright (c) 2024-2025 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

# This is an example file.
# It must be copied / renamed to supervaizer_control.py
# and edited to configure your agent(s)

import os

import shortuuid
from supervaizer import (
    Account,
    Agent,
    AgentMethod,
    AgentMethodField,
    AgentMethods,
    Parameter,
    ParametersSetup,
    Server,
)

import agent_rules
from agent_configurator import CONFIGURATOR_SURFACE, CONFIGURE_ACTION
from agent_dashboard import ANALYTICS_SURFACE, DATASET_QUERY_ACTION
from agent_data_resource import contacts_resource
from agent_v2 import (
    CONTACT_ACTIONS,
    build_human_loop_v2_registration,
    build_simple_agent_v2_registration,
    handle_human_loop_v2_action,
    handle_human_loop_v2_surface,
    handle_simple_v2_action,
    handle_simple_v2_surface,
)

#### SIMPLE AGENT ####
agent_name = "Hello World AI Agent"

# Define the parameters and secrets expected by the agent
simple_agent_parameters = ParametersSetup.from_list([
    Parameter(
        name="SIMPLE AGENT PARAMETER",
        description="Setup agent parameter in this workspace",
        is_environment=True,
    ),
    Parameter(
        name="SIMPLE AGENT SECRET",
        description="Setup agent secret in this workspace",
        is_environment=True,
        is_secret=True,
    ),
])


# Define the start method for the agent
job_start_method = AgentMethod(
    name="start",
    method="agent_simple.job_start",
    is_async=False,
    params={"action": "start"},
    fields=[
        AgentMethodField(
            name="How many times to say hello",
            type=int,
            field_type="IntegerField",
            required=True,
        )
    ],
)
job_stop_method = AgentMethod(
    name="stop",
    method="agent_simple.job_stop",
    is_async=False,
    params={"action": "stop"},
    description="Stop the running job",
)
job_status_method = AgentMethod(
    name="status",
    method="agent_simple.job_status",
    is_async=False,
    params={"action": "status"},
    description="Get the status of the agent",
)
# Define the Agent
simple_agent: Agent = Agent(
    name=agent_name,
    id=shortuuid.uuid(f"{agent_name}"),
    author="Alain Prasquier <al1@supervaize.com>",  # Author of the agent
    version="1.1",  # Version string
    description="This is a test agent",
    tags=["hello world", "ai agent"],
    methods=AgentMethods(
        job_start=job_start_method,
        job_stop=job_stop_method,
        job_status=job_status_method,
    ),
    parameters_setup=simple_agent_parameters,
    data_resources=[contacts_resource],
    supervaizer_v2_registration=build_simple_agent_v2_registration("1.1"),
)


#### HUMAN-IN-THE-LOOP AGENT ####
human_loop_agent_name = "Human-in-the-Loop Agent"

human_loop_job_start = AgentMethod(
    name="start",
    method="agent_human_loop.job_start",
    is_async=False,
    params={"action": "start"},
    fields=[
        AgentMethodField(
            name="How many cases to run",
            type=int,
            field_type="IntegerField",
            required=True,
        )
    ],
)
human_loop_job_stop = AgentMethod(
    name="stop",
    method="agent_human_loop.job_stop",
    is_async=False,
    params={"action": "stop"},
    description="Stop the running job",
)
human_loop_job_status = AgentMethod(
    name="status",
    method="agent_human_loop.job_status",
    is_async=False,
    params={"action": "status"},
    description="Get the status of the agent",
)
human_loop_human_answer = AgentMethod(
    name="human_answer",
    method="agent_human_loop.handle_human_input",
    is_async=False,
    fields=[],
)

human_loop_agent: Agent = Agent(
    name=human_loop_agent_name,
    id=shortuuid.uuid(human_loop_agent_name),
    author="Alain Prasquier <al1@supervaize.com>",
    version="1.0",
    description="Runs cases with a human approval step before each case completes.",
    tags=["hello world", "human in the loop", "approval"],
    methods=AgentMethods(
        job_start=human_loop_job_start,
        job_stop=human_loop_job_stop,
        job_status=human_loop_job_status,
        human_answer=human_loop_human_answer,
    ),
    supervaizer_v2_registration=build_human_loop_v2_registration("1.0"),
)


# Always provide a default value to prevent error.
# Get from app.supervaize.com
supervaize_account: Account = Account(
    workspace_id=os.getenv("SUPERVAIZE_WORKSPACE_ID") or "dummy_workspace_id",
    api_key=os.getenv("SUPERVAIZE_API_KEY") or "dummy_api_key",
    api_url=os.getenv("SUPERVAIZE_API_URL") or "https://app.supervaize.com",
)

# Define the supervaizer server capabilities
sv_server: Server = Server(
    agents=[simple_agent, human_loop_agent],
    a2a_endpoints=True,  # Enable A2A endpoints
    supervisor_account=supervaize_account,  # Account from Supervaize
)


def _register_v2_handlers(server: Server) -> None:
    for surface in ("job.start", "case.step.awaiting", CONFIGURATOR_SURFACE, ANALYTICS_SURFACE):
        server.register_v2_surface(
            surface,
            handle_simple_v2_surface,
            agent_slug=simple_agent.slug,
        )
    for action in (
        "job.start.preview",
        "job.start",
        "job.sync",
        "step.awaiting.submit",
        # Replaces the SDK default resume handler, which only wakes an
        # in-process SDK Case gate; this agent keeps its gates in agent_rules.
        agent_rules.RESUME_ACTION,
        CONFIGURE_ACTION,
        DATASET_QUERY_ACTION,
        *CONTACT_ACTIONS,
    ):
        server.register_v2_action(
            action,
            handle_simple_v2_action,
            agent_slug=simple_agent.slug,
        )

    server.register_v2_surface(
        "job.start",
        handle_human_loop_v2_surface,
        agent_slug=human_loop_agent.slug,
    )
    server.register_v2_surface(
        "case.step.awaiting",
        handle_human_loop_v2_surface,
        agent_slug=human_loop_agent.slug,
    )
    for action in ("job.start.preview", "job.start", "job.sync", "step.awaiting.submit"):
        server.register_v2_action(
            action,
            handle_human_loop_v2_action,
            agent_slug=human_loop_agent.slug,
        )


_register_v2_handlers(sv_server)
# The rule checkpoint gate posts to Studio with the supervisor account.
agent_rules.account = sv_server.supervisor_account


# Expose the FastAPI app instance for deployment
app = sv_server.app


if __name__ == "__main__":
    # Start the supervaize server
    sv_server.launch(log_level="DEBUG")
