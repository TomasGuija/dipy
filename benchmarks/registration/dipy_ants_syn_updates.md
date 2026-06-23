# DIPY / ANTs SyN Implementation Updates

This document tracks the DIPY changes used by the registration benchmark to
reduce implementation differences with ANTs SyN. Each update should describe
the behavioral change, its configuration, and its focused validation.

## 1. ANTs-Style Image Pyramid

### Previous DIPY behavior

`SymmetricDiffeomorphicRegistration` always used `ScaleSpace`. At pyramid level
`i`, it computed continuous per-axis scale factors from the minimum input
spacing and derived smoothing sigmas from `ss_sigma_factor`.

This produced physically isotropic output spacing, but it did not match ANTs'
integer shrink-factor pyramid or its smoothing schedule.

### Updated behavior

`SymmetricDiffeomorphicRegistration` now always constructs its pyramid with
`IsotropicScaleSpace`. For `L` levels, it automatically derives the nominal
shrink factors and smoothing sigmas used by ANTsPy SyN:

```text
sigma[i]  = L - 1 - i
factor[i] = 2 ** sigma[i]
```

For three levels:

```text
factors = [4, 2, 1]
sigmas  = [2, 1, 0]
```

The scalar sigma is applied equally along every voxel axis. For each nominal
factor, the finest-spacing axis receives that factor. Every other axis receives
the integer factor that makes its downsampled spacing closest to the target
spacing.

This creates approximately isotropic physical spacing. It does not force exact
isotropic spacing because every per-axis shrink factor remains an integer.

### API change

`ss_sigma_factor` has been removed from
`SymmetricDiffeomorphicRegistration`. SyN no longer exposes the previous
continuous scale-space construction.

## 2. Scale-Space Intensity Normalization

### Previous DIPY behavior

DIPY normalized the input image to `[0, 1]`, smoothed each coarse level, and
then independently renormalized every smoothed image to `[0, 1]`. Independent
per-level normalization changes the intensity scale after smoothing.

### Updated behavior

`IsotropicScaleSpace` now normalize the input image once before
constructing the pyramid. Every level is smoothed from that normalized image
without another min/max rescaling. This update has not been proven to actually essential. Results remain nearly the same with and without it. 

## 3. Discrete Gaussian Update Smoothing

### Previous DIPY behavior

`CCMetric` smoothed each update-field component with
`scipy.ndimage.gaussian_filter`. SciPy uses a sampled continuous Gaussian,
kernel truncation, and its own default boundary extension.

### Updated behavior

Update fields are now smoothed with a separable discrete Gaussian matching the
ITK SyN operation:

- kernel coefficients use the discrete Gaussian formulation based on modified
  Bessel functions;
- the configured value is interpreted as variance;
- kernel support is selected with maximum error `0.001`;
- each spatial axis is filtered independently;
- out-of-bounds values use zero-flux boundary extension;
- ITK's blend with the original field is retained for variances below `0.5`.

The generic smoothing helper operates on the complete vector field, so forward
and backward CC updates use the same implementation. Generated kernels are
cached by variance and axis size. The optimizer then sets the outer displacement
boundary to zero immediately after smoothing and before update normalization,
matching the SyN update order.


### Quantitative effect of the combined changes

Benchmarking results over 100 OASIS2 pairs:

| Method | NCC ↑ | NMI ↑ | Label Dice ↑ | Label Jaccard ↑ |
|---|---:|---:|---:|---:|
| Baseline | 0.9366 | 1.1833 | 0.9234 | 0.8598 |
| ANTs | 0.9506 | 1.2008 | **0.9236** | **0.8600** |
| DIPY | **0.9508** | **1.2011** | 0.9219 | 0.8571 |