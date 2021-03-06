#! /usr/bin/env python

"""
Module with functions for computing SVDs.
"""

from __future__ import division
from __future__ import print_function

__author__ = 'C. Gomez @ ULg'
__all__ = ['svd_wrapper',
           'randomized_svd_gpu']

import warnings
try:
    import cupy
    no_cupy = False
except ImportError:
    msg = "Cupy not found. Have a GPU? Consider setting up a CUDA environment "
    msg += "and installing cupy >= 2.0.0"
    warnings.warn(msg, ImportWarning)
    no_cupy = True

import numpy as np
from numpy import linalg
from matplotlib import pyplot as plt 
from scipy.sparse.linalg import svds
from sklearn.decomposition import randomized_svd
from sklearn.metrics import mean_squared_error as MSE
from sklearn.metrics import mean_absolute_error as MAE
from sklearn.utils import check_random_state


def svd_wrapper(matrix, mode, ncomp, debug, verbose, usv=False):
    """ Wrapper for different SVD libraries (CPU and GPU). 
      
    Parameters
    ----------
    matrix : array_like, 2d
        2d input matrix.
    mode : {'lapack', 'arpack', 'eigen', 'randsvd', 'cupy', 'eigencupy', 'randcupy'}, str
        Switch for the SVD method/library to be used. ``lapack`` uses the LAPACK 
        linear algebra library through Numpy and it is the most conventional way 
        of computing the SVD (deterministic result computed on CPU). ``arpack`` 
        uses the ARPACK Fortran libraries accessible through Scipy (computation
        on CPU). ``eigen`` computes the singular vectors through the 
        eigendecomposition of the covariance M.M' (computation on CPU).
        ``randsvd`` uses the randomized_svd algorithm implemented in Sklearn 
        (computation on CPU). ``cupy`` uses the Cupy library for GPU computation
        of the SVD as in the LAPACK version. ``eigencupy`` offers the same 
        method as with the ``eigen`` option but on GPU (through Cupy). 
        ``randcupy`` is an adaptation of the randomized_svd algorith, where all 
        the computations are done on a GPU. 
    ncomp : int
        Number of singular vectors to be obtained. In the cases when the full
        SVD is computed (LAPACK, ARPACK, EIGEN, CUPY), the matrix of singular 
        vectors is truncated. 
    debug : bool
        If True the explained variance ratio is computed and displayed.
    verbose: bool
        If True intermediate information is printed out.
    usv : {False, True}, bool optional
        If True the 3 terms of the SVD factorization are returned.
    
    Returns
    -------
    The right singular vectors of the input matrix. If ``usv`` is True it 
    returns the left and right singular vectors and the singular values of the
    input matrix.
    
    References
    ----------
    * For ``lapack`` SVD mode see:
    https://docs.scipy.org/doc/numpy-1.13.0/reference/generated/numpy.linalg.svd.html
    http://www.netlib.org/lapack/
    
    * For ``eigen`` mode see:
    https://docs.scipy.org/doc/numpy-1.13.0/reference/generated/numpy.linalg.eigh.html
    
    * For ``arpack`` SVD mode see:
    https://docs.scipy.org/doc/scipy-0.19.1/reference/generated/scipy.sparse.linalg.svds.html
    http://www.caam.rice.edu/software/ARPACK/
    
    * For ``randsvd`` SVD mode see:
    https://github.com/scikit-learn/scikit-learn/blob/master/sklearn/utils/extmath.py
    Finding structure with randomness: Stochastic algorithms for constructing
    approximate matrix decompositions
    Halko, et al., 2009 http://arxiv.org/abs/arXiv:0909.4061
    
    * For ``cupy`` SVD mode see:
    https://docs-cupy.chainer.org/en/stable/reference/generated/cupy.linalg.svd.html
    
    * For ``eigencupy`` SVD mode see:
    https://docs-cupy.chainer.org/en/master/reference/generated/cupy.linalg.eigh.html   
    
    """

    def reconstruction(ncomp, U, S, V, var=1):
        if mode == 'lapack':
            rec_matrix = np.dot(U[:, :ncomp],
                                np.dot(np.diag(S[:ncomp]), V[:ncomp]))
            rec_matrix = rec_matrix.T
            print('  Matrix reconstruction with {:} PCs:'.format(ncomp))
            print('  Mean Absolute Error =', MAE(matrix, rec_matrix))
            print('  Mean Squared Error =', MSE(matrix, rec_matrix))

            # see https://github.com/scikit-learn/scikit-learn/blob/c3980bcbabd9d2527548820581725df2904e4a0d/sklearn/decomposition/pca.py
            exp_var = (S ** 2) / (S.shape[0] - 1)
            full_var = np.sum(exp_var)
            explained_variance_ratio = exp_var / full_var   # % of variance explained by each PC
            ratio_cumsum = np.cumsum(explained_variance_ratio)
        elif mode == 'eigen':
            exp_var = (S ** 2) / (S.shape[0] - 1)
            full_var = np.sum(exp_var)
            explained_variance_ratio = exp_var / full_var   # % of variance explained by each PC
            ratio_cumsum = np.cumsum(explained_variance_ratio)
        else:
            rec_matrix = np.dot(U, np.dot(np.diag(S), V))
            print('  Matrix reconstruction MAE =', MAE(matrix, rec_matrix))
            exp_var = (S ** 2) / (S.shape[0] - 1)
            full_var = np.var(matrix, axis=0).sum()
            explained_variance_ratio = exp_var / full_var   # % of variance explained by each PC
            if var == 1:
                pass
            else:
                explained_variance_ratio = explained_variance_ratio[::-1]
            ratio_cumsum = np.cumsum(explained_variance_ratio)
            msg = '  This info makes sense when the matrix is mean centered '
            msg += '(temp-mean scaling)'
            print(msg)

        lw = 2; alpha = 0.4
        fig = plt.figure(figsize=(6, 3))
        fig.subplots_adjust(wspace=0.4)
        ax1 = plt.subplot2grid((1, 3), (0, 0), colspan=2)
        ax1.step(range(explained_variance_ratio.shape[0]),
                 explained_variance_ratio, alpha=alpha, where='mid',
                 label='Individual EVR', lw=lw)
        ax1.plot(ratio_cumsum, '.-', alpha=alpha,
                 label='Cumulative EVR', lw=lw)
        ax1.legend(loc='best', frameon=False, fontsize='medium')
        ax1.set_ylabel('Explained variance ratio (EVR)')
        ax1.set_xlabel('Principal components')
        ax1.grid(linestyle='solid', alpha=0.2)
        ax1.set_xlim(-10, explained_variance_ratio.shape[0] + 10)
        ax1.set_ylim(0, 1)

        trunc = 20
        ax2 = plt.subplot2grid((1, 3), (0, 2), colspan=1)
        # plt.setp(ax2.get_yticklabels(), visible=False)
        ax2.step(range(trunc), explained_variance_ratio[:trunc], alpha=alpha,
                 where='mid', lw=lw)
        ax2.plot(ratio_cumsum[:trunc], '.-', alpha=alpha, lw=lw)
        ax2.set_xlabel('Principal components')
        ax2.grid(linestyle='solid', alpha=0.2)
        ax2.set_xlim(-2, trunc + 2)
        ax2.set_ylim(0, 1)

        msg = '  Cumulative explained variance ratio for {:} PCs = {:.5f}'
        # plt.savefig('figure.pdf', dpi=300, bbox_inches='tight')
        print(msg.format(ncomp, ratio_cumsum[ncomp - 1]))

    # --------------------------------------------------------------------------

    if not matrix.ndim == 2:
        raise TypeError('Input matrix is not a 2d array')

    if usv:
        if mode not in ('lapack', 'arpack', 'randsvd', 'cupy', 'randcupy'):
            msg = 'Returning USV is supported with modes lapack, arpack, randsvd, cupy or randcupy'
            raise ValueError(msg)

    if ncomp > min(matrix.shape[0], matrix.shape[1]):
        msg = '{:} PCs cannot be obtained from a matrix with size [{:},{:}].'
        msg += ' Increase the size of the patches or request less PCs'
        raise RuntimeError(msg.format(ncomp, matrix.shape[0], matrix.shape[1]))

    if mode == 'eigen':
        # building the covariance as np.dot(matrix.T,matrix) is slower and takes more memory
        C = np.dot(matrix, matrix.T)        # covariance matrix
        e, EV = linalg.eigh(C)              # eigenvalues and eigenvectors
        pc = np.dot(EV.T, matrix)           # PCs using a compact trick when cov is MM'
        V = pc[::-1]                        # reverse since last eigenvectors are the ones we want
        S = np.sqrt(e)[::-1]                # reverse since eigenvalues are in increasing order
        if debug: reconstruction(ncomp, None, S, None)
        for i in range(V.shape[1]):
            V[:, i] /= S                    # scaling by the square root of eigenvalues
        V = V[:ncomp]
        if verbose: print('Done PCA with numpy linalg eigh functions')

    elif mode == 'lapack':
        # n_frames is usually smaller than n_pixels. In this setting taking the SVD of M'
        # and keeping the left (transposed) SVs is faster than taking the SVD of M (right SVs)
        U, S, V = linalg.svd(matrix.T, full_matrices=False)
        if debug: reconstruction(ncomp, U, S, V)
        V = V[:ncomp]                       # we cut projection matrix according to the # of PCs
        U = U[:, :ncomp]
        S = S[:ncomp]
        if verbose: print('Done SVD/PCA with numpy SVD (LAPACK)')

    elif mode == 'arpack':
        U, S, V = svds(matrix, k=ncomp)
        if debug: reconstruction(ncomp, U, S, V, -1)
        if verbose: print('Done SVD/PCA with scipy sparse SVD (ARPACK)')

    elif mode == 'randsvd':
        U, S, V = randomized_svd(matrix, n_components=ncomp, n_iter=2,
                                 transpose='auto', random_state=None)
        if debug: reconstruction(ncomp, U, S, V)
        if verbose: print('Done SVD/PCA with randomized SVD')

    elif mode == 'cupy':
        if no_cupy: raise RuntimeError('Cupy is not installed')
        a_gpu = cupy.array(matrix)
        a_gpu = cupy.asarray(a_gpu)  # move the data to the current device
        u_gpu, s_gpu, vh_gpu = cupy.linalg.svd(a_gpu, full_matrices=True,
                                               compute_uv=True)
        V = vh_gpu[:ncomp]
        V = cupy.asnumpy(V)
        if usv:
            S = s_gpu[:ncomp]
            S = cupy.asnumpy(S)
            U = u_gpu[:, :ncomp]
            U = cupy.asnumpy(U)
        if verbose: print('Done SVD/PCA with cupy (GPU)')

    elif mode == 'randcupy':
        if no_cupy: raise RuntimeError('Cupy is not installed')
        U, S, V = randomized_svd_gpu(matrix, ncomp, n_iter=2)
        V = cupy.asnumpy(V)
        S = cupy.asnumpy(S)
        U = cupy.asnumpy(U)
        if debug: reconstruction(ncomp, U, S, V)
        if verbose: print('Done randomized SVD/PCA with cupy (GPU)')

    elif mode == 'eigencupy':
        if no_cupy: raise RuntimeError('Cupy is not installed')
        a_gpu = cupy.array(matrix)
        a_gpu = cupy.asarray(a_gpu)         # move the data to the current device
        C = cupy.dot(a_gpu, a_gpu.T)        # covariance matrix
        e, EV = cupy.linalg.eigh(C)         # eigenvalues and eigenvectors
        pc = cupy.dot(EV.T, a_gpu)          # PCs using a compact trick when cov is MM'
        V = pc[::-1]                        # reverse since last eigenvectors are the ones we want
        S = cupy.sqrt(e)[::-1]              # reverse since eigenvalues are in increasing order
        if debug: reconstruction(ncomp, None, S, None)
        for i in range(V.shape[1]):
            V[:, i] /= S                    # scaling by the square root of eigenvalues
        V = V[:ncomp]
        V = cupy.asnumpy(V)
        S = cupy.asnumpy(S)
        if verbose: print('Done PCA with cupy eigh function (GPU)')

    else:
        raise ValueError('The SVD mode is not available')

    if usv:
        if mode == 'lapack':
            return V.T, S, U.T
        else:
            return U, S, V
    else:
        if mode == 'lapack':
            return U.T
        else:
            return V



def randomized_svd_gpu(M, n_components, n_oversamples=10, n_iter='auto',
                       transpose='auto', random_state=0):
    """Computes a truncated randomized SVD on GPU. Adapted from Sklearn.

    Parameters
    ----------
    M : ndarray or sparse matrix
        Matrix to decompose
    n_components : int
        Number of singular values and vectors to extract.
    n_oversamples : int (default is 10)
        Additional number of random vectors to sample the range of M so as
        to ensure proper conditioning. The total number of random vectors
        used to find the range of M is n_components + n_oversamples. Smaller
        number can improve speed but can negatively impact the quality of
        approximation of singular vectors and singular values.
    n_iter : int or 'auto' (default is 'auto')
        Number of power iterations. It can be used to deal with very noisy
        problems. When 'auto', it is set to 4, unless `n_components` is small
        (< .1 * min(X.shape)) `n_iter` in which case is set to 7.
        This improves precision with few components.
    transpose : True, False or 'auto' (default)
        Whether the algorithm should be applied to M.T instead of M. The
        result should approximately be the same. The 'auto' mode will
        trigger the transposition if M.shape[1] > M.shape[0] since this
        implementation of randomized SVD tend to be a little faster in that
        case.
    random_state : int, RandomState instance or None, optional (default=None)
        The seed of the pseudo random number generator to use when shuffling
        the data.  If int, random_state is the seed used by the random number
        generator; If RandomState instance, random_state is the random number
        generator; If None, the random number generator is the RandomState
        instance used by `np.random`.

    Notes
    -----
    This algorithm finds a (usually very good) approximate truncated
    singular value decomposition using randomization to speed up the
    computations. It is particularly fast on large matrices on which
    you wish to extract only a small number of components. In order to
    obtain further speed up, `n_iter` can be set <=2 (at the cost of
    loss of precision).

    References
    ----------
    * Finding structure with randomness: Stochastic algorithms for constructing
      approximate matrix decompositions
      Halko, et al., 2009 http://arxiv.org/abs/arXiv:0909.4061
    * A randomized algorithm for the decomposition of matrices
      Per-Gunnar Martinsson, Vladimir Rokhlin and Mark Tygert
    * An implementation of a randomized algorithm for principal component
      analysis
      A. Szlam et al. 2014
    """
    random_state = check_random_state(random_state)
    n_random = n_components + n_oversamples
    n_samples, n_features = M.shape

    if n_iter == 'auto':
        # Checks if the number of iterations is explicitly specified
        n_iter = 7 if n_components < .1 * min(M.shape) else 4

    if transpose == 'auto':
        transpose = n_samples < n_features
    if transpose: M = M.T       # this implementation is a bit faster with smaller shape[1]

    M = cupy.array(M)
    M = cupy.asarray(M)

    # Generating normal random vectors with shape: (M.shape[1], n_random)
    Q = random_state.normal(size=(M.shape[1], n_random))
    Q = cupy.array(Q)
    Q = cupy.asarray(Q)

    # Perform power iterations with Q to further 'imprint' the top
    # singular vectors of M in Q
    for i in range(n_iter):
        Q = cupy.dot(M, Q)
        Q = cupy.dot(M.T, Q)

    # Sample the range of M using by linear projection of Q. Extract an orthonormal basis
    Q, _ = cupy.linalg.qr(cupy.dot(M, Q), mode='reduced')

    # project M to the (k + p) dimensional space using the basis vectors
    B = cupy.dot(Q.T, M)

    B = cupy.array(B)
    Q = cupy.array(Q)
    # compute the SVD on the thin matrix: (k + p) wide
    Uhat, s, V = cupy.linalg.svd(B, full_matrices=False, compute_uv=True)
    del B
    U = cupy.dot(Q, Uhat)

    if transpose:
        # transpose back the results according to the input convention
        return V[:n_components, :].T, s[:n_components], U[:, :n_components].T
    else:
        return U[:, :n_components], s[:n_components], V[:n_components, :]

