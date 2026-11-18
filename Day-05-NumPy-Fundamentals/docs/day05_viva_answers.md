# Day 05 - Viva answers (own words, with a runnable check for each)

**1. What does `shape` tell you?**
The size along each dimension, as a tuple: `(3, 4)` is 3 rows x 4 columns, `(7,)` is a
flat vector of 7, `()` is a single number. `len(shape)` is `ndim`; the product is `size`.
It decides what operations are legal (broadcasting, `@`) and what an aggregate returns.
`a[:, 1]` has shape `(3,)` but `a[:, 1:2]` has shape `(3, 1)` - the same data, different shape.

**2. Broadcasting with a concrete example.**
`hours` has shape `(2, 2)` (2 tickets x [hours, rating]); `hours.mean(axis=0)` has shape `(2,)`.
`hours - means` right-aligns `(2, 2)` and `(2,)` -> `(2, 2)` and `(1, 2)`; the size-1
dimension is stretched virtually (no copy) so the same row of means is subtracted from every
row. Rule: align on the right; each pair of sizes must be equal or one must be 1.
Failing case: `(3,)` + `(4,)` -> error. Silent trap: `(3,)` + `(3, 1)` -> `(3, 3)`.
Checks: `tests/test_broadcasting.py`.

**3. Python list vs NumPy array.**
A list holds pointers to separate Python objects of any type; an `ndarray` holds one
contiguous block of a single dtype (`float64` = 8 bytes each) plus shape/strides. So arrays are
smaller, support vectorised maths in compiled code, slicing returns *views* (shared memory),
and the dtype is fixed (an int array cannot hold NaN; a list can hold `None`).
Cost: conversion from a list (see "numpy+convert" in `logs/benchmark.txt`) and no mixed types.

**4. What does `axis` mean?**
The dimension that gets *collapsed* by the reduction. For shape `(rows, cols)`:
`axis=0` collapses the rows -> one result per column; `axis=1` collapses the columns -> one
result per row; `axis=None` collapses everything. `keepdims=True` leaves that axis as size 1,
which is what makes the result broadcastable back against the original.

**5. Why do floats look imprecise?**
Binary floating point stores a finite number of binary digits; 0.1 has no exact binary form, so
`0.1 + 0.2 == 0.30000000000000004`. Every operation rounds. Consequences tested here:
compare with `isclose`, not `==`; adding a tiny number to a huge one loses it
(`1e16 + 1.0 == 1e16`); `E[x^2]-E[x]^2` cancels catastrophically with a large offset;
`NaN != NaN`. See `tests/test_numerical.py`.
