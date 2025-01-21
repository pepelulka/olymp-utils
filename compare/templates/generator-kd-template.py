#!/usr/bin/python
from sys import argv
from random import randint
from typing import List

def generate(args: List[int]):
    # Here we are generating some data and print it to stdout
    # 
    #   PLACE YOUR CODE HERE
    #
    pass

if __name__ == '__main__':
    if len(argv) < 2:
        print("missing args")
        exit(1)

    args = list(map(int, argv[1:]))

    generate(args)
