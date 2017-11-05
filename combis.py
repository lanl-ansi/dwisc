# combines ising samples

import sys, json

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

addative_times = [ 'total_real_time', 'post_processing_overhead_time',
    'qpu_sampling_time', 'total_post_processing_time', 'qpu_programming_time',
    'run_time_chip', 'qpu_access_time'
]

constant_times = [ 'anneal_time_per_run', 'readout_time_per_run',
    'qpu_readout_time_per_sample', 'qpu_delay_time_per_sample',
    'qpu_anneal_time_per_sample'
]

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')

def main(args):
    # if args.input_file == None:
    #     data = json.load(sys.stdin)
    # else:
    #     with open(args.input_file) as file:
    #         data = json.load(file)

    #bqpjson.validate(data)

    print_err('')
    solutions_all['collection_start'] = solutions_all['collection_start'].strftime(combis.TIME_FORMAT)
    solutions_all['collection_end'] = solutions_all['collection_end'].strftime(combis.TIME_FORMAT)
    print(json.dumps(solutions_all))

def combine_solution_data(solutions_all, solutions):
    # check data compatablity
    assert(len(solutions_all['variable_ids']) == len(solutions['variable_ids']))
    for i in range(len(solutions_all['variable_ids'])):
        assert(solutions_all['variable_ids'][i] == solutions['variable_ids'][i])

    for k in addative_times:
        solutions_all['timing'][k] = solutions_all['timing'][k] + solutions['timing'][k]

    for k in constant_times:
        if solutions_all['timing'][k] != solutions['timing'][k]:
            solutions_all['timing'][k] = None

    collection_start = min(solutions_all['collection_start'], solutions['collection_start'])
    collection_end   = max(solutions_all['collection_end'], solutions['collection_end'])

    solutions_all['collection_start'] = collection_start
    solutions_all['collection_end'] = collection_end

    if 'solve_ising_args' in solutions_all:
        if 'solve_ising_args' in solutions:
            for k,v in solutions_all['solve_ising_args'].items():
                if v != solutions['solve_ising_args'][k]:
                    del solutions_all['solve_ising_args'][k]
        else:
            del solutions_all['dw_parameters']

    if 'metadata' in solutions_all:
        if 'metadata' in solutions:
            for k,v in solutions_all['metadata'].items():
                if v != solutions['metadata'][k]:
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
            solution_lookup[sol] = solution

    new_solutions = [sol for sol in solution_lookup.values()]
    max_num_occurrences = max(sol['num_occurrences'] for sol in new_solutions)
    new_solutions.sort(key=lambda x: x['energy']*max_num_occurrences - x['num_occurrences'])

    solutions['solutions'] = new_solutions
    print_err('  reduced solutions: {}'.format(len(solutions['solutions'])))


def build_cli_parser():
    parser = argparse.ArgumentParser()

    #parser.add_argument('-f', '--input-file', help='the data file to operate on (.json)')

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(load_config(parser.parse_args()))