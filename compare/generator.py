#
# Source code for 
#

from dataclasses import dataclass
from typing import Any, ClassVar
from abc import ABC, abstractmethod
from pathlib import Path
import asyncio

from utils import *
from program import Program, exec_program_async, forward_from_stream

@dataclass
class Generator(JsonObject):
    name: str
    type: str
    program: Program
    generator_config: Any

    def to_object(self):
        return {
            'name': self.name,
            'type': self.type,
            'program': self.program.to_object(),
            'generator_config': self.generator_config
        }

# Stores generator and actually generates data using underlying generator
class GeneratorObject(ABC):
    # 
    @abstractmethod
    async def generate(self, filepath: Path):
        pass

# Starting with `n` = 0 and go up to infinity
# Each call of generate() function increments `n`
class SerialGeneratorObject(GeneratorObject):    
    def __init__(self, generator):
        if generator.type != 'serial':
            fail(f'SerialGeneratorObject got non-serial generator, got {generator.type} instead')
        self.generator = generator

        self.n = 0
        self.lock = asyncio.Lock()
    
    async def generate(self, filename=Path):
        async with self.lock:
            process = await exec_program_async(self.generator.program, [str(self.n)])
            self.n += 1
        with open(filename, 'wb') as f:
            task = asyncio.create_task(forward_from_stream(process.stdout, f))
            await process.wait()
            await task

class KDGeneratorObject(GeneratorObject):
    def __init__(self, generator):
        if generator.type != 'kd':
            fail(f'KDGeneratorObject got non-kd generator, got {generator.type} instead')
        self.generator = generator
        self.dimensions = generator.generator_config['d']
        self.lock = asyncio.Lock()
        
        self.counts = [0] * self.dimensions

    def _inc_minimal(self):
        min_element = self.counts[0]
        min_idx = 0
        for idx, el in enumerate(self.counts):
            if el < min_element:
                min_element = el
                min_idx = idx
        self.counts[min_idx] += 1

    async def generate(self, filename=Path):
        async with self.lock:
            process = await exec_program_async(self.generator.program, [str(arg) for arg in self.counts])
            self._inc_minimal()
        with open(filename, 'wb') as f:
            task = asyncio.create_task(forward_from_stream(process.stdout, f))
            await process.wait()
            await task
