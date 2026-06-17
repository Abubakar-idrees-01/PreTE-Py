import argparse
import os
import sys

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prete_py.interface import next_run
from prete_py.simulator import run_simulation, abstract_optical_layer
from prete_py.environment import get_failure_scenarios

print("Imports successful")


def parse_args():
    parser = argparse.ArgumentParser(description="PreTE-Py command line runner")
    parser.add_argument("--traffic", type=int, default=1)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--topology", "-t", type=str, required=True)
    parser.add_argument("--topoindex", "-i", type=int, default=1)
    parser.add_argument("--te", "-a", type=str, default="ARROW")
    parser.add_argument("--parallel", "-p", type=str, default="./parallel")
    parser.add_argument("--cutoff", "-c", type=float, default=0.001)
    parser.add_argument("--tunnel", "-n", type=int, default=2)
    parser.add_argument("--scenarioID", "-o", type=int, default=1)
    parser.add_argument("--ticketsnum", "-k", type=int, default=3)
    parser.add_argument("--largeticketsnum", "-j", type=int, default=10)
    parser.add_argument("--abstractoptical", "-b", type=int, default=0)
    parser.add_argument("--teavarbeta", "-x", type=float, default=0.95)
    parser.add_argument("--tunneltype", "-u", type=int, default=3)
    parser.add_argument("--missing", "-m", action="store_true")
    parser.add_argument("--simulation", "-l", action="store_true")
    parser.add_argument("--failurefree", "-f", action="store_true")
    parser.add_argument("--expandspectrum", "-e", type=int, default=0)
    parser.add_argument("--scenariogeneration", "-r", type=int, default=-1)
    parser.add_argument("--newtunnelnum", type=int, default=0)
    parser.add_argument("--maxnewtunnelnum", type=int, default=0)
    parser.add_argument("--train_prob", type=float, default=0.0)
    parser.add_argument("--test_prob", type=float, default=0.0)
    parser.add_argument("--maxflows", type=int, default=5,
                        help="maximum number of flows to process for faster simulation")
    parser.add_argument("--filter", action="store_true", dest="filter_option")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main():
    print("PreTE-Py simulation starting...")
    args = parse_args()
    output_dir = os.path.abspath("./data/experiment/exp")
    run_dir = next_run(output_dir, singleplot=False)
    data_root = os.path.abspath("../data/topology")

    if args.abstractoptical > 0:
        IPTopo, OpticalTopo, IPScenarios, OpticalScenarios = get_failure_scenarios(
            data_root,
            args.topology,
            args.topoindex,
            args.verbose,
            args.cutoff,
            args.scenarioID,
            args.abstractoptical,
            args.failurefree,
            args.expandspectrum,
            args.train_prob,
            args.test_prob,
        )
        if args.scenariogeneration >= 0:
            abstract_optical_layer(
                args.topology,
                args.topoindex,
                IPTopo,
                OpticalTopo,
                IPScenarios,
                OpticalScenarios,
                args.scenariogeneration,
                run_dir,
                args.ticketsnum,
                args.largeticketsnum,
                args.tunneltype,
                args.teavarbeta,
                args.verbose,
            )
        print(f"Abstract optical preparation complete for {args.topology}\n")
    else:
        print("Starting traffic engineering simulation...")
        run_simulation(
            data_root,
            args.topology,
            args.topoindex,
            args.traffic,
            args.scale,
            args.te,
            args.parallel,
            args.cutoff,
            args.tunnel,
            args.scenarioID,
            args.ticketsnum,
            args.largeticketsnum,
            args.teavarbeta,
            args.tunneltype,
            args.simulation,
            args.failurefree,
            args.expandspectrum,
            args.filter_option,
            args.train_prob,
            args.test_prob,
            args.maxflows,
            args.verbose,
        )


if __name__ == "__main__":
    main()
