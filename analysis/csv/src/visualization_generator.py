"""Visualization generation for NBA CSV analysis."""

import logging
import os
from pathlib import Path
from typing import List, no_type_check

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import seaborn as sns

# Get logger from main module for consistent logging
logger = logging.getLogger('csv_analysis')


class VisualizationGenerator:
    """Generates visualizations for NBA CSV data analysis."""

    def __init__(self, df: pl.DataFrame, csv_name: str, output_dir: Path):
        """
        Initialize the visualization generator.

        Args:
            df: Polars DataFrame containing the data
            csv_name: Name of the CSV file (without extension)
            output_dir: Directory to save visualizations
        """
        self.df = df
        self.csv_name = csv_name
        self.output_dir = output_dir

    @no_type_check
    def generate_visualizations(self) -> List[str]:
        """Generate visualizations for the dataset."""
        logger.info(f"Starting visualization generation for {self.csv_name}...")
        logger.debug(f"DataFrame shape: {self.df.shape}, Output dir: {self.output_dir}")
        
        if os.getenv("SKIP_VISUALIZATIONS") == "1":
            logger.info("Skipping visualizations due to SKIP_VISUALIZATIONS=1")
            return []

        # Skip for large datasets
        if len(self.df.columns) > 50 or len(self.df) > 100000:
            logger.info(
                f"Skipping visualizations for large dataset: "
                f"{len(self.df)} rows, {len(self.df.columns)} columns"
            )
            return []

        logger.info(
            f"Generating visualizations for {self.csv_name} "
            f"({len(self.df)} rows, {len(self.df.columns)} columns)..."
        )

        saved_plots: List[str] = []

        try:
            # Set up the plotting style
            plt.style.use("seaborn-v0_8")
            sns.set_palette("husl")

            # 1. Missing data visualization
            saved_plots.extend(self._generate_missing_data_plot())

            # 2. Correlation heatmap
            saved_plots.extend(self._generate_correlation_heatmap())

            # 3. Distribution plots
            saved_plots.extend(self._generate_distribution_plots())

            logger.info(f"Generated {len(saved_plots)} visualizations")

        except Exception as e:
            logger.error(f"Failed to generate visualizations: {e}")

        return saved_plots

    @no_type_check
    def _generate_missing_data_plot(self) -> List[str]:
        """Generate missing data visualization."""
        saved_plots: List[str] = []

        if len(self.df.columns) <= 50:  # Only for smaller datasets
            plt.figure(figsize=(12, 8))
            missing_data_df = self.df.null_count().to_pandas()
            missing_data = missing_data_df.iloc[0]
            if missing_data.sum() > 0:
                sns.barplot(
                    x=missing_data.index,
                    y=missing_data.values,
                )
                plt.xticks(rotation=45, ha="right")
                plt.title(f"Missing Data by Column - {self.csv_name}")
                plt.ylabel("Missing Values Count")
                plt.tight_layout()

                plot_path = self.output_dir / f"{self.csv_name}_missing_data.png"
                plt.savefig(plot_path, dpi=72, bbox_inches="tight")
                saved_plots.append(str(plot_path))
                plt.close()
        return saved_plots

    @no_type_check
    def _generate_correlation_heatmap(self) -> List[str]:
        """Generate correlation heatmap for numeric columns."""
        saved_plots: List[str] = []
        saved_plots: List[str] = []

        numeric_cols = [
            col
            for col in self.df.columns
            if self.df[col].dtype in [pl.Int64, pl.Float64]
        ]

        if len(numeric_cols) > 1 and len(numeric_cols) <= 20:
            plt.figure(figsize=(10, 8))
            corr_matrix = self.df.select(numeric_cols).to_pandas().corr()

            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
            sns.heatmap(
                corr_matrix,
                mask=mask,
                annot=True,
                cmap="coolwarm",
                center=0,
                square=True,
                linewidths=0.5,
                cbar_kws={"shrink": 0.5},
            )
            plt.title(f"Correlation Matrix - {self.csv_name}")
            plt.tight_layout()

            plot_path = self.output_dir / f"{self.csv_name}_correlation.png"
            plt.savefig(plot_path, dpi=72, bbox_inches="tight")
            saved_plots.append(str(plot_path))
        return saved_plots

    @no_type_check
    def _generate_distribution_plots(self) -> List[str]:
        """Generate distribution plots for key metrics."""
        saved_plots: List[str] = []
        """Generate distribution plots for key metrics."""
        saved_plots: List[str] = []

        key_metrics = ["PTS", "FG_PCT", "TS_PCT", "PER", "REB", "AST"]
        existing_metrics = [col for col in key_metrics if col in self.df.columns]

        if existing_metrics:
            n_metrics = len(existing_metrics)
            n_cols = min(3, n_metrics)
            n_rows = (n_metrics + n_cols - 1) // n_cols

            fig, axes = plt.subplots(
                n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows)
            )
            # Use fig to avoid "Variable not accessed" warning
            _ = fig  # Mark as used
            if n_rows == 1:
                axes = axes.reshape(1, -1)
            elif n_cols == 1:
                axes = axes.reshape(-1, 1)

            for i, metric in enumerate(existing_metrics):
                row, col = i // n_cols, i % n_cols
                ax = axes[row, col] if n_rows > 1 and n_cols > 1 else axes[i]

                data = self.df[metric].drop_nulls().to_list()
                if len(data) > 0:
                    sns.histplot(x=data, ax=ax, kde=True, bins=30)
                    ax.set_title(f"{metric} Distribution")
                    ax.set_xlabel(metric)

            # Hide empty subplots
            for i in range(len(existing_metrics), n_rows * n_cols):
                row, col = i // n_cols, i % n_cols
                ax = axes[row, col] if n_rows > 1 and n_cols > 1 else axes[i]
                ax.set_visible(False)

            plt.tight_layout()
            plot_path = self.output_dir / f"{self.csv_name}_distributions.png"
            plt.savefig(plot_path, dpi=72, bbox_inches="tight")
            saved_plots.append(str(plot_path))
            plt.close()

        return saved_plots
