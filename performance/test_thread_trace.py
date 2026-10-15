import unittest
from unittest.mock import patch

from thread_trace import count_window, parse_traces


class ThreadTraceTests(unittest.TestCase):
    def parse(self, files):
        class TraceFile:
            def __init__(self, name, body):
                self.name, self.body = name, body

            def is_file(self):
                return True

            def read_text(self, **_):
                return self.body

        class TraceDirectory:
            def is_dir(self):
                return True

            def iterdir(self):
                return [TraceFile(name, body) for name, body in files.items()]

        # Keep fixtures in memory: this verifies parsing independently from
        # filesystem permissions imposed by the Windows sandbox.
        with patch("thread_trace.Path", return_value=TraceDirectory()):
            return parse_traces("synthetic")

    def test_counts_only_successful_clone_thread_births(self):
        parsed = self.parse({
            "threads.77": "\n".join([
                "1700000000.000001 clone(child_stack=NULL, flags=CLONE_VM|CLONE_THREAD|CLONE_SIGHAND) = 88 <0.000123>",
                "1700000001.000001 clone3({flags=CLONE_VM|CLONE_THREAD}, 88) = 89 <0.000004>",
                "1700000002.000001 clone(child_stack=NULL, flags=SIGCHLD) = 90 <0.000010>",
                "1700000003.000001 clone3({flags=CLONE_VM|CLONE_THREAD}, 88) = -1 ENOSYS (Function not implemented) <0.000001>",
                "1700000004.000001 clone(child_stack=NULL, flags=CLONE_VM|CLONE_THREAD) = -1 EAGAIN (Resource temporarily unavailable) <0.000001>",
            ])
        })
        self.assertTrue(parsed["validation"]["exactCountAvailable"])
        self.assertEqual([(e["parentTid"], e["childTid"], e["syscall"]) for e in parsed["events"]], [(77, 88, "clone"), (77, 89, "clone3")])
        self.assertEqual(parsed["nonThreadCounts"], {"clone": 1, "clone3": 0})
        self.assertEqual(len(parsed["failedAttempts"]), 2)
        self.assertEqual(parsed["events"][0]["returnEpochNs"] - parsed["events"][0]["entryEpochNs"], 123_000)

    def test_reconstructs_unfinished_and_resumed_call_per_tid(self):
        parsed = self.parse({
            "threads.501": "1700000100.000000 clone(child_stack=NULL, flags=CLONE_VM|CLONE_THREAD <unfinished ...>\n1700000100.005000 <... clone resumed> |CLONE_SIGHAND) = 502 <0.005000>\n",
            "threads.600": "1700000100.001000 clone(child_stack=NULL, flags=CLONE_VM|CLONE_THREAD) = 601 <0.000002>\n",
        })
        self.assertTrue(parsed["validation"]["exactCountAvailable"])
        self.assertEqual([(event["parentTid"], event["childTid"]) for event in parsed["events"]], [(501, 502), (600, 601)])
        resumed = parsed["events"][0]
        self.assertEqual(resumed["entryEpochNs"], 1_700_000_100_000_000_000)
        self.assertEqual(resumed["returnEpochNs"], 1_700_000_100_005_000_000)

    def test_incomplete_or_unmatched_clone_makes_exact_count_unavailable(self):
        parsed = self.parse({
            "threads.1": "1700000000.0 <... clone resumed> ) = 2 <0.1>\n1700000001.0 clone3({flags=CLONE_THREAD <unfinished ...>\n",
        })
        self.assertFalse(parsed["validation"]["exactCountAvailable"])
        self.assertEqual(len(parsed["validation"]["fatalErrors"]), 2)

    def test_malformed_or_zero_clone_return_makes_exact_count_unavailable(self):
        parsed = self.parse({
            "threads.1": "\n".join([
                "1700000000.0 clone(child_stack=NULL, flags=CLONE_THREAD) = 0 <0.1>",
                "1700000001.0 clone3({flags=CLONE_THREAD}, 88) = ? <0.1>",
                "1700000002.0 clone(child_stack=NULL, flags=CLONE_THREAD) = 7 unexpected <0.1>",
            ]),
        })
        self.assertFalse(parsed["validation"]["exactCountAvailable"])
        self.assertEqual(len(parsed["events"]), 0)
        self.assertEqual(len(parsed["validation"]["fatalErrors"]), 3)

    def test_window_classifies_boundary_crossing_calls_as_ambiguous(self):
        events = [
            {"entryEpochNs": 20, "returnEpochNs": 30, "childTid": 1},
            {"entryEpochNs": 5, "returnEpochNs": 15, "childTid": 2},
            {"entryEpochNs": 35, "returnEpochNs": 45, "childTid": 3},
        ]
        result = count_window(events, 10, 12, 40, 42)
        self.assertEqual(result["definite"], 1)
        self.assertEqual(result["ambiguous"], 2)
        self.assertEqual([event["childTid"] for event in result["definiteInside"]], [1])
        self.assertEqual([event["childTid"] for event in result["ambiguousEvents"]], [2, 3])
        self.assertFalse(result["exactCountAvailable"])


if __name__ == "__main__":
    unittest.main()
