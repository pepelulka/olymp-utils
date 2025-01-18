import json
import os
import sys
import argparse
import shutil

import asyncio
from asyncio import StreamReader
import subprocess

from dataclasses import dataclass

from pathlib import Path

from enum import Enum

from jsonschema import validate

from typing import List, Tuple, Any

ACTION_LIST = [
    'create',
    'run'
]

WORKDIR = Path.cwd()
PYTHON_FILE_DIR = Path(os.path.dirname(os.path.realpath(__file__)))

TEMPLATES_DIR = PYTHON_FILE_DIR.joinpath('./.templates')
PROJECTS_DIR = WORKDIR.joinpath('./compare-projects')
CONFIG_TEMPLATE_PATH = TEMPLATES_DIR.joinpath('config-template.json')

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Runner logic here:
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

@dataclass
class Program:
    path: Path
    type: str

# `output` must support write function for text
# Constantly forwarding data from async stream reader to output stream 
async def forward_from_stream(stream: StreamReader, output):
    BUF_SIZE = 1024
    while True:
        content = await stream.read(BUF_SIZE)
        if len(content) == 0:
            return
        output.write(content)

async def exec_program_async(p: Program, args: List[str] = ()):
    if p.type == 'binary':
        return await asyncio.create_subprocess_exec(p.path, *args, stdout=asyncio.subprocess.PIPE)
    elif p.type == 'python':
        return await asyncio.create_subprocess_exec('python', p.path, *args, stdout=asyncio.subprocess.PIPE)
    return AssertionError(f'undefined type of program: {p.type}')


async def run_programs(programs_and_out_files: List[Tuple[Program, Path]]):
    cnt = len(programs_and_out_files)
    processes = []
    files = []
    tasks = []
    # Init
    for program, filename in programs_and_out_files:
        processes.append(await exec_program_async(program))
        files.append(open(filename, 'wb'))
        tasks.append(asyncio.create_task(forward_from_stream(processes[-1].stdout, files[-1])))
    # Waiting
    for i in range(cnt):
        await processes[i].wait()
        await tasks[i]
        files[i].close()

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Core logic here:
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

SUPPORTED_EXEC_TYPES = [
    'binary',
    'python'
]

DEFAULT_EXEC_TYPE = 'binary'

SUPPORTED_GENERATOR_TYPES = [
    'serial'
]

DEFAULT_GENERATOR_TYPE = 'serial'

CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'program1': {'$ref': '#/$defs/program'},
        'program2': {'$ref': '#/$defs/program'},
        'generators': {
            'type': 'array',
            'items': {
                '$ref': '#/$defs/generator'
            }
        },
        'required': ['program1', 'program2', 'generators']
    },
    '$defs': {
        'program': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'type': {'enum': SUPPORTED_EXEC_TYPES} 
            },
            'required': ['path']
        },
        'generator': {
            'type': 'object',
            'properties': {
                'type': {'enum': SUPPORTED_GENERATOR_TYPES},
                'name': {'type': 'string'},
                'program': {'$ref': '#/$defs/program'},
                'generator_config': {'type': 'object'}
            },
            'required': ['name', 'program']
        }
    }
}

@dataclass
class Generator:
    name: str
    type: str
    program: Program
    generator_config: Any

class Config:
    def __init__(self, config_obj):
        def value_from_dict_or_default(name: str, dictionary: Any, default_value: Any):
            if name not in dictionary.keys():
                return default_value
            return dictionary[name]
        
        def extract_program(obj):
            return Program(
                obj['path'],
                value_from_dict_or_default('type', obj, DEFAULT_EXEC_TYPE)
            )
        
        def extract_generator(obj):
            return Generator(
                obj['name'],
                value_from_dict_or_default('type', obj, DEFAULT_GENERATOR_TYPE),
                extract_program(obj['program']),
                value_from_dict_or_default('generator_config', obj, {})
            )

        # Extract info from json to python classes
        self.program1 = extract_program(config_obj['program1'])
        self.program2 = extract_program(config_obj['program2'])
        self.generators = [extract_generator(generator) for generator in self.generators]


# It doesn't check for project existance
def create_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    # Create project directory
    project_dir.mkdir(exist_ok=True, parents=True)
    # Create template for config
    project_config = project_dir.joinpath('config.json')
    project_config.touch()
    shutil.copy(CONFIG_TEMPLATE_PATH, project_config)


def run_project(name):
    asyncio.run(run_programs([
        (
            Program(
                Path("./a.py"),
                'python'
            ),
            'in_a'
        ),
        (
            Program(
                Path("./b.py"),
                'python'
            ),
            'in_b'
        )
    ]))


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Scripts logic here:
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def command_create_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    if project_dir.exists():
        eprint(f"Error: project {name} already exists!")
        sys.exit(1)
    create_project(name)

def command_run_project(name):
    project_dir = PROJECTS_DIR.joinpath(name)
    if not project_dir.exists():
        eprint(f"Error: project {name} doesn't exist!")
        sys.exit(1)
    run_project(name)


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

    return parser.parse_args()

def main():
    args = parse_args()
    if args.action == 'create':
        command_create_project(args.name)
    elif args.action == 'run':
        command_run_project(args.name)

if __name__ == "__main__":
    main()
