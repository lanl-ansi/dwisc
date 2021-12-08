#!/usr/bin/env python

import sys, argparse, json

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')

def main(args):
    print_err('loading: {}'.format(args.sample_data))
    with open(args.sample_data) as file:
        data = json.load(file)

    if not args.raw_data:
        header = ['num_occurrences'] + data['variable_ids']
        print(', '.join([str(x) for x in header]))

        for solution_data in data['solutions']:
            row = [solution_data['num_occurrences']] + solution_data['solution']
            print(', '.join([str(x) for x in row]))

    else:
        header = ['batch'] + data['variable_ids']
        print(', '.join([str(x) for x in header]))

        for solution_data in data['solutions']:
            row = [solution_data['batch']] + solution_data['solution']
            print(', '.join([str(x) for x in row]))

            if solution_data['num_occurrences'] > 1:
                print_err('printing raw data but num_occurrences of {} found'.format(solution_data['num_occurrences']))


def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('sample_data', help='a data file to operate on (.json)')

    parser.add_argument('-raw', '--raw-data', help='collect sample streams rather than histograms', action='store_true', default=False)

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())
