from pathlib import Path
import os
from typing import Type
from dataclasses import dataclass

from generator import SerialGeneratorObject, KDGeneratorObject, Generator

ACTION_LIST = [
    'create',
    'create-generator',
    'run'
]

WORKDIR = Path.cwd()
PYTHON_FILE_DIR = Path(os.path.dirname(os.path.realpath(__file__)))

TEMPLATES_DIR = PYTHON_FILE_DIR.joinpath('./templates')
PROJECTS_DIR = WORKDIR.joinpath('./compare-projects')
CONFIG_TEMPLATE_PATH = TEMPLATES_DIR.joinpath('config-template.json')
SERIAL_GENERATOR_TEMPLATE_PATH = TEMPLATES_DIR.joinpath('generator-serial-template.py')
KD_GENERATOR_TEMPLATE_PATH = TEMPLATES_DIR.joinpath('generator-kd-template.py')

# Generators:

# Overall information about each generator type:
@dataclass
class GeneratorTypeInfo:
    short_name: str
    description: str
    generator_object: Type

GENERATOR_TYPES = {
    "serial": GeneratorTypeInfo(
        'serial',
        """
The generator receives numbers from 0 to `count` as input. If `count` is not specified then 100 is used
        """,
        SerialGeneratorObject
    ),
    "kd": GeneratorTypeInfo(
        'kd',
        """
The generator receives input `d` numbers separated by a space. `d` must be specified in the config. Such numbers are generated `count` times. If `count` is not specified then 100 is used
        """,
        KDGeneratorObject
    )
}

SUPPORTED_EXEC_TYPES = [
    'binary',
    'python'
]

DEFAULT_EXEC_TYPE = 'binary'

SUPPORTED_GENERATOR_TYPES_SHORT_NAMES = GENERATOR_TYPES.keys()

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
                'type': {'enum': SUPPORTED_GENERATOR_TYPES_SHORT_NAMES},
                'name': {'type': 'string'},
                'program': {'$ref': '#/$defs/program'},
                'generator_config': {'type': 'object'}
            },
            'required': ['name', 'program']
        }
    }
}
