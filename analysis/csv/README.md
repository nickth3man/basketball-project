# NBA CSV Analysis System

A comprehensive data validation and profiling tool specifically designed for basketball-related CSV files. This system provides multi-layered validation, data quality assessment, and detailed reporting with basketball-specific business rules and domain expertise.

## 🏀 System Overview

The NBA CSV Analysis System is a sophisticated Python-based tool that performs comprehensive analysis of NBA CSV files through multiple validation layers:

- **Data Profiling**: Uses ydata-profiling for in-depth statistical analysis
- **Validation**: Multi-layered validation including frictionless and basketball-specific rules  
- **Quality Metrics**: Calculates completeness, uniqueness, and validity scores
- **Visualizations**: Generates correlation heatmaps, distribution plots, and missing data charts
- **Parallel Processing**: Supports multi-file analysis with configurable workers
- **Performance Optimizations**: Memory management and selective processing for large datasets

## 📁 Project Structure

```text
analysis/csv/
├── src/                          # Source code
│   ├── csv_analysis.py          # Main analysis script
│   ├── basketball_validator.py  # Basketball-specific validation rules
│   ├── data_quality_analyzer.py # Data quality assessment
│   ├── visualization_generator.py # Charts and plots generation
│   ├── csv_type_inferrer.py     # CSV type detection
│   ├── report_generator.py      # HTML/JSON report generation
│   └── analysis_types.py        # Shared type definitions
├── output/                       # Analysis results and reports
├── csv_files/                    # Input CSV files (example)
└── README.md                     # This documentation
```

### Module Descriptions

- **`csv_analysis.py`**: Main orchestrator script that coordinates the analysis pipeline
- **`basketball_validator.py`**: Implements basketball-specific validation rules (shooting logic, efficiency ranges, etc.)
- **`data_quality_analyzer.py`**: Calculates completeness, uniqueness, and validity metrics
- **`visualization_generator.py`**: Generates correlation heatmaps, distribution plots, and missing data charts
- **`csv_type_inferrer.py`**: Automatically detects CSV types based on filename patterns
- **`report_generator.py`**: Creates HTML and JSON summary reports with frictionless validation
- **`analysis_types.py`**: Defines shared TypedDict classes for consistent data structures

## 🚀 Key Features

### Basketball-Specific Validation

- **Shooting Logic**: Validates FGM ≤ FGA, FTM ≤ FTA, 3PM ≤ 3PA
- **Efficiency Ranges**: Checks FG%, TS%, EFG% within reasonable bounds
- **PER Analysis**: Validates Player Efficiency Rating in realistic ranges (0-40)
- **Score Validation**: Ensures PTS ≈ 2×FGM + FTM + 3×FG3M
- **Game Logic**: Validates positive scores, proper game structure

### Data Quality Assessment

- **Completeness Score**: Measures data availability across columns
- **Uniqueness Score**: Identifies duplicate records
- **Validity Score**: Based on validation rule success rate
- **Type Validation**: Ensures appropriate data types
- **Constraint Validation**: Checks logical relationships

### Advanced Analytics

- **Statistical Profiling**: Comprehensive data distribution analysis
- **Correlation Analysis**: Identifies relationships between variables
- **Missing Data Patterns**: Visualizes and quantifies data gaps
- **Distribution Analysis**: Histograms and density plots for key metrics

## 📋 Installation Requirements

### System Dependencies

- Python 3.8 or higher
- At least 4GB RAM (8GB recommended for large datasets)

### Python Dependencies

Install the required packages using pip:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install \
    polars>=0.37.0 \
    ydata-profiling>=4.6.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    numpy>=1.24.0 \
    frictionless>=5.4.0 \
    scikit-learn>=1.3.0
```

### Optional Dependencies for Enhanced Functionality

```bash
pip install \
    plotly>=5.15.0 \
    kaleido>=0.2.1 \
    psutil>=5.9.0
```

## ⚡ Quick Start

### Basic Usage

```bash
# Single file analysis
python src/csv_analysis.py --csv-path ../csv_files/game.csv --output-dir ./reports

# Analyze all CSV files in directory
python src/csv_analysis.py --all-csvs --csv-dir ../csv_files --output-dir ./reports
```

### Advanced Usage

```bash
# Batch processing with parallel workers
python src/csv_analysis.py --all-csvs --max-workers 4 --output-dir ./reports

# Minimal mode for large datasets
python src/csv_analysis.py --all-csvs --minimal --max-workers 2

# Resume interrupted processing
python src/csv_analysis.py --all-csvs --resume --output-dir ./reports
```

## 📖 Detailed Usage

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--csv-path` | Path to single CSV file | None |
| `--csv-dir` | Directory containing CSV files | `../csv_files` |
| `--all-csvs` | Analyze all CSV files in directory | False |
| `--output-dir` | Output directory for reports | `analysis/csv/output` |
| `--minimal` | Run in minimal mode (skip heavy operations) | False |
| `--max-workers` | Maximum parallel workers | 2 |
| `--resume` | Skip already processed files | False |

### Examples

#### 1. Single File Analysis

```bash
python src/csv_analysis.py --csv-path ../csv_files/player_stats.csv --output-dir ./reports
```

#### 2. Batch Analysis with Performance Tuning

```bash
python src/csv_analysis.py --all-csvs --csv-dir ../csv_files --output-dir ./reports --max-workers 4
```

#### 3. Large Dataset Processing

```bash
python src/csv_analysis.py --all-csvs --minimal --max-workers 2 --output-dir ./reports
```

#### 4. Resume Processing

```bash
python src/csv_analysis.py --all-csvs --resume --output-dir ./reports
```

## 📊 Output Formats

The system generates multiple output formats for comprehensive analysis:

### 1. Summary Reports

- **JSON Format**: `filename_summary_report.json` - Machine-readable analysis results
- **HTML Format**: `filename_summary_report.html` - Human-readable formatted report

### 2. Validation Reports

- **Basketball Validation**: `filename_basketball_validation.json` - Sport-specific validation results
- **Frictionless Validation**: `filename_frictionless_validation.json` - Data structure validation

### 3. Quality Metrics

- **Quality Metrics**: `filename_quality_metrics.json` - Data quality scores and statistics

### 4. Profile Reports

- **Data Profile**: `filename_profile.html` - Comprehensive statistical analysis with ydata-profiling

### 5. Visualizations

- **Missing Data Plot**: `filename_missing_data.png` - Bar chart of missing values
- **Correlation Heatmap**: `filename_correlation.png` - Variable correlation matrix
- **Distribution Plots**: `filename_distributions.png` - Histograms of key metrics

### 6. Directory Structure

```text
output/
├── filename1/
│   ├── filename1_summary_report.json
│   ├── filename1_summary_report.html
│   ├── filename1_basketball_validation.json
│   ├── filename1_frictionless_validation.json
│   ├── filename1_quality_metrics.json
│   ├── filename1_profile.html
│   ├── filename1_missing_data.png
│   ├── filename1_correlation.png
│   └── filename1_distributions.png
└── filename2/
    └── ... (same structure)
```

## ⚙️ Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SKIP_PROFILE` | Skip ydata-profiling generation | `0` |
| `SKIP_FRICTIONLESS` | Skip frictionless validation | `0` |
| `SKIP_VISUALIZATIONS` | Skip plot generation | `0` |

### CSV Type Detection

The system automatically detects CSV types based on filename patterns:

| Pattern | Type | Description |
|---------|------|-------------|
| `game*` | `game_info` | Game-level statistics |
| `player*` | `player_stats` | Player performance data |
| `team*` | `team_stats` | Team-level statistics |
| `play_by_play` | `play_by_play` | Event-by-event data |
| `draft*` | `draft_combine` | Draft combine measurements |
| `inactive*` | `inactive_players` | Inactive player data |
| `officials` | `officials` | Referee information |

## 🏀 Basketball-Specific Validation Rules

### Shooting Statistics Logic

- **Field Goals**: `FGM ≤ FGA` (Made shots cannot exceed attempted)
- **Free Throws**: `FTM ≤ FTA` (Made free throws cannot exceed attempted)  
- **Three Pointers**: `FG3M ≤ FG3A` (Made 3-pointers cannot exceed attempted)

### Efficiency Metrics Ranges

- **Field Goal Percentage**: `0 ≤ FG_PCT ≤ 1` (0% to 100%)
- **True Shooting Percentage**: `0.2 ≤ TS_PCT ≤ 0.8` (20% to 80%)
- **Effective Field Goal Percentage**: `0 ≤ EFG_PCT ≤ 1` (0% to 100%)

### Advanced Statistics

- **Player Efficiency Rating**: `0 ≤ PER ≤ 40` (Realistic NBA range)
- **Box Plus/Minus**: Reasonable statistical bounds
- **Value Over Replacement Player**: Contextual limits

### Score Validation

- **Point Calculation**: `PTS ≈ 2×FGM + FTM + 3×FG3M`
- **Game Scores**: Positive values only
- **Point Differentials**: Logical consistency checks

### Game Structure

- **Quarter Progression**: Temporal consistency in play-by-play
- **Score Progression**: Points change appropriately with events
- **Player Participation**: Substitution patterns make sense

## 🚀 Performance Considerations

### Memory Management

- **Polars Backend**: Uses efficient columnar processing
- **Garbage Collection**: Automatic memory cleanup between operations
- **Large Dataset Handling**: Automatic skipping of heavy operations for datasets >100k rows

### Processing Optimization

- **Parallel Workers**: Configurable concurrent file processing
- **Minimal Mode**: Skips resource-intensive operations
- **Selective Processing**: Only generates necessary outputs

### Recommended Settings

| Dataset Size | Workers | Mode | Memory |
|--------------|---------|------|---------|
| < 10k rows | 2-4 | Normal | 4GB |
| 10k-100k rows | 2-4 | Normal | 8GB |
| > 100k rows | 1-2 | Minimal | 8GB+ |

### Performance Tips

1. **Use Minimal Mode** for very large datasets
2. **Limit Workers** based on available CPU cores
3. **Monitor Memory Usage** during batch processing
4. **Resume Processing** to avoid reprocessing completed files

## 🔧 Troubleshooting

### Common Issues

#### 1. Memory Errors

```bash
# Solution: Use minimal mode
python src/csv_analysis.py --all-csvs --minimal --max-workers 1
```

#### 2. Import Errors

```bash
# Solution: Install missing dependencies
pip install ydata-profiling frictionless polars
```

#### 3. Large File Processing

```bash
# Solution: Increase worker timeout or reduce workers
python src/csv_analysis.py --all-csvs --max-workers 1 --minimal
```

#### 4. Permission Errors

```bash
# Solution: Check output directory permissions
mkdir -p ./output && chmod 755 ./output
```

### Error Codes and Messages

| Error Code | Description | Solution |
|------------|-------------|----------|
| `E001` | File not found | Check CSV path and permissions |
| `E002` | Invalid CSV format | Verify CSV structure and encoding |
| `E003` | Memory limit exceeded | Use minimal mode or reduce workers |
| `E004` | Missing dependencies | Install required packages |
| `E005` | Output directory error | Check write permissions |

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python src/csv_analysis.py --csv-path file.csv
```

### Log Files

Logs are written to standard output. For persistent logging:

```bash
python src/csv_analysis.py --all-csvs > analysis.log 2>&1
```

## 📈 Sample Output

### Quality Metrics Example

```text
Completeness Score: 94.7%
Uniqueness Score: 99.8% 
Validity Score: 87.2%
Duplicate Rows: 12 (0.2%)
```

### Validation Results Example

```text
Basketball Validations:
✓ Shooting Logic: PASSED
✓ Efficiency Ranges: PASSED  
✓ PER Analysis: PASSED
✗ Score Validation: FAILED (3 discrepancies found)

Frictionless Validation:
✓ Schema Validation: PASSED
✓ Data Type Validation: PASSED
Errors: 0, Warnings: 2
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For questions, issues, or feature requests:

- Create an issue in the repository
- Check the troubleshooting section above
- Review the example outputs and configurations

---

**Note**: This system is specifically designed for NBA data analysis and may require adaptation for other basketball leagues or sports data.
