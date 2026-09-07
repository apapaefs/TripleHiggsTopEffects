# Language and grammar review: 7 September 2026

Reviewed the abstract, main text, captions, and acknowledgements in
[`main_k3t_extended.tex`](main_k3t_extended.tex), together with the redline.
Line references below refer to the clean source at the time of the review,
after the acknowledgement addition. This is a follow-up to the earlier review, which remains a record
of changes already implemented.

The prose is generally clear and consistent with the paper's British-English
conventions. The most useful remaining changes concern a caption inconsistency,
one nested sentence, and the precision of comparisons and conclusions.
All seven suggestions below were implemented in the clean and redline
manuscripts on 7 September 2026. The review is retained as an audit record;
its descriptions and proposed wording document the issues before correction.

## Applied: AP's acknowledgement

The acknowledgement now appears in both versions, with the complete sentence
marked as an addition in the redline:

> AP acknowledges support from the National Science Foundation under Grant
> No. PHY 2210161 and from the U.S. Department of Energy, Office of Science,
> Office of Nuclear Physics, under Award No. DE-SC0025728.

“Support from” is more idiomatic here than “support by”. Repeating “from”
makes the two funding sources parallel. “U.S.” matches the preceding
acknowledgement, and “Award No.” matches “Grant No.”. Both award identifiers
are preserved exactly as supplied.

## 1. Correct the fixed-coupling wording in Figures 3 and 4

Locations: captions at lines 311 and 472; discussion at line 477.

Both captions currently state that `kappa_t=1`, although the contours vary
`kappa_t`, as their labels and the discussion explain. The Figure 3 Run 2
panel, for example, explicitly labels the shifts as -20%, 0, and 20%.
This is an internal wording inconsistency, rather than an optional style edit.

Replace the final sentence of the Figure 3 caption with:

> We fix $\kappa_4=1$ and $\kappa_{3t}=0$, while $\kappa_t$ takes the values
> indicated by the contour labels.

For Figure 4, use the same sentence with $\kappa_3=1$ in place of
$\kappa_4=1$. In the discussion at line 477, replace “Parameters not shown
explicitly are fixed to their SM values” with:

> Apart from $\kappa_t$, which varies as indicated by the contour labels,
> all parameters not shown on the axes are fixed to their SM values.

## 2. Split the nested sentence about the top-quark Yukawa coupling

Location: line 475, beginning “The left panel demonstrates that modifications”.

The sequence “of ..., where ..., which ...” separates the subject from
“have a significant impact” and makes the relative clause difficult to follow.
Suggested replacement, retaining the existing citations:

```latex
The left panel shows that shifts of $\Delta\kappa_t=\pm20\%$, where
$\Delta\kappa_t=\kappa_t-1$, can significantly affect the resulting
constraints. Such shifts remain allowed at $95\%$~CL by LHC~Run~2
data~\cite{ATLAS:2022vkf,CMS:2022dwd}.
```

## 3. Make the Figure 8 benchmark assumptions explicit

Location: line 549, sentence beginning “The non-SM values”.

The current sentence names only `kappa3` and `kappa4` before saying that
“the remaining parameters” take their SM values. This can be read as including
`kappa2t`, although the plotted benchmarks have `kappa2t=2` and `kappa2t=-0.5`.
Suggested replacement:

> The non-SM values of $\kappa_3$ or $\kappa_4$ satisfy the relevant
> perturbative-unitarity constraints. The values of $\kappa_{2t}$ are
> indicated in the panels, and all parameters not specified by each benchmark
> are fixed to their SM values, including $\kappa_{3t}=0$.

## 4. Compare the precision of the two coefficient sets directly

Location: line 498, beginning “Their additional decimal places”.

“Compared with the first parametrisation” is attached to “decimal places”,
and significant figures are the more natural measure for coefficients of
different magnitudes. Suggested replacement:

> We retain more significant figures than in the first parametrisation to
> preserve the numerical accuracy of the fit.

## 5. Compare distributions with distributions

Location: line 562, beginning “Nevertheless, their normalised distributions”.

“Differ ... from the SM” is understandable shorthand, but an explicit
comparison reads more precisely:

> Nevertheless, their normalised distributions differ substantially from
> the SM distributions and from one another.

The same clarification would help the final sentence of line 573, where
“kinematic distributions from the SM” currently carries the comparison.

## 6. Make the conclusion's subject and level of inference precise

Location: line 573, final sentence.

“Differential information ... identifies ... benchmarks” assigns the action
to the information rather than the analysis. “Lifts ... degeneracies” also
sounds stronger than a demonstration of different parton-level distributions;
the Figure 8 discussion already uses the appropriately qualified “can help”.
Suggested replacement:

> We further identify mixed $(\kappa_3,\kappa_4,\kappa_{3t})$ benchmarks
> with nearly identical inclusive rates, $\mu_{3h}\simeq65$, whose
> normalised kinematic distributions differ substantially from the SM
> distributions and from one another. These examples illustrate how
> differential information can help to lift inclusive-rate degeneracies.

## 7. Use a direct formulation for the future-collider outlook

Location: line 575, beginning “An improvement by approximately one order”.

“An improvement ... in the determination” is grammatical but indirect.
Suggested replacement, retaining the existing citation list:

> The proposed hadron-collider stage of the Future Circular Collider could
> improve the sensitivity to the Higgs boson quartic self-coupling by
> approximately one order of magnitude.

The abstract and the recently shortened Figure 9 discussion need no further
substantial language changes. The existing conventions “parametrisation”,
“normalised”, and “formulae” are appropriate and should be retained.
