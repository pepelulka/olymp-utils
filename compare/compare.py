#!/usr/bin/python
import json
import argparse
import shutil

import asyncio

from settings import *
from utils import *
from program import Program
from generator import Generator
from core import run_generator, Config

# It doesn't check for project existance
def create_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    # Create project directory
    project_dir.mkdir(exist_ok=True, parents=True)
    # Create template for config
    project_config = project_dir.joinpath('config.json')
    project_config.touch()
    shutil.copy(CONFIG_TEMPLATE_PATH, project_config)

def create_generator(name, gen_name, gen_type):
    project_dir = PROJECTS_DIR.joinpath(name)
    # Create generators directory
    generators_dir = project_dir.joinpath('generators')
    generators_dir.mkdir(exist_ok=True, parents=True)
    # Create template for config
    generator_exec_file = generators_dir.joinpath(f'{gen_name}.py')
    gen_config = {'count': 100}
    # TODO: Refactor
    match gen_type:
        case 'serial':
            shutil.copy(SERIAL_GENERATOR_TEMPLATE_PATH, generator_exec_file)
        case 'kd':
            shutil.copy(KD_GENERATOR_TEMPLATE_PATH, generator_exec_file)
        case _:
            fail(f"Undefined generator type {gen_type}")
    # Edit config
    project_config = project_dir.joinpath('config.json')
    with open(project_config, 'r') as cfg_file:
        obj = json.load(cfg_file)
    config = Config(obj)
    new_generator = Generator(
        gen_name,
        gen_type,
        Program(
            f'generators/{gen_name}.py',
            'python'
        ),
        gen_config
    )
    config.push_generator(new_generator)
    with open(project_config, 'w') as cfg_file:
        config.json_dump(cfg_file)


def run_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    project_config = project_dir.joinpath('config.json')
    with open(project_config, 'r') as cfg_file:
        obj = json.load(cfg_file)
    config = Config(obj, path_prefix=project_dir)
    for generator in config.generators:
        print(f'Running generator {generator.name}...')
        asyncio.run(run_generator(
            config.program1,
            config.program2,
            generator,
            project_dir.joinpath('.compare-buf'),
            project_dir.joinpath('out')
        ))
        print(f'Generator {generator.name} finished!')

def command_create_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    if project_dir.exists():
        fail(f"project {name} already exists!")
    create_project(name)

def command_run_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    if not project_dir.exists():
        fail(f"project {name} doesn't exist!")
    run_project(name)

# example:
# compare.py create-generator <project-name> <generator-name> [generator-type]
def command_create_generator(name, args):
    project_dir = PROJECTS_DIR.joinpath(name)
    if not project_dir.exists():
        fail(f"project {name} doesn't exist!")
    
    if len(args) == 0:
        fail("You must specify generator name!")
    
    if len(args) == 1:
        gen_type = DEFAULT_GENERATOR_TYPE
        warning(f"generator type was not specified, using default generator type: {DEFAULT_GENERATOR_TYPE}")
    else:
        gen_type = args[1]
        if gen_type not in SUPPORTED_GENERATOR_TYPES_SHORT_NAMES:
            fail(f"{args[1]} generator type is not supported. List of supported generator types: {", ".join(SUPPORTED_GENERATOR_TYPES_SHORT_NAMES)}")
    
    create_generator(name, args[0], gen_type)


def parse_args():
    parser = argparse.ArgumentParser(
        prog="compare.py",
        description="Tool to find corner cases in your programs",
        epilog=""
    )
    parser.add_argument(
        'action',
        choices=ACTION_LIST
    )
    parser.add_argument("name", type=str)
    parser.add_argument("args", nargs="*")

    return parser.parse_args()

def main():
    args = parse_args()
    if args.action == 'create':
        command_create_project(args.name)
    elif args.action == 'run':
        command_run_project(args.name)
    elif args.action == 'create-generator':
        command_create_generator(args.name, args.args)

if __name__ == "__main__":
    main()
