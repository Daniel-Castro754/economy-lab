# Economy Lab — External Engine Qualification

- Report ID: `d297903f-0b34-4a26-aa27-ebfd766429d4`
- SHA-256: `72d214b762531f54b3c3aeda940b122975cdfc56d6ffbbda5a44e00b77dfa1f8`
- Generated: 2026-08-30T17:06:05.799444+00:00
- Economy Lab: 2.11.0
- Runtime: Linux 6.18.35 (x86_64) · Python 3.12.13
- Overall: **PARTIAL**
- Qualification ready: **NO**

| Engine | Status | Qualification | Version | Compatibility | Integrated |
| --- | --- | --- | --- | --- | --- |
| MESA | UNAVAILABLE | none | — | unknown | no |
| HARK | UNAVAILABLE | none | — | unknown | no |
| DYNARE | UNAVAILABLE | none | — | unknown | no |
| MINSKY | UNAVAILABLE | none | — | unknown | no |

## MESA

Mesa não está instalado neste runtime.

| Stage | Status | Time | Evidence |
| --- | --- | ---: | --- |
| detect-import | UNAVAILABLE | 0 ms | Mesa não está instalado neste runtime. |

## HARK

Econ-ARK/HARK não está instalado neste runtime.

| Stage | Status | Time | Evidence |
| --- | --- | ---: | --- |
| detect-import | UNAVAILABLE | 0 ms | Econ-ARK/HARK não está instalado neste runtime. |

## DYNARE

Dynare/Octave não está pronto para execução.

**Error:** `GNU Octave não encontrado; defina OCTAVE_EXECUTABLE se necessário; pasta matlab do Dynare não encontrada; defina DYNARE_MATLAB_PATH`

| Stage | Status | Time | Evidence |
| --- | --- | ---: | --- |
| detect-runtime | UNAVAILABLE | 0 ms | Dynare/Octave não está pronto para execução. — GNU Octave não encontrado; defina OCTAVE_EXECUTABLE se necessário; pasta matlab do Dynare não encontrada; defina DYNARE_MATLAB_PATH |

## MINSKY

MINSKY_REST_URL não está configurado.

| Stage | Status | Time | Evidence |
| --- | --- | ---: | --- |
| rest-handshake | UNAVAILABLE | 0 ms | MINSKY_REST_URL não está configurado. |

## Notes

- Minsky qualification is read-only by design; it does not step/reset/load/save the open model.
- A PASS is runtime evidence, not a statement that the economic model is calibrated or empirically valid.
- Keep this report with the release/build that was qualified.
