import collections
import logging
import os
import sys
import time

import docker
import matplotlib.pyplot as plt

from docker.errors import BuildError, APIError
from docker.models.containers import Container

TestResult = collections.namedtuple("TestResult", ["time_taken", "status", "iteration"],
                                    verbose = False,
                                    rename = False)

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
        return "python"
    elif ending == "go":
        return "go"



def generate_docker_file(root, files):
    for file in files:
        lang = __get_lang(file)
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
            "WORKDIR /app",
            "COPY --from=test_builder /go/src/github.com/mattpaletta/Little-Book-Of-Semaphores/app ./app",
            "ADD {0} /app/{1}".format(os.path.join(root, file), file),
            "" if requirements == "" else "ADD {0} /app/requirements.txt".format(requirements),
            "" if requirements == "" else "RUN pip3 install -r requirements.txt",
            # "ENTRYPOINT ['/bin/bash']"
        ]
        output_dockerfile_name = "Dockerfile_{0}_{1}".format(root.strip("./"), lang)

        with open("images/" + output_dockerfile_name, "w+") as output_dockerfile:
            output_dockerfile.write("\n".join(dockerfile_contents))
        yield "images/" + output_dockerfile_name, test_command, entry_command


if __name__ == "__main__":
    _configure_logging()

    SIZE_OF_SAMPLE = 2

    logging.info("Getting docker client")
    client = docker.client.from_env()

    all_test_data = []

    logging.info("Finding tests.")
    for test, files in _get_tests():
        logging.info("Found test: {0}".format(test))
        for dockerfile, test_command, entry_command in generate_docker_file(test, files):
            docker_image = None

            docker_image_name = "mattpaletta/csc_464_a1_" + dockerfile[len("images/Dockerfile_"):].lower() + ":latest"
            try:
                logging.info("Building test image: {0}".format(docker_image_name))

                docker_image, build_logs = client.images.build(path = ".",
                                                               dockerfile = "./" + dockerfile,
                                                               container_limits= {
                    "cpushares": 10,
                    "cpusetcpus": "1"  # force to only execute on CPU 1
                }, tag = docker_image_name)

                logging.info("Built image: {0}".format(docker_image_name))
                # print(list(build_logs))
            except BuildError as e:
                print(e)
                exit(1)
            except APIError as e:
                print(e)
                exit(1)

            logging.info("Running test: {0} with samples: {1}".format(docker_image_name, SIZE_OF_SAMPLE))

            test_results = []
            current_test = 1
            while current_test <= SIZE_OF_SAMPLE:
                logging.info("Starting Test: {0}/{1}".format(current_test, SIZE_OF_SAMPLE))

                logging.info("Running standard benchmark")
                # MARK:// Run the 'before benchmark'
                before_container: Container = client.containers.run(image = docker_image_name,
                                      command = 'sh -c "{0}"'.format(test_command),
                                      stdout = True,
                                      stderr = True,
                                      tty = True,
                                      detach = True)
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
                                                                    stdout = True,
                                                                    stderr = True,
                                                                    tty = True,
                                                                    detach = True)
                start = time.time()
                stats = test_container.stats()
                test_exit_code = test_container.wait()["StatusCode"]
                end = time.time()
                print(list(stats))
                test_time = end - start
                logging.info("Test: {0}/{1} {2}".format(current_test, SIZE_OF_SAMPLE, "passed" if test_exit_code == 0 else "FAILED"))

                if test_exit_code != 0:
                    print(test_container.logs())

                test_container.remove()


                # MARK:// Run the 'after benchmark'
                logging.info("Running standard benchmark")
                after_container: Container = client.containers.run(image = docker_image_name,
                                                                    command = 'sh -c "{0}"'.format(test_command),
                                                                    stdout = True,
                                                                    stderr = True,
                                                                    tty = True,
                                                                    detach = True)
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
                    logging.info("System seems to have changed by: {0}. Retrying test after timeout.".format(change_percent))
                    time.sleep(10)
                    continue

                logging.info("Saving results")
                test_results.append(TestResult(time_taken = test_time,
                                               iteration = current_test-1,
                                               status = test_exit_code))
                current_test += 1
            exit(0)