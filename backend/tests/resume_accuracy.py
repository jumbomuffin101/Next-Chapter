"""Run from repository root: python -m backend.tests.resume_accuracy [--baseline]."""
import argparse
import subprocess
import time
import tracemalloc
import types

from backend.app.parsing.rule_parser import parse_resume_text
from backend.app.parsing.extract import extract_text
from backend.tests.test_resume_quality import CASES, pdf_with_lines


def score(parser):
    predicted, expected = set(), set()
    for label, text, target in CASES:
        result = parser(text)
        predicted.add((label, "name", (result.full_name or "").casefold()))
        expected.add((label, "name", target["name"].casefold()))
        predicted.update((label, "job", f"{j.title.casefold()}|{j.employer.casefold()}") for j in result.work_experience)
        expected.update((label, "job", f"{title.casefold()}|{employer.casefold()}") for title, employer in target["jobs"])
        predicted.update((label, "skill", skill.casefold()) for skill in result.skills)
        expected.update((label, "skill", skill.casefold()) for skill in target["skills"])
        predicted.update((label, "cert", cert.casefold()) for cert in result.certifications)
        expected.update((label, "cert", cert.casefold()) for cert in target["certs"])
    return {field: {
        "correct": len({item for item in predicted & expected if item[1] == field}),
        "predicted": len({item for item in predicted if item[1] == field}),
        "expected": len({item for item in expected if item[1] == field}),
    } for field in ("name", "job", "skill", "cert")}


def baseline_parser():
    source = subprocess.run(["git", "show", "580cb4769ddc229f5f4a7fa56465383d89af8a32:backend/app/parsing/rule_parser.py"],
                            check=True, capture_output=True).stdout.decode("utf-8")
    module = types.ModuleType("backend.app.parsing._pre_audit_parser")
    module.__package__ = "backend.app.parsing"
    exec(compile(source, "pre_audit_rule_parser.py", "exec"), module.__dict__)
    return module.parse_resume_text


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--baseline", action="store_true")
    args.add_argument("--benchmark", action="store_true")
    options = args.parse_args()
    use_baseline = options.baseline
    if options.benchmark:
        payload = pdf_with_lines([CASES[0][1].splitlines()])
        tracemalloc.start()
        started = time.perf_counter()
        for _ in range(25):
            parse_resume_text(extract_text(payload))
        elapsed = (time.perf_counter() - started) * 1000 / 25
        _, peak = tracemalloc.get_traced_memory()
        print(f"25 synthetic one-page PDF parses: {elapsed:.1f} ms/parse; peak traced Python memory {peak / 1048576:.1f} MiB")
        raise SystemExit(0)
    result = score(baseline_parser() if use_baseline else parse_resume_text)
    for field, counts in result.items():
        correct, predicted, expected = counts.values()
        precision = correct / predicted if predicted else 1.0
        recall = correct / expected if expected else 1.0
        print(f"{field}: precision={precision:.3f} recall={recall:.3f} ({correct}/{predicted} predicted, {expected} expected)")
