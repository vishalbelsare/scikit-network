#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mar 3, 2019
@author: Nathan de Lara <ndelara@enst.fr>
@author: Thomas Bonald <bonald@enst.fr>
"""

import numpy as np
from scipy import sparse
from typing import Union
from sknetwork.clustering.louvain import Louvain, GreedyModularity
from sknetwork.clustering.postprocessing import reindex_clusters
from sknetwork.utils.adjacency_formats import bipartite2undirected, bipartite2directed
from sknetwork.utils.checks import check_probs, check_format, check_engine
from sknetwork.utils.algorithm_base_class import Algorithm


class BiLouvain(Algorithm):
    """
    BiLouvain algorithm for the co-clustering of biadjacency graphs in Python (default) and Numba.

    Seeks the best partition of the nodes with respect to bimodularity.

    The bimodularity of a clustering is

    :math:`Q = \\sum_{i=1}^n\\sum_{j=1}^p\\big(\\dfrac{B_{ij}}{w} -
    \\gamma \\dfrac{d_if_j}{w^2}\\big)\\delta_{c^d_i,c^f_j}`,

    where

    :math:`c^d_i` is the cluster of sample node `i` (rows of the biadjacency matrix),\n
    :math:`c^f_j` is the cluster of feature node `j` (columns of the biadjacency matrix),\n
    :math:`\\delta` is the Kronecker symbol,\n
    :math:`\\gamma \\ge 0` is the resolution parameter.


    The `force_undirected` parameter of the :class:`fit` method forces the algorithm to consider the adjacency
    as undirected, without considering its biadjacency structure.

    Parameters
    ----------
    resolution:
        Resolution parameter.
    tol:
        Minimum increase in the objective function to enter a new optimization pass.
    agg_tol:
        Minimum increase in the objective function to enter a new aggregation pass.
    max_agg_iter:
        Maximum number of aggregations.
        A negative value is interpreted as no limit.
    engine: str
        ``'default'``, ``'python'`` or ``'numba'``. If ``'default'``, tests if numba is available.
    verbose:
        Verbose mode.

    Attributes
    ----------
    labels_: np.ndarray
        Cluster index of each sample node (rows).
    feature_labels_: np.ndarray
        Cluster index of each feature node (columns).
    iteration_count_: int
        Total number of aggregations performed.
    aggregate_graph_: sparse.csr_matrix
        Aggregated adjacency at the end of the algorithm.
    score_: float
        objective function value after fit
    n_clusters_: int
        number of clusters after fit
    """

    def __init__(self, resolution: float = 1, tol: float = 1e-3, agg_tol: float = 1e-3, max_agg_iter: int = -1,
                 engine='default', verbose: bool = False):
        self.resolution = resolution
        self.tol = tol
        self.agg_tol = agg_tol
        if type(max_agg_iter) != int:
            raise TypeError('The maximum number of iterations must be an integer.')
        self.max_agg_iter = max_agg_iter
        self.engine = check_engine(engine)
        self.verbose = verbose
        self.labels_ = None
        self.feature_labels_ = None
        self.iteration_count_ = None
        self.aggregate_graph_ = None
        self.score_ = None
        self.n_clusters_ = None

    def fit(self, biadjacency: sparse.csr_matrix, weights: Union['str', np.ndarray] = 'degree',
            feature_weights: Union['str', np.ndarray] = 'degree', force_undirected: bool = False,
            sorted_cluster: bool = True):
        """
        Alternates local optimization and aggregation until convergence.

        Parameters
        ----------
        biadjacency:
            Biadjacency matrix of the graph.
        weights:
            Probabilities for the samples in the null model. ``'degree'``, ``'uniform'`` or custom weights.
        feature_weights:
            Probabilities for the features in the null model. ``'degree'``, ``'uniform'`` or custom weights.
        force_undirected:
            If True, maximizes the modularity of the undirected graph instead of the bimodularity.
        sorted_cluster:
            If True, sort labels in decreasing order of cluster size.

        Returns
        -------
        self: :class:`BiLouvain`
        """
        biadjacency = check_format(biadjacency)
        n, p = biadjacency.shape

        louvain = Louvain(GreedyModularity(self.resolution, self.tol, engine=self.engine), verbose=self.verbose)

        if force_undirected:
            adjacency = bipartite2undirected(biadjacency)
            samp_weights = check_probs(weights, biadjacency)
            feat_weights = check_probs(feature_weights, biadjacency.T)
            weights = np.hstack((samp_weights, feat_weights))
            weights = check_probs(weights, adjacency)
            louvain.fit(adjacency, weights)
        else:
            adjacency = bipartite2directed(biadjacency)
            samp_weights = np.hstack((check_probs(weights, biadjacency), np.zeros(p)))
            feat_weights = np.hstack((np.zeros(n), check_probs(feature_weights, biadjacency.T)))
            louvain.fit(adjacency, samp_weights, feat_weights)

        self.n_clusters_ = louvain.n_clusters_
        self.iteration_count_ = louvain.iteration_count_
        labels = louvain.labels_
        if sorted_cluster:
            labels = reindex_clusters(labels)
        self.labels_ = labels[:n]
        self.feature_labels_ = labels[n:]
        self.aggregate_graph_ = louvain.aggregate_graph_
        return self
