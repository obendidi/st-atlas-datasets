import csv
import gzip
from pathlib import Path

import pandas as pd
import scipy.io
from scipy.sparse import coo_matrix

from st_visium_datasets.utils import get_nested_filepath


def load_feature_barcode_matrix_df(
    feature_bc_matrix_dir: Path,
) -> pd.DataFrame:
    """Feature-Barcode Matrices are a key output generated by 10x Genomics technology,
    particularly in single-cell RNA sequencing (scRNA-seq).
    They essentially represent a way to organize and quantify gene expression data
    from individual cells.

    The returned dataframe is in the following format:

    - Rows = features (genes): These refer to genes or genomic regions that are being
    measured. Each row in the dataframe represents a gene or genomic region.
    Each row contains the feature id, gene name and feature type.
    - Columns = barcodes (cells): These represent individual cells. Each column in
    the dataframe corresponds to a specific cell that was sequenced.
    - The values in the df typically represent the count of RNA molecules
    (gene expression) detected for each gene in each cell. So, each cell's column
    will have counts for the various genes in the rows.
    """
    if not feature_bc_matrix_dir.is_dir():
        raise ValueError(f"{feature_bc_matrix_dir} is not a directory")

    mat = _load_mat(feature_bc_matrix_dir)
    feature_ids, gene_names, feature_types = _load_features(feature_bc_matrix_dir)
    barcodes = _load_barcodes(feature_bc_matrix_dir)

    df: pd.DataFrame = pd.DataFrame.sparse.from_spmatrix(mat)
    df.columns = barcodes
    df.insert(loc=0, column="feature_id", value=feature_ids)
    df.insert(loc=1, column="feature_type", value=feature_types)
    df.insert(loc=2, column="gene", value=gene_names)
    df = df.set_index(["feature_id", "gene", "feature_type"])
    return df


def _load_mat(feature_bc_matrix_dir: Path) -> coo_matrix:
    """Read in MEX format matrix as table"""
    mat_path = get_nested_filepath(feature_bc_matrix_dir, "matrix.mtx.gz")
    return scipy.io.mmread(mat_path)


def _load_features(
    feature_bc_matrix_dir: Path
) -> tuple[list[str], list[str], list[str]]:
    """Read in features.tsv.gz as table
    - list of transcript/feature ids, e.g. 'ENSG00000187634'
    - list of gene names, e.g. 'RER1'
    - list of feature types, e.g. 'Gene Expression'
    """
    features_path = get_nested_filepath(feature_bc_matrix_dir, "features.tsv.gz")
    with gzip.open(features_path, "rt") as f:
        reader = csv.reader(f, delimiter="\t")
        rows = list(reader)
    feature_ids, gene_names, feature_types = zip(*rows)
    return feature_ids, gene_names, feature_types


def _load_barcodes(feature_bc_matrix_dir: Path) -> list[str]:
    """Read in barcodes.tsv.gz as table

    list of barcodes, e.g. 'AAACATACAAAACG-1'
    """
    barcodes_path = get_nested_filepath(feature_bc_matrix_dir, "barcodes.tsv.gz")
    with gzip.open(barcodes_path, "rt") as f:
        reader = csv.reader(f, delimiter="\t")
        return sum(reader, [])


def load_prove_set_df(probe_set_filepath: Path) -> pd.DataFrame:
    """Probes that are predicted to have off-target activity to homologous genes
    or sequences are excluded from analysis by default (all probes are present in
    the raw matrix file). These probes are marked with FALSE in the included column
    of the probe set reference CSV. Any gene that has at least one probe with predicted
    off-target activity will be excluded from filtered outputs. Setting filter-probes
    to false in the multi config file for cellranger multi will result in UMI counts
    from all non-deprecated probes, including those with predicted off-target activity,
    to be used in the analysis. Probes whose ID is prefixed with DEPRECATED are always
    excluded from the analysis. Please see the Probe Set Overview for details on the
    probes."""
    df = pd.read_csv(probe_set_filepath, comment="#")
    df = df.rename(columns={"gene_id": "feature_id"})
    df = df[df["included"]].drop(columns=["included"])
    return df
