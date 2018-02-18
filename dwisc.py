#!/usr/bin/env python2

from __future__ import print_function

import os, sys, argparse, json, datetime

import dwave_micro_client

import bqpjson

import combis

json_dumps_kwargs = {
    'sort_keys':True,
    'indent':2,
    'separators':(',', ': ')
}

# prints a line to standard error
def print_err(data):
    sys.stderr.write(str(data)+'\n')


def check_diff(a,b):
    if a != b:
        print_err('values differ: {} - {}'.format(a, b))
        quit()


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

    # A core assumption of this solver is that the given bqpjson data will magically be compatable with the given D-Wave QPU

    dw_url = None
    dw_tokens = []
    dw_proxy_url = None
    dw_solver_name = None

    if args.connection_labels != None:
        for connection_label in args.connection_labels:
            url, token, proxy_url, solver_name = dwave_micro_client.load_configuration(connection_label)
            if dw_url == None:
                dw_url = url
            else:
                check_diff(dw_url, url)

            if dw_proxy_url == None:
                dw_proxy_url = proxy_url
            else:
                check_diff(dw_proxy_url, proxy_url)

            if dw_solver_name == None:
                dw_solver_name = solver_name
            else:
                check_diff(dw_solver_name, solver_name)

            dw_tokens.append(token)
    else:
        if args.connection_label != None:
            url, token, proxy_url, solver_name = dwave_micro_client.load_configuration(args.connection_label)
        else:
            url, token, proxy_url, solver_name = dwave_micro_client.load_configuration()
        dw_url, dw_proxy_url, dw_solver_name = url, proxy_url, solver_name
        dw_tokens.append(token)


    if 'dw_url' in data['metadata']:
        dw_url = data['metadata']['dw_url'].encode('ascii','ignore')
        print_err('using d-wave url provided in data file: %s' % dw_url)

    if 'dw_solver_name' in data['metadata']:
        dw_solver_name = data['metadata']['dw_solver_name'].encode('ascii','ignore')
        print_err('using d-wave solver name provided in data file: %s' % dw_solver_name)

    if 'dw_chip_id' in data['metadata']:
        dw_chip_id = data['metadata']['dw_chip_id'].encode('ascii','ignore')
        print_err('found d-wave chip id in data file: %s' % dw_chip_id)


    if dw_url is None or len(dw_tokens) <= 0 or dw_solver_name is None:
        print_err('d-wave solver parameters not found')
        quit()


    connections = []
    for dw_token in dw_tokens:
        if dw_proxy_url is None:
            connections.append(dwave_micro_client.Connection(dw_url, dw_token, permissive_ssl=True))
        else:
            connections.append(dwave_micro_client.Connection(dw_url, dw_token, dw_proxy_url, permissive_ssl=True))

    solvers = [conn.get_solver(dw_solver_name) for conn in connections]

    if not dw_chip_id is None:
        if solvers[0].properties['chip_id'] != dw_chip_id:
            print_err('WARNING: chip ids do not match.  data: %s  hardware: %s' % (dw_chip_id, solvers[0].properties['chip_id']))

    solution_metadata = {
        'dw_url': dw_url,
        'dw_solver_name': dw_solver_name,
        'dw_chip_id': solvers[0].properties['chip_id'],
    }

    h = {}
    for lt in data['linear_terms']:
        h[lt['id']] = lt['coeff']

    J = {}
    for qt in data['quadratic_terms']:
        i = qt['id_tail']
        j = qt['id_head']
        assert(not (i,j) in J)
        J[(i,j)] = qt['coeff']

    print_err('')
    print_err('check problem:')
    for solver in solvers:
        check = solver.check_problem(h, J)
        print_err('  {} - {}'.format(solver.id, check))

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

    return
    print_err('')
    print_err('starting collection:')
    submitted_problems = []
    num_reads_remaining = args.num_reads
    problem_index = 0
    while num_reads_remaining > 0:
        num_reads = min(args.solve_num_reads, num_reads_remaining)
        params['num_reads'] = num_reads

        print_err('  submit {} of {} remaining'.format(num_reads, num_reads_remaining))

        solver_index = problem_index % len(solvers)
        submitted_problems.append({
            'problem': solvers[solver_index].sample_ising(h, J, **params),
            'start_time': datetime.datetime.utcnow(),
            'params': {k:v for k,v in params.items()}
            })
        num_reads_remaining -= num_reads
        problem_index += 1

    #answers = solve_ising(solver, h, J, **params)
    print_err('  waiting...')

    solutions_all = None
    for i, submitted_problem in enumerate(submitted_problems):
        problem = submitted_problem['problem']
        problem.wait()
        print_err('  collect {} of {} solves'.format(i+1, len(submitted_problems)))

        solutions = answers_to_solutions(
            problem,
            data['variable_ids'],
            submitted_problem['start_time'],
            datetime.datetime.utcnow(),
            submitted_problem['params'],
            solution_metadata
        )
        if solutions_all != None:
            combis.combine_solution_data(solutions_all, solutions)
        else:
            solutions_all = solutions

    combis.merge_solution_counts(solutions_all)

    print_err('')
    total_collected = sum(solution['occurrences'] for solution in solutions_all['solutions'])
    print_err('total collected: {}'.format(total_collected))
    for i, solution in enumerate(solutions_all['solutions']):
        print_err('  %f - %d' % (solution['energy'], solution['occurrences']))
        if i >= 50:
            print_err('  first 50 of {} solutions'.format(len(solutions_all['solutions'])))
            break
    assert(total_collected == args.num_reads)

    print_err('')
    solutions_all['collection_start'] = solutions_all['collection_start'].strftime(combis.TIME_FORMAT)
    solutions_all['collection_end'] = solutions_all['collection_end'].strftime(combis.TIME_FORMAT)

    if args.pretty_print:
        print(json.dumps(solutions_all, **json_dumps_kwargs))
    else:
        print(json.dumps(solutions_all))


def answers_to_solutions(problem, variable_ids, start_time, end_time, solve_ising_args=None, metadata=None):
    solutions = []
    for i, sample in enumerate(problem.samples):
        solutions.append({
            'energy': problem.energies[i],
            'occurrences': problem.occurrences[i],
            'solution': [sample[i] for i in variable_ids]
        })

    solution_data = {
        'timing':problem.timing,
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


def build_cli_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('-cl', '--connection-label', help='connection details to load from .dwrc', default=None)
    parser.add_argument('-cls', '--connection-labels', help='connection details to load from .dwrc', default=None)

    parser.add_argument('-f', '--input-file', help='the data file to operate on (.json)')
    #parser.add_argument('-o', '--output-file', help='the data file to operate on (.json)')

    parser.add_argument('-pp', '--pretty-print', help='pretty print json output', action='store_true', default=False)

    parser.add_argument('-snr', '--solve-num-reads', help='the number of reads to request in each solve_ising call', type=int, default=10000)

    parser.add_argument('-nr', '--num-reads', help='the total number of reads to take', type=int, default=25000)
    parser.add_argument('-at', '--annealing-time', help='the annealing time of each d-wave sample', type=int, default=5)
    parser.add_argument('-srtr', '--spin-reversal-transform-rate', help='the number of reads to take before each spin reversal transform', type=int)

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())
