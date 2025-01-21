from utils import JsonObject
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import asyncio
from asyncio import StreamReader, StreamWriter

@dataclass
class Program(JsonObject):
    path: Path
    type: str

    def to_object(self):
        return {
            'path': str(self.path),
            'type': self.type
        }

# `output` must support write function for text
# Constantly forwarding data from async stream reader to output stream 
async def forward_from_stream(stream: StreamReader, output):
    BUF_SIZE = 1024
    while True:
        content = await stream.read(BUF_SIZE)
        if len(content) == 0:
            return
        output.write(content)

async def forward_into_stream(stream: StreamWriter, input):
    BUF_SIZE = 1024
    while True:
        content = input.read(BUF_SIZE)
        if len(content) == 0:
            return
        stream.write(content)
        await stream.drain()

async def exec_program_async(p: Program, args: List[str] = ()):
    if p.type == 'binary':
        return await asyncio.create_subprocess_exec(p.path, *args, stdout=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE)
    elif p.type == 'python':
        return await asyncio.create_subprocess_exec('python', p.path, *args, stdout=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE)
    return AssertionError(f'undefined type of program: {p.type}')


async def run_programs(programs_and_out_files: List[Tuple[Program, Path, Path]]):
    cnt = len(programs_and_out_files)
    processes = []
    files = []
    tasks = []
    # Init
    for program, input_filename, output_filename in programs_and_out_files:
        processes.append(await exec_program_async(program))
        files.append(open(input_filename, 'rb'))
        files.append(open(output_filename, 'wb'))
        tasks.append(asyncio.create_task(forward_from_stream(processes[-1].stdout, files[-1])))
        tasks.append(asyncio.create_task(forward_into_stream(processes[-1].stdin, files[-2])))
    # Waiting
    for i in range(cnt):
        await processes[i].wait()
        await tasks[2 * i]
        await tasks[2 * i + 1]
        files[2 * i].close()
        files[2 * i + 1].close()
