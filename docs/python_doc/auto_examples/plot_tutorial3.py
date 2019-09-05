"""
Tutorial 3: Null models for gradient significance
==================================================
In this tutorial we assess the significance of correlations between the first
canonical gradient and data from other modalities (curvature, cortical
thickness and T1w/T2w image intensity). A normal test of the significance of
the correlation cannot be used, because the spatial auto-correlation in MRI
data may bias the test statistic. In this tutorial we will show two approaches
for null hypothesis testing: spin permutations and Moran spectral
randomization.

.. note::
    When using either approach to compare gradients to non-gradient markers,
    we recommend randomizing the non-gradient markers as these randomizations
    need not maintain the statistical independence between gradients.

"""


###############################################################################
# Spin Permutations
# ------------------------------
#
# Here, we use the spin permutations approach previously proposed in
# `(Alexander-Bloch et al., 2018)
# <https://www.sciencedirect.com/science/article/pii/S1053811918304968>`_,
# which preserves the auto-correlation of the permuted feature(s) by rotating
# the feature data on the spherical domain.
# We will start by loading the conte69 surfaces for left and right hemispheres,
# their corresponding spheres, midline mask, and t1w/t2w intensity as well as
# cortical thickness data, and a template functional gradient.


import warnings
warnings.simplefilter('ignore')

import numpy as np
from brainspace.datasets import load_gradient, load_marker, load_conte69

# load the conte69 hemisphere surfaces and spheres
surf_lh, surf_rh = load_conte69()
sphere_lh, sphere_rh = load_conte69(as_sphere=True)

# Load the data
t1wt2w_lh, t1wt2w_rh = load_marker('t1wt2w')
t1wt2w = np.concatenate([t1wt2w_lh, t1wt2w_rh])

thickness_lh, thickness_rh = load_marker('thickness')
thickness = np.concatenate([thickness_lh, thickness_rh])

# Template functional gradient
embedding = load_gradient('fc', idx=0, join=True)


###############################################################################
# Let’s first generate some null data using spintest.

import numpy as np

from brainspace.null_models import SpinPermutations
from brainspace.plotting import plot_hemispheres

# Let's create some rotations
n_permutations = 1000

sp = SpinPermutations(n_rep=n_permutations, random_state=0)
sp.fit(sphere_lh, points_rh=sphere_rh)

t1wt2w_rotated = np.hstack(sp.randomize(t1wt2w_lh, t1wt2w_rh))
thickness_rotated = np.hstack(sp.randomize(thickness_lh, thickness_rh))


###############################################################################
# As an illustration of the rotation, let’s plot the original t1w/t2w data

# Plot original data
plot_hemispheres(surf_lh, surf_rh, array_name=t1wt2w, size=(1200, 300), cmap='viridis',
                 nan_color=(0.5, 0.5, 0.5, 1), color_bar=True)


###############################################################################
# as well as a few rotated versions.

# sphinx_gallery_thumbnail_number = 2
# Plot some rotations
plot_hemispheres(surf_lh, surf_rh, array_name=t1wt2w_rotated[:3], size=(1200, 800),
                 cmap='viridis', nan_color=(0.5, 0.5, 0.5, 1), color_bar=True,
                 label_text=['Rot0', 'Rot1', 'Rot2'])


###############################################################################
#
# .. warning::
#
#    With spin permutations, midline vertices (i.e,, NaNs) from both the
#    original and rotated data are discarded. Depending on the overlap of
#    midlines in the, statistical comparisons between them may compare
#    different numbers of features. This can bias your test statistics.
#    Therefore, if a large portion of the sphere is not used, we recommend
#    using Moran spectral randomization instead.
#
# Now we simply compute the correlations between the first gradient and the
# original data, as well as all rotated data.

from scipy.stats import spearmanr

feats = {'t1wt2w': t1wt2w, 'thickness': thickness}
rotated = {'t1wt2w': t1wt2w_rotated, 'thickness': thickness_rotated}

r_spin = np.empty(n_permutations)
mask = ~np.isnan(thickness)
for fn, feat in feats.items():
    r_orig, pv_orig = spearmanr(feat[mask], embedding[mask])

    for i, perm in enumerate(rotated[fn]):
        mask_rot = mask & ~np.isnan(perm)  # Remove non-cortex
        r_spin[i] = spearmanr(perm[mask_rot], embedding[mask_rot])[0]
    pv_spin = np.mean(np.abs(r_spin) > np.abs(r_orig))

    print('{0}:\n Obs : {1:.5e}\n Spin: {2:.5e}\n'.
          format(fn.capitalize(), pv_orig, pv_spin))

###############################################################################
# It is interesting to see that both p-values increase when taking into
# consideration the auto-correlation present in the surfaces. Also, we can see
# that the correlation with thickness is no longer statistically significant
# after spin permutations.
#
#
#
# Moran Spectral Randomization
# ------------------------------
#
# Moran Spectral Randomization (MSR) computes Moran's I, a metric for spatial
# auto-correlation and generates normally distributed data with similar
# auto-correlation. MSR relies on a weight matrix denoting the spatial
# proximity of features to one another. Within neuroimaging, one
# straightforward example of this is inverse geodesic distance i.e. distance
# along the cortical surface.
#
# In this example we will show how to use MSR to assess statistical
# significance between cortical markers (here curvature and cortical t1wt2w
# intensity) and the first functional connectivity gradient. We will start by
# loading the left temporal lobe mask, t1w/t2w intensity as well as cortical
# thickness data, and a template functional gradient


from brainspace.datasets import load_mask
from brainspace.mesh import mesh_elements as me

n_pts_lh = surf_lh.n_points
mask_tl, _ = load_mask(name='temporal')

# Keep only the temporal lobe.
embedding_tl = embedding[:n_pts_lh][mask_tl]
t1wt2w_tl = t1wt2w_lh[mask_tl]
curv_tl = load_marker('curvature')[0][mask_tl]


###############################################################################
# We will now compute the Moran eigenvectors. This can be done either by
# providing a weight matrix of spatial proximity between each vertex, or by
# providing a cortical surface. Here we’ll use a cortical surface.

from brainspace.null_models import MoranRandomization

# compute spatial weight matrix
w = me.get_ring_distance(surf_lh, n_ring=1, mask=mask_tl)
w.data **= -1

n_rand = 1000

msr = MoranRandomization(n_rep=n_rand, procedure='singleton', tol=1e-6,
                         random_state=0)
msr.fit(w)


###############################################################################
# Using the Moran eigenvectors we can now compute the randomized data.

curv_rand = msr.randomize(curv_tl)
t1wt2w_rand = msr.randomize(t1wt2w_tl)


###############################################################################
# Now that we have the randomized data, we can compute correlations between
# the gradient and the real/randomised data and generate the non-parametric
# p-values.

feats = {'t1wt2w': t1wt2w_tl, 'curvature': curv_tl}
rand = {'t1wt2w': t1wt2w_rand, 'curvature': curv_rand}

for fn, data in rand.items():
    r_obs, pv_obs = spearmanr(feats[fn], embedding_tl, nan_policy='omit')

    r_rand = np.asarray([spearmanr(embedding_tl, d)[0] for d in data])
    pv_rand = np.mean(np.abs(r_rand) >= np.abs(r_obs))

    print('{0}:\n Obs  : {1:.5e}\n Moran: {2:.5e}\n'.
          format(fn.capitalize(), pv_obs, pv_rand))
