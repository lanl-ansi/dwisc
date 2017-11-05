#!/usr/bin/env python2

from __future__ import print_function

import os, sys, argparse, json, datetime

from dwave_sapi2.remote import RemoteConnection
#from dwave_sapi2.core import solve_ising
from dwave_sapi2.core import async_solve_ising, await_completion

import bqpjson

DEFAULT_CONFIG_FILE = '_config'
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')


def main(args):
    if args.input_file == None:
        data = json.load(sys.stdin)
    else:
        with open(args.input_file) as file:
            data = json.load(file)

    bqpjson.validate(data)

    if data['variable_domain'] != 'spin':
        print_err('only spin domains are supported. Given %s' % data['variable_domain'])
        quit()

    if data['scale'] != 1.0:
        print_err('A non-one scaling value is not yet supported. Given %s' % data['scale'])
        quit()

    if data['offset'] != 0.0:
        print_err('A non-zero offset value is not yet supported. Given %s' % data['offset'])
        quit()

    # A core assumption of this solver is that the given B-QP will magically be compatable with the given D-Wave QPU
    dw_url = args.dw_url
    dw_token = args.dw_token
    dw_solver_name = args.dw_solver_name
    dw_chip_id = None

    if 'dw_url' in data['metadata']:
        dw_url = data['metadata']['dw_url'].encode('ascii','ignore')
        print_err('using d-wave url provided in data file: %s' % dw_url)

    if 'dw_solver_name' in data['metadata']:
        dw_solver_name = data['metadata']['dw_solver_name'].encode('ascii','ignore')
        print_err('using d-wave solver name provided in data file: %s' % dw_solver_name)

    if 'dw_chip_id' in data['metadata']:
        dw_chip_id = data['metadata']['dw_chip_id'].encode('ascii','ignore')
        print_err('found d-wave chip id in data file: %s' % dw_chip_id)

    if dw_url is None or dw_token is None or dw_solver_name is None:
        print_err('d-wave solver parameters not found')
        quit()

    if args.dw_proxy is None: 
        remote_connection = RemoteConnection(dw_url, dw_token)
    else:
        remote_connection = RemoteConnection(dw_url, dw_token, args.dw_proxy)

    solver = remote_connection.get_solver(dw_solver_name)
    if not dw_chip_id is None:
        if solver.properties['chip_id'] != dw_chip_id:
            print_err('WARNING: chip ids do not match.  data: %s  hardware: %s' % (dw_chip_id, solver.properties['chip_id']))

    solution_metadata = {
        'dw_url': dw_url,
        'dw_solver_name': dw_solver_name,
        'dw_chip_id': solver.properties['chip_id'],
    }

    #couplers = solver.properties['couplers']
    #sites = solver.properties['qubits']

    #site_range = tuple(solver.properties['h_range'])
    #coupler_range = tuple(solver.properties['j_range'])

    h = [0]*(max(data['variable_ids'])+1)
    for lt in data['linear_terms']:
        i = lt['id']
        assert(i < len(h))
        h[i] = lt['coeff']

    J = {}
    for qt in data['quadratic_terms']:
        i = qt['id_tail']
        j = qt['id_head']
        assert(not (i,j) in J)
        J[(i,j)] = qt['coeff']

    params = {
        'auto_scale': False,
        'annealing_time': args.annealing_time,
        'num_reads': args.solve_num_reads
    }

    if args.spin_reversal_transform_rate != None:
        params['num_spin_reversal_transforms'] = args.solve_num_reads/args.spin_reversal_transform_rate

    print_err('')
    print_err('total num reads: {}'.format(args.num_reads))
    print_err('d-wave parameters:')
    for k,v in params.items():
        print_err('  {} - {}'.format(k,v))

    print_err('')
    print_err('starting collection:')
    submitted_problems = []
    num_reads_remaining = args.num_reads
    while num_reads_remaining > 0:
        num_reads = min(args.solve_num_reads, num_reads_remaining)
        params['num_reads'] = num_reads

        print_err('  submit {} of {} remaining'.format(num_reads, num_reads_remaining))
        submitted_problems.append({
            'problem': async_solve_ising(solver, h, J, **params),
            'start_time': datetime.datetime.utcnow(),
            'params': {k:v for k,v in params.items()}
            })
        num_reads_remaining -= num_reads

    #answers = solve_ising(solver, h, J, **params)
    print_err('  waiting...')

    solutions_all = None
    for i, submitted_problem in enumerate(submitted_problems):
        problem = submitted_problem['problem']
        await_completion([problem], 1, float('inf'))
        print_err('  collect {} of {} solves'.format(i+1, len(submitted_problems)))
        answers = problem.result()

        solutions = answers_to_solutions(
            answers,
            data['variable_ids'],
            submitted_problem['start_time'],
            datetime.datetime.utcnow(),
            submitted_problem['params'],
            solution_metadata
        )
        if solutions_all != None:
            combine_solution_data(solutions_all, solutions)
        else:
            solutions_all = solutions

    merge_solution_counts(solutions_all)

    print_err('')
    #print(solutions_all)
    total_collected = sum(solution['num_occurrences'] for solution in solutions_all['solutions'])
    print_err('total collected: {}'.format(total_collected))
    for i, solution in enumerate(solutions_all['solutions']):
        print_err('  %f - %d' % (solution['energy'], solution['num_occurrences']))
        if i >= 50:
            print_err('  first 50 of {} solutions'.format(len(solutions_all['solutions'])))
            break
    assert(total_collected == args.num_reads)

    #print('BQP_DATA, %d, %d, %f, %f, %f, %f, %f, %d, %d' % (nodes, edges, scaled_objective, scaled_lower_bound, best_objective, lower_bound, best_runtime, 0, best_nodes))
    print_err('')
    solutions_all['collection_start'] = solutions_all['collection_start'].strftime(TIME_FORMAT)
    solutions_all['collection_end'] = solutions_all['collection_end'].strftime(TIME_FORMAT)
    print(json.dumps(solutions_all))


def answers_to_solutions(answers, variable_ids, start_time, end_time, solve_ising_args=None, metadata=None):
    solutions = []
    for i, solution in enumerate(answers['solutions']):
        solutions.append({
            'energy': answers['energies'][i],
            'num_occurrences': answers['num_occurrences'][i],
            'solution': [solution[i] for i in variable_ids]
        })

    solution_data = {
        'timing':answers['timing'],
        'variable_ids':variable_ids,
        'solutions':solutions
    }

    solution_data['collection_start'] = start_time
    solution_data['collection_end'] = end_time

    if solve_ising_args != None:
        solution_data['solve_ising_args'] = solve_ising_args

    if metadata != None:
        solution_data['metadata'] = metadata

    return solution_data


addative_times = [ 'total_real_time', 'post_processing_overhead_time',
    'qpu_sampling_time', 'total_post_processing_time', 'qpu_programming_time',
    'run_time_chip', 'qpu_access_time'
]

constant_times = [ 'anneal_time_per_run', 'readout_time_per_run',
    'qpu_readout_time_per_sample', 'qpu_delay_time_per_sample',
    'qpu_anneal_time_per_sample'
]

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


# loads a configuration file and sets up undefined CLI arguments
def load_config(args):
    config_file_path = args.config_file

    if os.path.isfile(config_file_path):
        with open(config_file_path, 'r') as config_file:
            try:
                config_data = json.load(config_file)
                for key, value in config_data.items():
                    if isinstance(value, dict) or isinstance(value, list):
                        print_err('invalid value for configuration key "%s", only single values are allowed' % config_file_path)
                        quit()
                    if not hasattr(args, key) or getattr(args, key) == None:
                        if isinstance(value, unicode):
                            value = value.encode('ascii','ignore')
                        setattr(args, key, value)
                    else:
                        print_err('skipping the configuration key "%s", it already has a value of %s' % (key, str(getattr(args, key))))
            except ValueError:
                print_err('the config file does not appear to be a valid json document: %s' % config_file_path)
                quit()
    else:
        if config_file_path != DEFAULT_CONFIG_FILE:
            print_err('unable to open conifguration file: %s' % config_file_path)
            quit()

    return args

# D-Wave Ising Sample Collector
def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('-f', '--input-file', help='the data file to operate on (.json)')
    #parser.add_argument('-o', '--output-file', help='the data file to operate on (.json)')

    parser.add_argument('-cf', '--config-file', help='a configuration file for specifying common parameters', default=DEFAULT_CONFIG_FILE)

    parser.add_argument('-url', '--dw-url', help='url of the d-wave machine')
    parser.add_argument('-token', '--dw-token', help='token for accessing the d-wave machine')
    parser.add_argument('-proxy', '--dw-proxy', help='proxy for accessing the d-wave machine')
    parser.add_argument('-solver', '--dw-solver-name', help='d-wave solver to use', type=int)

    parser.add_argument('-snr', '--solve-num-reads', help='the number of reads to request in each solve_ising call', type=int, default=10000)

    parser.add_argument('-nr', '--num-reads', help='the total number of reads to take', type=int, default=25000)
    parser.add_argument('-at', '--annealing-time', help='the annealing time of each d-wave sample', type=int, default=5)
    parser.add_argument('-srtr', '--spin-reversal-transform-rate', help='the number of reads to take before each spin reversal transform', type=int)

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(load_config(parser.parse_args()))
