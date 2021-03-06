import pandas as pd

from onecodex.exceptions import OneCodexException
from onecodex.taxonomy import TaxonomyMixin


class DistanceMixin(TaxonomyMixin):
    def alpha_diversity(self, metric="simpson", rank="auto"):
        """Calculate the diversity within a community.

        Parameters
        ----------
        metric : {'simpson', 'chao1', 'shannon'}
            The diversity metric to calculate.
        rank : {'auto', 'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'}, optional
            Analysis will be restricted to abundances of taxa at the specified level.

        Returns
        -------
        pandas.DataFrame, a distance matrix.
        """
        import skbio.diversity

        if metric not in ("simpson", "chao1", "shannon"):
            raise OneCodexException(
                "For alpha diversity, metric must be one of: simpson, chao1, shannon"
            )

        # needs read counts, not relative abundances
        if self._guess_normalized():
            raise OneCodexException("Alpha diversity requires unnormalized read counts.")

        df = self.to_df(rank=rank, normalize=False)

        output = {"classification_id": [], metric: []}

        for c_id in df.index:
            output["classification_id"].append(c_id)
            output[metric].append(
                skbio.diversity.alpha_diversity(metric, df.loc[c_id].tolist(), [c_id]).values[0]
            )

        return pd.DataFrame(output).set_index("classification_id")

    def beta_diversity(self, metric="braycurtis", rank="auto"):
        """Calculate the diversity between two communities.

        Parameters
        ----------
        metric : {'jaccard', 'braycurtis', 'cityblock'}
            The distance metric to calculate.
        rank : {'auto', 'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'}, optional
            Analysis will be restricted to abundances of taxa at the specified level.

        Returns
        -------
        skbio.stats.distance.DistanceMatrix, a distance matrix.
        """
        import skbio.diversity

        if metric not in ("jaccard", "braycurtis", "cityblock"):
            raise OneCodexException(
                "For beta diversity, metric must be one of: jaccard, braycurtis, cityblock"
            )

        df = self.to_df(rank=rank, normalize=self._guess_normalized())

        counts = []
        for c_id in df.index:
            counts.append(df.loc[c_id].tolist())

        # NOTE: see #291 for a discussion on using these metrics with normalized read counts. we are
        # explicitly disabling skbio's check for a counts matrix to allow normalized data to make
        # its way into this function.
        return skbio.diversity.beta_diversity(metric, counts, df.index.tolist(), validate=False)

    def unifrac(self, weighted=True, rank="auto"):
        """Calculate the UniFrac beta diversity metric.

        UniFrac takes into account the relatedness of community members. Weighted UniFrac considers
        abundances, unweighted UniFrac considers presence.

        Parameters
        ----------
        weighted : `bool`
            Calculate the weighted (True) or unweighted (False) distance metric.
        rank : {'auto', 'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'}, optional
            Analysis will be restricted to abundances of taxa at the specified level.

        Returns
        -------
        skbio.stats.distance.DistanceMatrix, a distance matrix.
        """
        # needs read counts, not relative abundances
        import skbio.diversity

        if self._guess_normalized():
            raise OneCodexException("UniFrac requires unnormalized read counts.")

        df = self.to_df(rank=rank, normalize=False)

        counts = []
        for c_id in df.index:
            counts.append(df.loc[c_id].tolist())

        tax_ids = df.keys().tolist()

        tree = self.tree_build()
        tree = self.tree_prune_rank(tree, rank=df.ocx_rank)

        # there's a bug (?) in skbio where it expects the root to only have
        # one child, so we do a little faking here
        from skbio.tree import TreeNode

        new_tree = TreeNode(name="fake root")
        new_tree.rank = "no rank"
        new_tree.append(tree)

        # then finally run the calculation and return
        if weighted:
            return skbio.diversity.beta_diversity(
                "weighted_unifrac", counts, df.index.tolist(), tree=new_tree, otu_ids=tax_ids
            )
        else:
            return skbio.diversity.beta_diversity(
                "unweighted_unifrac", counts, df.index.tolist(), tree=new_tree, otu_ids=tax_ids
            )
