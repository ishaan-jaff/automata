# Add this import at the beginning of your file
import click

from automata.configs.config_enums import InstructionConfigVersion
from automata.core.utils import Namespace

from .click_options import common_options


@click.group()
@click.pass_context
def cli(ctx):
    pass


@common_options
@cli.command()
@click.option(
    "--instruction_version",
    type=str,
    default=f"{InstructionConfigVersion.AGENT_INTRODUCTION_DEV.value}",
    help="The config version of the agent.",
)
@click.option(
    "--include_overview",
    type=bool,
    help="Should the instruction prompt include an overview?",
)
@click.option(
    "--is_test",
    type=bool,
    help="Should we run with test execution?",
    default=False,
)
@click.pass_context
def task(ctx, *args, **kwargs):
    from .scripts.run_task import main

    main(kwargs)


@common_options
@cli.command()
@click.option(
    "--instruction_version",
    type=str,
    default=f"{InstructionConfigVersion.AGENT_INTRODUCTION_DEV.value}",
    help="The config version of the agent.",
)
@click.option(
    "--include_overview",
    type=bool,
    help="Should the instruction prompt include an overview?",
)
@click.pass_context
def main_coordinator(ctx, *args, **kwargs):
    from .scripts.run_coordinator import main

    main(kwargs)


@common_options
@cli.command()
@click.option(
    "--eval_config",
    type=str,
    help="What config are we evaluating on?",
    default="python_indexer_payload",
)
@click.pass_context
def evaluator(ctx, *args, **kwargs):
    from .scripts.run_evaluator import main

    namespace = Namespace(**kwargs)
    main(namespace)