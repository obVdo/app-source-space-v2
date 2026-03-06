# app-source-space-v2

Compute a surface-based source space from a FreeSurfer reconstruction.

The source space defines the candidate source locations on the cortical surface. It is a required input for the forward model computation.

## Inputs

| Datatype | Description |
|----------|-------------|
| `neuro/freesurfer` | FreeSurfer subject directory (output of recon-all) |

## Outputs

| Datatype | File | Description |
|----------|------|-------------|
| `neuro/source-space` | `source_space-src.fif` | Source space (consumed by app-forward-v2) |
| `report/html` | `report.html` | Interactive MRI slider with source points overlaid |

## Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `spacing` | `oct6` | `oct6`, `oct5`, `oct4` | Source density. `oct6` = 4098 sources/hemisphere (recommended). `oct5` = 1026. `oct4` = 258 (testing only). |
| `surface` | `white` | `white`, `inflated` | Cortical surface to place sources on. |
| `add_dist` | `false` | `false`, `patch`, `true` | Distance/patch information. `false` = fastest. `patch` = patch info only (needs SciPy). `true` = full (needs scikit-learn). |

## Pipeline Position

```
app-freesurfer-v2
      │
      └──→ app-source-space-v2  (source_space-src.fif)
                  │
                  └──→ app-forward-v2
```

`app-bem-v2` and `app-coreg-v2` run in parallel with this app — all three feed into `app-forward-v2`.

## Container

`docker://brainlife/mne-freesurfer:7.3.2-1.2.1`

Contains FreeSurfer 7.3.2 and MNE-Python 1.2.1.
