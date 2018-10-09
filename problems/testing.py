import argparse
import collections
import logging
import os
import pickle
import sys
import time
from typing import List
from matplotlib import pyplot as plt
import docker
import pandas as pd
import yaml

from docker.errors import BuildError, APIError
from docker.models.containers import Container

TestResult = collections.namedtuple("TestResult", ["time_taken", "status", "iteration",
                                                   "test_time", "system_info"],
                                    verbose = False,
                                    rename = False)


def get_args():
    DATA_PATH = "argparse.yaml"

    with open(DATA_PATH, "r") as file:
        configs = yaml.load(file)

    arg_lists = []
    parser = argparse.ArgumentParser()

    # Dynamically populate runtime arguemnts.
    for g_name, group in configs.items():
        arg = parser.add_argument_group(g_name)
        arg_lists.append(arg)

        for conf in group.keys():
            arg.add_argument("--" + str(conf), **group[conf])

    parsed, unparsed = parser.parse_known_args()

    return parsed

def _configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)s]')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def _get_tests():
    for root, dir, files in os.walk("."):
        # Don't include the root directory, and only include top-level directories.
        if root != "." and len(root.split("/")) == 2:
            yield root, files


def __get_lang(file):
    ending = file.split(".")[-1]
    if ending == "py":
        yield "python"
        yield "pypy"
    elif ending == "go":
        yield "go"


def generate_docker_file(root, files):
    for file in files:
        # Could build with multiple executables. (like pypy and python)
        for lang in __get_lang(file):
            if lang == "go":
                root_container = "golang:1.11.1-alpine"
                entry_command = "go run {0}".format(file)

            elif lang == "pypy":
                root_container = "pypy:3-6.0.0-slim-jessie"
                entry_command = "pypy3 {0}".format(file)

            elif lang == "python":
                root_container = "python:3.6.6-slim-jessie"
                entry_command = "python3 {0}".format(file)

            else:
                logging.warning("Unknown language: " + lang)
                continue

            test_container = "golang:1.11.1-alpine"
            test_file = "baseline.go"
            test_command = "./app"

            requirements = ""
            if files.__contains__("requirements.txt"):
                requirements = os.path.join(root, "requirements.txt")

            if not os.path.exists("images"):
                os.mkdir("images")

            dockerfile_contents = [
                "FROM {0} as test_builder".format(test_container),
                "ADD ./{0} /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores/{0}".format(test_file),
                "WORKDIR /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores",
                "RUN go install /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores",
                "RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -tags netgo -installsuffix netgo -o app .",
                "",
                "FROM {0}".format(root_container),
                # "ENTRYPOINT ['/bin/bash']"
            ]

            if lang == "go":
                dockerfile_contents.append("WORKDIR /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores")
                dockerfile_contents.append("COPY --from=test_builder /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores/app ./app")
                dockerfile_contents.append("ADD {0} ./{1}".format(os.path.join(root, file), file))

                dockerfile_contents.append("RUN apk add git")
                dockerfile_contents.append("RUN go get .")
                dockerfile_contents.append("RUN go build -i {0}".format(file))
                # entry_command = "./{0}".format(file.split(".")[0])
            else:
                # Most of them can just write to /app, except golang.
                dockerfile_contents.append("WORKDIR /app")
                dockerfile_contents.append(
                    "COPY --from=test_builder /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores/app ./app")
                dockerfile_contents.append("ADD {0} /app/{1}".format(os.path.join(root, file), file))

            if requirements != "" and lang in ["pypy", "python"]:
                dockerfile_contents.append("ADD {0} /app/requirements.txt".format(requirements))
                dockerfile_contents.append("RUN pip3 install -r requirements.txt")

            output_dockerfile_name = "Dockerfile_{0}_{1}".format(root.strip("./"), lang)

            with open("images/" + output_dockerfile_name, "w+") as output_dockerfile:
                output_dockerfile.write("\n".join(dockerfile_contents))
            yield "images/" + output_dockerfile_name, test_command, entry_command, file


def determine_auto_skip(configs):
    # We have a cache.
    should_cache = False
    if os.path.exists("cache.pkl"):
        with open("cache.pkl", "rb") as f:
            cache = pickle.load(f)
        should_cache = cache == configs

    with open("cache.pkl", "wb") as f:
        pickle.dump(configs, f)
    return should_cache

def avg(lst):
    return sum(lst) / len(list(lst))


if __name__ == "__main__":
    _configure_logging()
    configs = get_args()


    # Only skip tests if the configs haven't changed from last time.
    SIZE_OF_SAMPLE = configs.sample_size
    AUTO_SKIP = determine_auto_skip(configs) if configs.auto_skip else False

    logging.info("Getting docker client")
    client = docker.client.from_env()

    all_test_data = []

    logging.info("Finding tests.")
    for test, files in _get_tests():
        logging.info("Found test: {0}".format(test))
        for dockerfile, test_command, entry_command, file in generate_docker_file(test, files):
            if entry_command.startswith("./"):
                test_file = (file.split(" ")[-1]).split(".")[0]  # Get the filename
            else:
                test_file = (entry_command.split(" ")[-1]).split(".")[0]

            first_run_csv = "results/tables/{0}.csv".format(
                test[2:] + "_first_" + entry_command.split(" ")[0] + "_" + test_file)
            overall_run_csv = "results/tables/{0}.csv".format(
                test[2:] + "_" + entry_command.split(" ")[0] + "_" + test_file)

            if AUTO_SKIP and os.path.exists(first_run_csv) and os.path.exists(overall_run_csv):
                logging.info("Test already run.  Skipping. (FROM AUTO_SKIP")
                continue

            docker_image = None

            docker_image_name = "mattpaletta/csc_464_a1_{0}_{1}:latest".format(
                    dockerfile[len("images/Dockerfile_"):].lower(),
                    test_file
            )

            try:
                logging.info("Building test image: {0}".format(docker_image_name))

                docker_image, build_logs = client.images.build(path = ".",
                                                               dockerfile = "./" + dockerfile,
                                                               tag = docker_image_name)

                logging.info("Built image: {0}".format(docker_image_name))
            except BuildError as e:
                print(e)
                continue
            except APIError as e:
                print(e)
                exit(1)

            logging.info("Running test: {0} with samples: {1}".format(docker_image_name, SIZE_OF_SAMPLE))

            test_results = []
            current_test = 1
            while current_test <= SIZE_OF_SAMPLE:
                container_settings = {
                    # "cpu_period": 1000,
                    # "cpu_quota": 1000,
                    # "cpuset_cpus": "0",
                    "stdout": True,
                    "stderr": True,
                    "detach": True,
                    "tty": True
                }

                logging.info("Starting Test: {0}/{1}".format(current_test, SIZE_OF_SAMPLE))

                logging.info("Running standard benchmark")
                # MARK:// Run the 'before benchmark'
                before_container: Container = client.containers.run(image = docker_image_name,
                                                                    command = 'sh -c "{0}"'.format(test_command),
                                                                    **container_settings)
                start = time.time()
                before_code = before_container.wait()["StatusCode"]
                end = time.time()
                before_benchmark = end - start
                before_container.remove()
                if before_code != 0:
                    logging.warning("Benchmark failed.  Retrying after timeout.")
                    time.sleep(10)
                    continue


                # MARK:// Run the 'after benchmark'
                logging.info("Running test")
                test_container: Container = client.containers.run(image = docker_image_name,
                                                                  command = 'sh -c "{0}"'.format(entry_command),
                                                                  **container_settings)
                start = time.time()
                stats = test_container.stats(decode=True)
                processed_stats = []
                for s in stats:
                    cpu_usage = s["cpu_stats"]["cpu_usage"]["total_usage"]
                    if cpu_usage == 0 and len(s["memory_stats"].keys()) == 0:
                        break
                    processed_stats.append(s)

                test_exit_code = test_container.wait()["StatusCode"]
                end = time.time()



                test_time = end - start
                logging.info("Test: {0}/{1} {2}".format(current_test, SIZE_OF_SAMPLE, "passed" if test_exit_code == 0 else "FAILED"))

                if test_exit_code != 0:
                    print(test_container.logs())

                test_container.remove()


                # MARK:// Run the 'after benchmark'
                logging.info("Running standard benchmark")
                after_container: Container = client.containers.run(image = docker_image_name,
                                                                   command = 'sh -c "{0}"'.format(test_command),
                                                                   **container_settings)
                start = time.time()
                after_code = after_container.wait()["StatusCode"]
                end = time.time()
                after_benchmark = end - start
                after_container.remove()
                if after_code != 0:
                    logging.warning("Benchmark failed.  Retrying after timeout.")
                    time.sleep(10)
                    continue

                change_percent = ((float(after_benchmark) - before_benchmark) / before_benchmark) * 100

                if change_percent >= 5.0:
                    logging.info("System seems to have changed by: {0}%. Retrying test after timeout.".format(round(change_percent, 4)))
                    time.sleep(10)
                    continue

                logging.info("Saving results")
                test_results.append(TestResult(time_taken = test_time,
                                               test_time = avg([before_benchmark, after_benchmark]),
                                               iteration = current_test-1,
                                               status = test_exit_code,
                                               system_info = processed_stats))
                current_test += 1

            logging.info("Processing {0} results".format(len(test_results)))
            # Process all results from that test.
            if not os.path.exists("results"):
                os.mkdir("results")


            # Plot CPU usage (just from 1 run)
            # Plot memory usage
            usage_df = []

            logging.info("Processing first run info")
            first_run = test_results[0]
            # Observe the entire run.
            for stats in first_run.system_info:
                date_recorded = stats["read"]

                total_cpu_usage: int = stats["cpu_stats"]["cpu_usage"]["total_usage"]
                user_cpu_usage: int = stats["cpu_stats"]["cpu_usage"]["usage_in_kernelmode"]
                kernel_cpu_usage: int = stats["cpu_stats"]["cpu_usage"]["usage_in_usermode"]
                per_cpu_usage: List[int] = stats["cpu_stats"]["cpu_usage"]["percpu_usage"]

                avg_memory_usage = stats["memory_stats"]["usage"]
                max_memory_usage = stats["memory_stats"]["max_usage"]
                memory_cache = stats["memory_stats"]["stats"]["cache"]

                stat_data = {"time_recorded": date_recorded,
                                 "total_cpu_usage": total_cpu_usage,
                                 "user_cpu_usage": user_cpu_usage,
                                 "kernel_cpu_usage": kernel_cpu_usage,
                                 "avg_per_usage": avg(per_cpu_usage),
                                 "avg_memory_usage": avg_memory_usage,
                                 "max_memory_usage": max_memory_usage,
                                 "memory_cache": memory_cache
                                 }
                usage_df.append(stat_data)

            if not os.path.exists("results/tables"):
                os.mkdir("results/tables")

            logging.info("Writing first run info")
            pd.DataFrame(usage_df).to_csv(first_run_csv)

            # For the table
            # Test Name and executor run
            # Get max CPU usage (per core)
            # Get avg CPU usage (across cores)
            # Get max memory usage

            logging.info("Processing overall run data")
            general_df = []

            for result in test_results:
                iteration = result.iteration
                time_taken = result.time_taken
                test_time = result.test_time
                stats = result.system_info

                # Test_time is the average test time
                normalized_test_time = (1 / test_time) * time_taken

                cpu_usage_list = list(map(lambda stat: stat["cpu_stats"]["cpu_usage"]["total_usage"], stats))
                max_cpu_usage = max(cpu_usage_list) if len(cpu_usage_list) > 0 else 0.0

                avg_memory_usage_list = list(map(lambda stat: stat["memory_stats"]["usage"], stats))
                avg_memory_usage = avg(avg_memory_usage_list) if len(avg_memory_usage_list) > 0 else 0

                max_memory_usage_list = list(map(lambda stat: stat["memory_stats"]["max_usage"], stats))
                max_memory_usage = max(max_memory_usage_list) if len(max_memory_usage_list) > 0 else 0

                stat_data = {
                                    "iteration"   : iteration,
                                    "max_cpu_usage" : max_cpu_usage,
                                    "avg_memory_usage"  : avg_memory_usage,
                                    "max_memory_usage": max_memory_usage,
                                    "time_taken": time_taken,
                                    "test_time": test_time,
                                    "normalized_test": normalized_test_time
                                 }

                general_df.append(stat_data)

            logging.info("Writing overall run data")
            pd.DataFrame(general_df).to_csv(overall_run_csv)

    logging.info("Plotting test results.")
    for test, files in _get_tests():
        logging.info("Found test: {0}".format(test))
        for dockerfile, test_command, entry_command, file in generate_docker_file(test, files):
            if entry_command.startswith("./"):
                test_file = (file.split(" ")[-1]).split(".")[0]  # Get the filename
            else:
                test_file = (entry_command.split(" ")[-1]).split(".")[0]

            first_run_csv = "results/tables/{0}.csv".format(
                test[2:] + "_first_" + entry_command.split(" ")[0] + "_" + test_file)
            overall_run_csv = "results/tables/{0}.csv".format(
                test[2:] + "_" + entry_command.split(" ")[0] + "_" + test_file)

            if not os.path.exists("results/figures"):
                os.mkdir("results/figures")

            if not os.path.exists("results/figures/first"):
                os.mkdir("results/figures/first")

            if not os.path.exists("results/figures/overall"):
                os.mkdir("results/figures/overall")

            if not os.path.exists(first_run_csv):
                logging.warning("First run CSV not found.")
            else:
                df = pd.read_csv(first_run_csv, index_col = 0)
                if len(df) == 0:
                    logging.warning("Found empty dataframe")
                    continue

                # TODO:// Calculate CPU usage percentage.
                # cpuDelta = res.cpu_stats.cpu_usage.total_usage - res.precpu_stats.cpu_usage.total_usage
                # systemDelta = res.cpu_stats.system_cpu_usage - res.precpu_stats.system_cpu_usage
                # RESULT_CPU_USAGE = cpuDelta / systemDelta * 100


                time_recorded = df["time_recorded"]
                for column in df.columns:
                    if column == "time_recorded":
                        continue

                    plot_output = "results/figures/first/" + test[2:] + "_first_" + entry_command.split(" ")[0] + "_" + test_file + "_" + column + ".png"

                    if os.path.exists(plot_output):
                        os.remove(plot_output)

                    plt.plot(df.index, df[column])
                    plt.xlabel('sample')
                    plt.ylabel(column)
                    plt.title(test[2:] + "_first_" + entry_command.split(" ")[0] + "_" + test_file + "_" + column)
                    plt.grid(True)
                    plt.savefig(plot_output)
                    # plt.show()
                    plt.close()

            if not os.path.exists(overall_run_csv):
                logging.warning("First run CSV not found.")
            else:
                df = pd.read_csv(overall_run_csv, index_col = 0)
                if len(df) == 0:
                    logging.warning("Found empty dataframe")
                    continue

                time_recorded = df["iteration"]
                for column in df.columns:
                    if column == "iteration":
                        continue

                    plot_output = "results/figures/overall/" + test[2:] + "_samples_" + entry_command.split(" ")[
                        0] + "_" + test_file + "_" + column + ".png"

                    if os.path.exists(plot_output):
                        os.remove(plot_output)

                    plt.plot(df.index, df[column])
                    plt.xlabel('iteration')
                    plt.ylabel(column)
                    plt.title(test[2:] + "_samples_" + entry_command.split(" ")[0] + "_" + test_file + "_" + column)
                    plt.grid(True)
                    plt.savefig(plot_output)
                    # plt.show()
                    plt.close()

