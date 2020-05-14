from onecodex.exceptions import OneCodexException
from onecodex.lib.enums import AbundanceField, Rank, Field
from onecodex.viz._primitives import sort_helper


class VizBargraphMixin(object):
    def plot_bargraph(
        self,
        rank=Rank.Auto,
        normalize="auto",
        top_n="auto",
        threshold="auto",
        title=None,
        xlabel=None,
        ylabel=None,
        tooltip=None,
        return_chart=False,
        haxis=None,
        legend="auto",
        label=None,
        sort_x=None,
        include_taxa_missing_rank=None,
        include_other=False,
        width=None,
        height=None,
    ):
        """Plot a bargraph of relative abundance of taxa for multiple samples.

        Parameters
        ----------
        rank : {'auto', 'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species'}, optional
            Analysis will be restricted to abundances of taxa at the specified level.
        normalize : 'auto' or `bool`, optional
            Convert read counts to relative abundances such that each sample sums to 1.0. Setting
            'auto' will choose automatically based on the data.
        return_chart : `bool`, optional
            When True, return an `altair.Chart` object instead of displaying the resulting plot in
            the current notebook.
        top_n : `int`, optional
            Display the top N most abundant taxa in the entire cohort of samples.
        threshold : `float`
            Display only taxa that are more abundant that this threshold in one or more samples.
        title : `string`, optional
            Text label at the top of the plot.
        xlabel : `string`, optional
            Text label along the horizontal axis.
        ylabel : `string`, optional
            Text label along the vertical axis.
        tooltip : `string` or `list`, optional
            A string or list containing strings representing metadata fields. When a point in the
            plot is hovered over, the value of the metadata associated with that sample will be
            displayed in a modal.
        haxis : `string`, optional
            The metadata field (or tuple containing multiple categorical fields) used to group
            samples together.
        legend: `string`, optional
            Title for color scale. Defaults to the field used to generate the plot, e.g.
            readcount_w_children or abundance.
        label : `string` or `callable`, optional
            A metadata field (or function) used to label each analysis. If passing a function, a
            dict containing the metadata for each analysis is passed as the first and only
            positional argument. The callable function must return a string.
        sort_x : `list` or `callable`, optional
            Either a list of sorted labels or a function that will be called with a list of x-axis labels
            as the only argument, and must return the same list in a user-specified order.
        include_no_level : `bool`, optional
            Whether or not a row should be plotted for taxa that do not have a designated parent at `rank`.

        Examples
        --------
        Plot a bargraph of the top 10 most abundant genera

        >>> plot_bargraph(rank='genus', top_n=10)
        """
        # Deferred imports
        import altair as alt

        if rank is None:
            raise OneCodexException("Please specify a rank or 'auto' to choose automatically")

        if not (threshold or top_n):
            raise OneCodexException("Please specify at least one of: threshold, top_n")

        if top_n == "auto" and threshold == "auto":
            top_n = 10
            threshold = None
        elif top_n == "auto" and threshold != "auto":
            top_n = None
        elif top_n != "auto" and threshold == "auto":
            threshold = None

        df = self.to_df(rank=rank, normalize=normalize, threshold=threshold)

        field = df.ocx.field

        if self._field in AbundanceField.values() and include_taxa_missing_rank is None:
            include_taxa_missing_rank = True

        if include_taxa_missing_rank:
            if field != Field.AbundanceWChildren:
                raise OneCodexException(
                    "No-level data can only be imputed on abundances w/ children"
                )

            name = "No {}".format(rank)

            df[name] = 1 - df.sum(axis=1)

        top_n = df.mean().sort_values(ascending=False).iloc[:top_n].index

        df = df[top_n]

        if include_other and normalize:
            df["Other"] = 1 - df.sum(axis=1)

        if legend == "auto":
            legend = field

        if tooltip:
            if not isinstance(tooltip, list):
                tooltip = [tooltip]
        else:
            tooltip = []

        if haxis:
            tooltip.append(haxis)

        tooltip.insert(0, "Label")

        # takes metadata columns and returns a dataframe with just those columns
        # renames columns in the case where columns are taxids
        magic_metadata, magic_fields = self._metadata_fetch(tooltip, label=label)

        df = df.join(magic_metadata)

        df = df.reset_index().melt(
            id_vars=["classification_id"] + magic_metadata.columns.tolist(),
            var_name="tax_id",
            value_name=field,
        )

        # add taxa names
        df["tax_name"] = df["tax_id"].apply(
            lambda t: "{} ({})".format(self.taxonomy["name"][t], t)
            if t in self.taxonomy["name"]
            else t
        )

        #
        # TODO: how to sort bars in bargraph
        # - abundance (mean across all samples)
        # - parent taxon (this will require that we make a few assumptions
        # about taxonomic ranks but as all taxonomic data will be coming from
        # OCX this should be okay)
        #

        ylabel = ylabel or field
        xlabel = xlabel or ""

        # should ultimately be Label, tax_name, readcount_w_children, then custom fields
        tooltip_for_altair = [magic_fields[f] for f in tooltip]
        tooltip_for_altair.insert(1, "tax_name")
        tooltip_for_altair.insert(2, "{}:Q".format(field))

        kwargs = {}

        if haxis:
            kwargs["column"] = haxis

        domain = sorted(df["tax_name"].unique())

        no_level_name = "No {}".format(rank)
        if include_taxa_missing_rank and no_level_name in domain:
            domain.remove(no_level_name)
            domain += [no_level_name]

        if include_other:
            domain.remove("Other")
            domain += ["Other"]

        sort_order = sort_helper(sort_x, df["Label"].tolist())

        df["order"] = df["tax_name"].apply(domain.index)

        y_scale_kwargs = {"zero": True, "nice": False}
        if normalize:
            y_scale_kwargs["domain"] = [0, 1]

        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("Label", axis=alt.Axis(title=xlabel), sort=sort_order),
                y=alt.Y(field, axis=alt.Axis(title=ylabel), scale=alt.Scale(**y_scale_kwargs)),
                color=alt.Color("tax_name", legend=alt.Legend(title=legend), sort=domain),
                tooltip=tooltip_for_altair,
                href="url:N",
                order=alt.Order("order", sort="descending"),
                **kwargs
            )
        )

        if haxis:
            chart = chart.resolve_scale(x="independent")

        props = {}

        if title:
            props["title"] = title
        if width:
            props["width"] = width
        if height:
            props["height"] = height

        if props:
            chart = chart.properties(**props)

        return chart if return_chart else chart.display()
