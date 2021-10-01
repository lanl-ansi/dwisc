#!/usr/bin/env python3

# combines ising samples

import sys, os, argparse, json, datetime

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

addative_times = [ 'total_real_time', 'post_processing_overhead_time',
    'qpu_sampling_time', 'total_post_processing_time', 'qpu_programming_time',
    'run_time_chip', 'qpu_access_time'
]

constant_times = [ 'anneal_time_per_run', 'readout_time_per_run',
    'qpu_readout_time_per_sample', 'qpu_delay_time_per_sample',
    'qpu_anneal_time_per_sample', 'qpu_access_overhead_time'
]

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')

def main(args):
    file_locations = []
    for dir_name, subdir_list, file_list in os.walk(args.sample_directory):
        for file_name in sorted(file_list):
            if file_name.endswith('.json'):
                file_locations.append(os.path.join(dir_name, file_name))


    solutions = None

    for file_loc in file_locations:
        print_err('loading: {}'.format(file_loc))
        with open(file_loc) as file:
            try:
                data = json.load(file)
            except:
                print_err('json parsing error: {}'.format(file_loc))
                continue
        
        #TODO check that data is a "solutions" json file
        
        data['collection_start'] = datetime.datetime.strptime(data['collection_start'], TIME_FORMAT)
        data['collection_end'] = datetime.datetime.strptime(data['collection_end'], TIME_FORMAT)

        if solutions != None:
            combine_solution_data(solutions, data)
        else:
            solutions = data

    if solutions == None:
        print_err('no results found')
        return

    if not args.combine_only:
        merge_solution_counts(solutions)

    print_err('')
    print_err('collection_time: {}'.format(str(solutions['collection_end']-solutions['collection_start'])))

    print_err('')
    total_collected = sum(solution['num_occurrences'] for solution in solutions['solutions'])
    print_err('total collected: {}'.format(total_collected))
    for i, solution in enumerate(solutions['solutions']):
        print_err('  %f - %d' % (solution['energy'], solution['num_occurrences']))
        if i >= 50:
            print_err('  first 50 of {} solutions'.format(len(solutions['solutions'])))
            break

    print_err('')
    solutions['collection_start'] = solutions['collection_start'].strftime(TIME_FORMAT)
    solutions['collection_end'] = solutions['collection_end'].strftime(TIME_FORMAT)
    print(json.dumps(solutions))


def combine_solution_data(solutions_all, solutions):
    # check data compatablity
    assert(len(solutions_all['variable_ids']) == len(solutions['variable_ids']))
    for i in range(len(solutions_all['variable_ids'])):
        assert(solutions_all['variable_ids'][i] == solutions['variable_ids'][i])

    for k in addative_times:
        if k in solutions['timing']:
            solutions_all['timing'][k] = solutions_all['timing'][k] + solutions['timing'][k]

    for k in constant_times:
        if k in solutions['timing']:
            if solutions_all['timing'][k] != solutions['timing'][k]:
                solutions_all['timing'][k] = None

    collection_start = min(solutions_all['collection_start'], solutions['collection_start'])
    collection_end   = max(solutions_all['collection_end'], solutions['collection_end'])

    solutions_all['collection_start'] = collection_start
    solutions_all['collection_end'] = collection_end

    if 'solve_ising_args' in solutions_all:
        if 'solve_ising_args' in solutions:
            for k,v in solutions['solve_ising_args'].items():
                if k in solutions_all and v != solutions_all['solve_ising_args'][k]:
                    del solutions_all['solve_ising_args'][k]
        else:
            del solutions_all['dw_parameters']

    if 'metadata' in solutions_all:
        if 'metadata' in solutions:
            for k,v in solutions['metadata'].items():
                if k in solutions_all and v != solutions_all['metadata'][k]:
                    del solutions_all['metadata'][k]
        else:
            del solutions_all['metadata']

    for new_solution in solutions['solutions']:
        solutions_all['solutions'].append(new_solution)


def merge_solution_counts(solutions):
    print_err('')
    print_err('merge solutions:')
    print_err('  base solutions: {}'.format(len(solutions['solutions'])))

    solution_lookup = {}
    for solution in solutions['solutions']:
        sol = tuple(solution['solution'])
        if sol in solution_lookup:
            solution_lookup[sol]['num_occurrences'] += solution['num_occurrences']
        else:
            solution['batch'] = 0
            solution_lookup[sol] = solution

    new_solutions = [sol for sol in solution_lookup.values()]
    max_num_occurrences = max(sol['num_occurrences'] for sol in new_solutions)
    new_solutions.sort(key=lambda x: x['energy']*max_num_occurrences - x['num_occurrences'])

    solutions['solutions'] = new_solutions
    print_err('  reduced solutions: {}'.format(len(solutions['solutions'])))


def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('-co', '--combine-only', help='stops the process of merging solution counts (used for raw data collection)', action='store_true')
    parser.add_argument('-sd', '--sample-directory', help='a directory of data files to operate on (.json)', required=True)

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())