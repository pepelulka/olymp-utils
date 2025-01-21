#!/usr/bin/python
from sys import argv
from random import randint

def generate(n: int):
    # Here we are generating some data and print it to stdout
    # 
    #   PLACE YOUR CODE HERE
    #
    pass

if __name__ == '__main__':
    if len(argv) < 2:
        print("missing arg")
        exit(1)

    n = int(argv[1])

    generate(n)