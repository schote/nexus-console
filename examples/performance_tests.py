# %%
import csv
from timeit import timeit

import numpy as np
from scipy.signal import resample


# Define function to test calls 
def test_calls(calls: list) -> dict:
    r = dict()
    for c in calls:
        t = timeit(c, number=1000, globals=globals())
        print(f"{c}: {t}s")
        r[c] = t
    return r


# globals
n_samples = 100000
factor = .1
offset = 5
order = "F"

array_a = np.zeros(n_samples)
array_b = np.ones(n_samples)
list_a = [0.] * n_samples 
list_b = [0.] * n_samples

x = np.arange(2*np.pi, step=(2*np.pi)/20)

results = dict()

# %%
# numpy arange vs. linspace
results.update(test_calls([
    "np.linspace(0, n_samples, n_samples)",
    "np.arange(n_samples)",
    "np.arange(n_samples)*factor",
    "np.arange(0, n_samples, step=factor)",
    "np.linspace(offset, offset+n_samples, n_samples)",
    "np.linspace(0, n_samples, n_samples) + offset",
]))

# %%
# Create list/array filled with zeros
results.update(test_calls([
    "np.zeros(n_samples)",
    "[0]*n_samples",
    "np.zeros(n_samples, dtype=float)",
    "[0.]*n_samples",
]))

# %%
# Concatenation
results.update(test_calls([
    "np.concatenate((list_a, list_b))",
    "np.concatenate((array_a, array_b))",
    "list_a + list_b",
    "list(array_a) + list(array_b)",
]))

# %%
# Interpolation vs. resampling
results.update(test_calls([
    "np.interp(x=np.linspace(x[0], x[-1], n_samples), xp=x, fp=np.sin(x))",
    "resample(np.sin(x), num=n_samples)",
]))

# %%
# Calculate carrier
results.update(test_calls([
    "np.exp(2j*np.pi*x)",
    "np.exp(2j*np.pi*x + offset)",
    "np.exp(2j*np.pi*x) * np.exp(1j*offset)",
]))

# %%
# Stack and reorder array
results.update(test_calls([
    "np.stack((array_a, array_b)).flatten(order=order)",
    "np.array([list_a, list_b]).flatten(order=order)",
]))


# %%
# Write results to csv table
with open("performance_test_results.csv", "w", newline="") as csv_fh:
    writer = csv.DictWriter(csv_fh, fieldnames=results.keys())
    writer.writeheader()
    writer.writerow(results)
# %%
