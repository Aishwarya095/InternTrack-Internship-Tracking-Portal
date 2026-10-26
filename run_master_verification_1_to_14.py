import os
import sys
import unittest
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

test_files = [
    ('Labs 1-7 (Main Acceptance Suite)', 'tests/test_acceptance.py'),
    ('Lab 8 (Parallel Swarm & Human Gate)', 'test_lab8_complete_suite.py'),
    ('Lab 9 (Deep Research & Grounding)', 'test_lab9_grounding.py'),
    ('Lab 10 (Ops Resilience & Self-Healing)', 'test_lab10_resilience.py'),
    ('Lab 11 (SDLC Factory & Green Gate)', 'test_lab11_sdlc_factory.py'),
    ('Lab 12 (Safety, Masking & Rollback)', 'test_lab12_governance.py'),
    ('Lab 13 (Discipline Specialists & Invariants)', 'test_lab13_discipline_specialists.py'),
    ('Lab 14 (Capstone Team-Owned System)', 'test_lab14_capstone.py')
]

results = []
total_tests = 0
total_passed = 0
total_failed = 0
total_errors = 0

print('=' * 80)
print('INTERNTRACK (AURA) — MASTER VERIFICATION RUNNER FOR LABS 1 TO 14')
print('Institution: KLE Technological University, Hubli')
print('Course: 26ECAC401 Agentic AI — 15 Worklets / 14-Lab Build Book (Chapter 10)')
print('=' * 80)

for label, rel_path in test_files:
    full_path = os.path.join(current_dir, rel_path)
    if not os.path.exists(full_path):
        print(f'[MISSING] {label} -> {full_path}')
        continue
    
    loader = unittest.TestLoader()
    dirname = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    suite = loader.discover(dirname, pattern=filename)
    
    t0 = time.time()
    runner = unittest.TextTestRunner(verbosity=0)
    res = runner.run(suite)
    elapsed = round(time.time() - t0, 3)
    
    count = res.testsRun
    fails = len(res.failures)
    errs = len(res.errors)
    passed = count - fails - errs
    
    total_tests += count
    total_passed += passed
    total_failed += fails
    total_errors += errs
    
    status = 'PASS (100% OK)' if (fails == 0 and errs == 0 and count > 0) else 'FAILED'
    print(f'[*] {label.ljust(45)} | Tests: {str(count).rjust(2)} | Passed: {str(passed).rjust(2)} | Status: {status} ({elapsed}s)')

print('=' * 80)
print(f'GRAND TOTAL: {total_tests} Tests Run across all 14 Labs')
print(f'             {total_passed} Passed | {total_failed} Failed | {total_errors} Errors')
print(f'OVERALL PASS RATE: {round((total_passed/total_tests)*100, 1)}%')
print('=' * 80)
