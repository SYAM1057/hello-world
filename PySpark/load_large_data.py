from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType  # Import types as needed

# Initialize SparkSession with configurations for large data
spark = SparkSession.builder \
    .appName("EfficientDataLoader") \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .getOrCreate()

# Define the path to your 10GB data file (replace with actual path)
file_path = "path/to/your/10gb_file"  # e.g., "/data/large_file.parquet" or "/data/large_file.csv"

# Option 1: Loading Parquet file (recommended for efficiency)
def load_parquet_efficiently(file_path):
    """
    Load a Parquet file efficiently.
    Parquet is columnar, compressed, and supports predicate pushdown.
    """
    df = spark.read.parquet(file_path)
    # Repartition to optimize for your cluster/core count (adjust number based on available cores)
    df = df.repartition(100)  # Example: repartition to 100 partitions
    return df

# Option 2: Loading CSV file efficiently
def load_csv_efficiently(file_path, schema=None):
    """
    Load a CSV file efficiently.
    Define schema to avoid inferSchema which can be slow on large files.
    """
    if schema is None:
        # Example schema - replace with your actual schema
        schema = StructType([
            StructField("column1", StringType(), True),
            StructField("column2", IntegerType(), True),
            StructField("column3", DoubleType(), True),
            # Add more fields as needed
        ])

    df = spark.read \
        .option("header", "true") \
        .option("sep", ",") \
        .option("inferSchema", "false") \
        .schema(schema) \
        .csv(file_path)

    # Repartition to optimize
    df = df.repartition(100)
    return df

# Example usage:
# For Parquet
# df = load_parquet_efficiently(file_path)

# For CSV
# df = load_csv_efficiently(file_path)

# After loading, you can perform operations
# df.show()
# df.count()  # This will trigger computation

# Don't forget to stop the session when done
# spark.stop()</content>
>parameter name="filePath">d:\Github_Syam\hello-world\PySpark\load_large_data.py