#!/usr/bin/env python

import sys, argparse, json

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')

def main(args):
    print_err('loading: {}'.format(args.sample_data))
    with open(args.sample_data) as file:
        data = json.load(file)

    for i,solution in enumerate(data):
        output_file = '{}_{:05d}.csv'.format(args.csv_prefix, i)
        print_err('writing: {}'.format(output_file))

        with open(output_file, 'w') as file:
            file.write('count, ' + ', '.join([str(vid) for vid in solution['variable_ids']]) + '\n')
            for solution_data in solution['solutions']:
                row = [solution_data['num_occurrences']] + solution_data['solution']
                #print(', '.join([str(x) for x in row]))
                file.write(', '.join([str(x) for x in row]) + '\n')

def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('sample_data', help='a data file to operate on (.json)')

    parser.add_argument('csv_prefix', help='output file prefix (.csv)')

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())
