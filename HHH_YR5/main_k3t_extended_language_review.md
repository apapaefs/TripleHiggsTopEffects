# Language and consistency review

Reviewed source: [`main_k3t_extended.tex`](main_k3t_extended.tex), including
the inserted coefficients in
[`ct3_rate_fit_coefficients.tex`](ct3_rate_fit_coefficients.tex).

The corrections identified below were implemented in
`main_k3t_extended.tex` on 2 September 2026. The review is retained as an
audit record, so its original line references describe the pre-correction
source. The mixed $\kappa_{3t}$ benchmark discussion was also restored to the
validated $\mu_{3h}\simeq65$ samples at the author's request.

## Language convention

This review interprets “Oxford British English” according to the current
[University of Oxford spelling guidance](https://www.ox.ac.uk/about/the-university/brand/style-guide/words):
use British spellings and the suffixes `-ise`, `-yse`, and `-isation`. This
differs from the `-ize` convention used by Oxford University Press. In
mathematical contexts, the preferred plural is *formulae*.

The draft is already predominantly consistent with British English. The most
important findings concern the scope of the two parametrisations, fixed
couplings, luminosity conventions, benchmark-rate wording, and several
technical statements.

## Important consistency corrections

### 1. Clarify the scope of the two parametrisations

Locations: lines 91 and 178.

The abstract and introduction currently imply that a single parametrisation
simultaneously retains the dependence on all five couplings. The two fits do
not simultaneously vary `kappa2t` and `kappa3t`.

Suggested wording:

> We derive complementary compact parametrisations of the inclusive
> gluon-fusion cross section: one retains the dependence on
> $\kappa_3$, $\kappa_4$, $\kappa_t$, and $\kappa_{2t}$ for
> $\kappa_{3t}=0$, while the other incorporates $\kappa_{3t}$ for
> $\kappa_t=1$ and $\kappa_{2t}=0$.

In the final sentence of the abstract, also replace “HL-LHC data” with
“HL-LHC projections” and “provide additional discrimination” with “provide
additional discriminatory power”.

### 2. State explicitly where `kappa3t` is fixed to zero

Locations: lines 205–208, 298, 459–464, and 521–536.

The original rate parametrisation and Figures 2–4 predate the introduction of
$\kappa_{3t}$. In the combined draft, they should explicitly state that
$\kappa_{3t}=0$. The same applies to the Figure 7 and Figure 8 samples.

For example, the Figure 7 caption should end with:

> All results are obtained for $\kappa_t=1$ and
> $\kappa_{2t}=\kappa_{3t}=0$.

The discussion introducing Eq. 9 should likewise state that
$\kappa_{3t}=0$ throughout the first parametrisation.

### 3. Reconcile the HL-LHC luminosity conventions

Locations: lines 158, 176, and 462.

The introduction uses $6\,\mathrm{ab}^{-1}$, whereas the constraint discussion
uses $3\,\mathrm{ab}^{-1}$. If the former denotes the combined ATLAS–CMS
exposure, state this explicitly:

> $3\,\mathrm{ab}^{-1}$ per experiment, corresponding to a combined exposure
> of $6\,\mathrm{ab}^{-1}$.

Line 462 should also be rewritten so that the $3\,\mathrm{ab}^{-1}$ assumption
clearly applies only to the HL-LHC projection, not to the Run 2 data.

### 4. Do not call unequal rates “the same”

Locations: lines 524 and 536.

The statements that the benchmarks have “the same” signal strength conflict
with the subsequent statements that their cross sections differ.

For Figure 7, use:

> Both benchmark points give $\mu_{3h}\simeq65$, and their inclusive cross
> sections differ by less than $5\%$.

Use the analogous wording with $\mu_{3h}\simeq75$ for Figure 8. This also makes
Figures 7–9 use the same approximate-rate convention.

### 5. Correct the statement about rescaling normalised distributions

Location: line 524.

A normalised distribution cannot undergo an overall rescaling. Replace:

> variations of $\kappa_t$ approximately induce an overall rescaling of the
> normalised distributions

with:

> variations of $\kappa_t$ predominantly rescale the unnormalised spectra and
> therefore have little effect on their normalised shapes.

### 6. Correct the second rate-degenerate solution

Locations: lines 513 and 558.

The displayed fitted coefficients give the non-zero roots

- $\kappa_{3t}=0.179023$ at $13\,\mathrm{TeV}$;
- $\kappa_{3t}=0.177556$ at $13.6\,\mathrm{TeV}$;
- $\kappa_{3t}=0.179190$ at $14\,\mathrm{TeV}$.

It is therefore not accurate to state that the solution is $0.179$ at all
three energies “to the accuracy of the fit”. Either quote $0.179$, $0.178$,
and $0.179$, respectively, or use:

> an energy-dependent second solution near $\kappa_{3t}=0.179$.

The conclusion should use the same wording.

### 7. Reconcile Figure 1 with the extended Lagrangian

Locations: lines 188–193.

Figure 1 displays top-quark couplings involving one or two Higgs bosons, but
not the two-top–three-Higgs vertex. The current transition implies that all
terms in the extended Lagrangian are highlighted in the figure.

Either add the $t\bar t hhh$ vertex to the diagram or replace the opening of
line 193 with:

> The relevant terms in the $\kappa$-framework Lagrangian are

### 8. Use “allowed”, not “preferred”, for upper-limit regions

Location: line 205.

The contours are constructed from upper limits rather than a likelihood
preference. Replace “preferred $95\%$ CL regions” with “allowed $95\%$ CL
regions”. Also standardise “black points” and “black dots” throughout the
captions and discussion.

### 9. Add a citation for the projected `kappa3` interval

Locations: lines 158–161.

The projected HL-LHC interval $0.5<\kappa_3<1.7$ currently has no citation.
Add the appropriate projection reference immediately after the displayed
interval.

### 10. Correct the DOI for the Bizoń–Haisch–Rottoli article

Locations: lines 716–721 and the corresponding entry in `ref.bib`.

The 2019 article should use DOI
[`10.1007/JHEP10(2019)267`](https://link.springer.com/article/10.1007/JHEP10%282019%29267).
The DOI currently shown, `10.1007/JHEP02(2024)170`, belongs to the 2024
addendum. If the addendum is also relevant, cite it separately or record it as
an addendum rather than pairing its DOI with the 2019 journal details.

## Language and phrasing corrections

- **Line 91:** change “HL-LHC data” to “HL-LHC projections” and “provide
  additional discrimination” to “provide additional discriminatory power”.
- **Line 193:** prefer “The relevant terms in the $\kappa$-framework
  Lagrangian are” to “The $\kappa$-formalism Lagrangian … takes the form”.
- **Line 208:** use “At centre-of-mass energies …” rather than “For collision
  energies of …”.
- **Lines 298 and 459:** change “As Figure …” to “As in Figure …”.
- **Line 446:** “We note that …” is more natural than “Notice that …”.
- **Lines 448–449:** use “the infinite-top-quark-mass limit”.
- **Line 451:** simplify “the LHC triple-Higgs gluon-fusion production cross
  section” to “the triple-Higgs gluon-fusion cross section at the LHC”.
- **Line 469:** add a comma after “In this scan”.
- **Line 471:** “Following Eq. 9, we write …” is more direct than “Following
  the form of Eq. 9 …”.
- **Line 483:** replace “agree at the percent level” with the more precise
  “agree to within $1.1\%$”.
- **Lines 496 and 504:** insert a source-space after the closing `\label{...}`
  for consistency with the other captions.
- **Line 524:** remove the repeated explanation of the two observables and
  fixed couplings already supplied by the Figure 7 caption.
- **Line 524:** replace “reaching up to about $50\%$ in both …, in the peak
  regions as well as …” with “with deviations of up to about $50\%$ in the
  peak regions and high-energy tails of both distributions”.
- **Line 524:** label the projected quartic-coupling equation and refer to it
  directly instead of saying “the constraint quoted below Eq. …”.
- **Line 532:** prefer “two further benchmark scenarios in the
  $\kappa$-framework” to “two other $\kappa$-benchmark scenarios”.
- **Line 536:** remove the stray ordinary space in `As in ~Figure`.
- **Line 544:** “wider plotting ranges” is more idiomatic than “wider
  displayed ranges”.
- **Line 547:** “differ substantially from both the SM and one another” is
  smoother than “differ strongly both from the SM and from one another”.
- **Line 554:** replace “retain significant discovery potential” with “offer
  significant discovery potential”.
- **Line 556:** use the mathematical plural and British quotation convention:
  `‘pocket formulae’`.
- **Line 556:** standardise the lone “parameterisation” to the otherwise-used
  “parametrisation”.
- **Line 556:** use lower case for the generic term “Higgs effective field
  theory”.
- **Line 558:** avoid repeating “using”: “Using these parametrisations, we
  have studied how current and projected LHC data constrain …”.
- **Line 560:** “the proposed hadron-collider stage of the Future Circular
  Collider” is clearer than “a hadron-collider option of the Future Circular
  Collider”.

## Suggested rewrite of the Figure 7 discussion

The current paragraph at line 524 duplicates much of the caption and contains
the normalised-rescaling issue. A tighter version would be:

> Modifications of the Higgs trilinear and quartic self-couplings affect both
> the inclusive $gg\to3h$ cross section and the kinematic properties of the
> final state. Figure 7 compares normalised distributions for the SM with two
> BSM benchmarks. Both benchmarks give $\mu_{3h}\simeq65$, and their inclusive
> cross sections differ by less than $5\%$, while their values of $\kappa_3$
> and $\kappa_4$ satisfy the perturbative-unitarity constraints from tree-level
> $hh\to hh$ scattering. We set $\kappa_t=1$ and
> $\kappa_{2t}=\kappa_{3t}=0$. Variations of $\kappa_t$ predominantly rescale
> the unnormalised spectra and therefore have little effect on their normalised
> shapes [41]. Nevertheless, the two benchmarks produce deviations of up to
> about $50\%$ in the peak regions and high-energy tails of both distributions.
> Differential information can therefore strengthen future HL-LHC constraints
> beyond those obtained from the inclusive rate alone.

## Suggested rewrite of the Figure 8 discussion

The paragraph at line 536 could read:

> Figure 8 presents further normalised distributions for the SM and two BSM
> benchmarks in the $\kappa$-framework. Both benchmarks give
> $\mu_{3h}\simeq75$, and their inclusive cross sections differ by less than
> $5\%$. The non-SM values of $\kappa_3$ or $\kappa_4$ satisfy the relevant
> perturbative-unitarity constraints, while the remaining parameters are fixed
> to their SM values, including $\kappa_{3t}=0$. As in Figure 7, sizeable shape
> distortions remain despite the near-degeneracy of the inclusive rates. This
> illustrates how differential information can help to resolve parameter
> degeneracies in future $gg\to3h$ searches at the HL-LHC.

## Source and typography consistency

- Replace `\rm SM`, `\rm ATLAS`, and `\rm CMS` with `\mathrm{SM}`,
  `\text{ATLAS}`, and `\text{CMS}`.
- Replace `\{\tt MCFM\}` and `\{\tt PDF4LHC21\}` with `\texttt{MCFM}` and
  `\texttt{PDF4LHC21}`.
- Use en-dash equation ranges, for example `Eqs.~(...)--(...)`, rather than
  “to”.
- Standardise displayed-equation punctuation. Some intermediate rows in the
  coefficient lists lack commas, whereas others end with `\,,`.
- Standardise spacing around equal signs and inequalities in the source.
- Use a single form of “at $95\%$ CL” throughout; the draft alternates between
  “at the $95\%$ CL” and “at $95\%$ CL”.
- The original coefficients are displayed to approximately three significant
  figures, whereas the new fit retains six or seven. Either harmonise their
  presentation or add a sentence explaining that the additional digits are
  retained to reproduce the numerical fit accuracy.
- Consider replacing `\cdot10^{-n}` with the more conventional
  `\times10^{-n}` in the three coefficient lists.
- Keep the original spelling and capitalisation of published article titles,
  even where they use American English.

## Compilation and bibliography observations

- All 56 citations in the manual bibliography are used, and no cited item is
  missing.
- No duplicate or unresolved `\label`/`\ref` pairs were found.
- The document compiles without undefined references.
- The compilation log reports a conflict between the `cite` package loaded by
  the class and `natbib`; remove the redundant package or use the citation
  mechanism expected by `SciPost.cls`.
- The section title containing `$\kappa$` produces a PDF-bookmark warning. Use
  `\texorpdfstring` or provide a plain-text bookmark title.
- The log reports a substantial overfull box in the template copyright block
  and a small overfull box around lines 193–194.
- `ref.bib` contains multiple duplicate citation keys. This does not affect
  the current manually embedded bibliography, but the duplicates should be
  removed before re-enabling BibTeX.
- The inactive template comments contain `finilized` instead of `finalised`
  and “longer that 6 pages” instead of “longer than 6 pages”. These do not
  affect the rendered manuscript but can be corrected for source hygiene.

## Recommended order of work

1. Resolve the coupling-scope, fixed-$\kappa_{3t}$, luminosity, and benchmark
   consistency points.
2. Correct the rate-degenerate root and bibliography DOI.
3. Apply the language changes and streamline the distribution discussion.
4. Standardise LaTeX notation, significant figures, and equation punctuation.
5. Recompile and inspect the clean and redline PDFs.
