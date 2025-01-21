import json

import asyncio

from typing import List, Tuple, Any, Callable, Awaitable
from enum import Enum
from pathlib import Path
import multiprocessing
import shutil

from program import Program, run_programs
from settings import DEFAULT_EXEC_TYPE, DEFAULT_GENERATOR_TYPE, GENERATOR_TYPES
from generator import Generator, GeneratorObject, SerialGeneratorObject
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
from functools import partial


def _create_generator_object(generator: Generator) -> GeneratorObject: 
    return GENERATOR_TYPES[generator.type].generator_object(generator)


@dataclass
class Task:
    input_path: Path
    output1_path: Path
    output2_path: Path
    report_directory_path: Path


@dataclass
class WorkerConfig:
    worker_function: Callable[[asyncio.Queue, asyncio.Queue], Awaitable[Any]] | Callable[[asyncio.Queue], Awaitable[Any]] 
    worker_count: int


class Pipeline:
    def __init__(self, *args: WorkerConfig):
        self.workers = args
        self.workers_count = len(args)
    
    async def _initialize_queues(self):
        self.queues = [asyncio.Queue() for _ in range(self.workers_count)]
    
    async def _start_workers(self):
        for idx, worker in enumerate(self.workers):
            for _ in range(worker.worker_count):
                if idx == self.workers_count - 1:
                    asyncio.create_task(worker.worker_function(self.queues[idx]))
                else:
                    asyncio.create_task(worker.worker_function(
                        self.queues[idx],
                        None if idx == self.workers_count - 1 else self.queues[idx + 1]
                    ))
    
    async def _wait_queues(self):
        for queue in self.queues:
            await queue.join()

    async def run_list(self, tasks_list):
        if self.workers_count == 0:
            return 
        
        await self._initialize_queues()
        
        for task in tasks_list:
            self.queues[0].put_nowait(task)
        
        await self._start_workers()
        await self._wait_queues()

    async def run_async_generator(self, async_generator):
        raise NotImplemented

    async def run_generator(self, generator):
        raise NotImplemented


class Config:
    def __init__(self, config_obj, path_prefix=Path("")):
        def _value_from_dict_or_default(name: str, dictionary: Any, default_value: Any):
            if name not in dictionary.keys():
                return default_value
            return dictionary[name]
        
        def _extract_program(obj):
            return Program(
                path_prefix.joinpath(obj['path']),
                _value_from_dict_or_default('type', obj, DEFAULT_EXEC_TYPE)
            )
        
        def _extract_generator(obj):
            return Generator(
                obj['name'],
                _value_from_dict_or_default('type', obj, DEFAULT_GENERATOR_TYPE),
                _extract_program(obj['program']),
                _value_from_dict_or_default('generator_config', obj, {})
            )

        # Extract info from json to python classes
        self.program1 = _extract_program(config_obj['program1'])
        self.program2 = _extract_program(config_obj['program2'])
        self.generators = [_extract_generator(generator) for generator in config_obj['generators']]

    def json_dump(self, stream):
        obj = {
            'program1': self.program1.to_object(),
            'program2': self.program2.to_object(),
            'generators': [generator.to_object() for generator in self.generators]
        }
        json.dump(obj, stream, indent=4)

    def get_generators(self):
        return self.generators
    
    def get_program1(self):
        return self.program1
    
    def get_program2(self):
        return self.program2
    
    def set_generators(self, generators: List[Generator]):
        self.generators = generators

    def push_generator(self, generator: Generator):
        self.generators.append(generator)
    
    def set_program1(self, program: Program):
        self.program1 = program
    
    def set_program2(self, program: Program):
        self.program2 = program


def _first_mismatch_index(str1: str, str2: str) -> int:
    for i in range(max(len(str1), len(str2))):
        if i >= len(str1) or i >= len(str2):
            return i
        if str1[i] != str2[i]:
            return i
    return -1

def _compare(filename1: Path, filename2: Path) -> Tuple[bool, str]:
    linenumber = 0
    with open(filename1, 'r') as f1, open(filename2, 'r') as f2:
        while True:
            linenumber += 1
            line1 = f1.readline()
            line2 = f2.readline()
            if line1 == '' and line2 == '':
                return True, ''
            elif line1 == '' or line2 == '':
                return False, f'Unexpected end of file in line {linenumber} in file {filename1 if line1 == '' else filename2}'
            if line1 != line2:
                return False, f'Mismatch in line {linenumber} and column {_first_mismatch_index(line1, line2) + 1}'

async def remove_file(filename: Path):
    return await asyncio.create_subprocess_exec('rm', str(filename))

# Pipeline setup
# Tasks are path objects
# Pipeline: generator_worker -> exec_worker -> compare_worker -> clean_up_worker
async def generator_worker(generator_object: GeneratorObject, input_tasks: asyncio.Queue, output_tasks: asyncio.Queue):
    while True:
        task = await input_tasks.get()
        await generator_object.generate(task.input_path)
        input_tasks.task_done()
        # Put task in the next queue
        output_tasks.put_nowait(task)

async def exec_worker(programs: Tuple[Program, Program], input_tasks: asyncio.Queue, output_tasks: asyncio.Queue):
    while True:
        task = await input_tasks.get()
        await run_programs([
            (programs[0], task.input_path, task.output1_path),
            (programs[1], task.input_path, task.output2_path)
        ])
        input_tasks.task_done()
        # Put task in the next queue
        output_tasks.put_nowait(task)

async def compare_worker(input_tasks: asyncio.Queue, output_tasks: asyncio.Queue):
    while True:
        task = await input_tasks.get()

        with ProcessPoolExecutor() as pool:
            loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
            process_coroutine = loop.run_in_executor(pool, partial(_compare, task.output1_path, task.output2_path))
            results = await asyncio.gather(process_coroutine)
            result, verbose = results[0]

        if not result:
            print(f'Compare mismatch in files {task.output1_path} and {task.output2_path}: {verbose}.')
            print(f'Saved input file for them: {task.input_path}')
            shutil.copy(task.input_path, task.report_directory_path)
        input_tasks.task_done()
        # Put task in the next queue
        output_tasks.put_nowait(task)

async def clean_up_worker(input_tasks: asyncio.Queue):
    while True:
        task = await input_tasks.get()
        processes = (
            await remove_file(task.input_path),
            await remove_file(task.output1_path),
            await remove_file(task.output2_path),
        )
        for process in processes:
            await process.wait()
        input_tasks.task_done()

# Simply prints about comparison in stdout
async def run_generator(program1: Program, program2: Program, generator: Generator, buf_dir: Path, report_dir: Path):
    GENERATOR_WORKERS = 5
    EXEC_WORKERS = 5
    COMPARE_WORKERS = 5
    CLEAN_UP_WORKERS = 5

    buf_dir.mkdir(exist_ok=True, parents=True)
    report_dir.mkdir(exist_ok=True, parents=True)

    # TODO: Refactor (maybe)
    tasks = [
        Task(
            buf_dir.joinpath(f'{generator.name}_in_{i}'),
            buf_dir.joinpath(f'{generator.name}_out1_{i}'),
            buf_dir.joinpath(f'{generator.name}_out2_{i}'),
            report_dir
        ) for i in range(generator.generator_config['count'])
    ]

        
    pipeline = Pipeline(
        WorkerConfig(
            partial(generator_worker, _create_generator_object(generator)),
            GENERATOR_WORKERS
        ),
        WorkerConfig(
            partial(exec_worker, (program1, program2)),
            EXEC_WORKERS
        ),
        WorkerConfig(
            compare_worker,
            COMPARE_WORKERS
        ),
        WorkerConfig(
            clean_up_worker,
            CLEAN_UP_WORKERS
        )
    )
    
    await pipeline.run_list(tasks)
