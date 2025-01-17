# Copyright 2023 Graphcore Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os

from byte_mlperf.backends import runtime_backend

from . import engine_poprt

log = logging.getLogger("RuntimeBackendIPU")


class RuntimeBackendIPU(runtime_backend.RuntimeBackend):
    def __init__(self):
        super(RuntimeBackendIPU, self).__init__()
        self.hardware_type = "IPU"
        self.need_reload = False
        self.model_runtimes = []
        self.configs = None
        self.batch_size = -1
        self.engine = None
        self.runner_name = "POPRT"
        self.compiled_dir = (
            os.path.split(os.path.abspath(__file__))[0] + "/compiled_models"
        )

    def predict(self, feeds, test_benchmark=False):
        results = self.engine.predict(feeds)
        return results

    def _get_engine(self, batch_size):
        if not self.batch_size == batch_size:
            self.batch_size = batch_size

            interact_info = self.configs.get("interact_info", {})
            runtime_options = interact_info.get("runtime_options", {})

            if self.runner_name == "POPRT":
                self.engine = engine_poprt.PopRT(self.popef_path, runtime_options)
            else:
                raise ValueError("engine_name must be POPRT")
        return self.engine

    def benchmark(self, dataloader):
        report = {}
        report["BS"] = self.batch_size
        interact_info = self.configs.get("interact_info", {})
        if interact_info.get("pack", False):
            # load performance report from acc test for models used pack feature
            perf_path = "byte_mlperf/reports/IPU/{0}/performance_bs{1}.json".format(
                self.model_info["model"], self.batch_size
            )
            assert os.path.exists(perf_path)
            with open(perf_path, "r") as f:
                perf = json.load(f)
                report["QPS"] = perf["QPS"]
                report["AVG Latency"] = perf["AVG Latency"]
                report["P99 Latency"] = perf["P99 Latency"]

        else:
            iterations = self.workload["iterations"]
            clients = interact_info.get("clients", 1)

            qps, avg_latency, tail_latency = self.engine.benchmark(
                clients, self.batch_size, iterations
            )

            report["QPS"] = int(qps)
            report["AVG Latency"] = avg_latency
            report["P99 Latency"] = tail_latency

        return report

    def get_loaded_batch_size(self):
        # return self.workload['batch_sizes'][0]
        return self.batch_size

    def load(self, batch_size) -> None:
        self.popef_path = os.path.join(
            self.compiled_dir,
            self.configs["model"],
            str(batch_size),
            "executable.popef",
        )
        self._get_engine(batch_size)
