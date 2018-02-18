#!/usr/bin/env python

import sys, argparse, json

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')

def main(args):
    print_err('loading: {}'.format(args.sample_data))
    with open(args.sample_data) as file:
        data = json.load(file)

    for solution_data in data['solutions']:
        row = [solution_data['num_occurrences']] + solution_data['num_solution']
        print(', '.join([str(x) for x in row]))

def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('sample_data', help='a data file to operate on (.json)')

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())
