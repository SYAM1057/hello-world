from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

# Initialize SparkSession with Hive support
spark = SparkSession.builder \
    .appName("LoadMultipleCSVsIntoHive") \
    .config("spark.sql.warehouse.dir", "/user/hive/warehouse") \
    .enableHiveSupport() \
    .getOrCreate()

# Replace with the directory or glob path containing all CSV files
csv_path = "hdfs:///data/csv_files/*.csv"  # or local file path: "file:///d:/data/csv_files/*.csv"

# Define the schema for the CSV files to avoid expensive inference
schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("name", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("category", StringType(), True),
    # Add/replace fields to match your file columns
])

# Optional: Hive database and table names
hive_database = "analytics_db"
hive_table = "sales_csv"
full_table_name = f"{hive_database}.{hive_table}"

# Create database if needed
spark.sql(f"CREATE DATABASE IF NOT EXISTS {hive_database}")

# Read all CSV files in the specified path
csv_df = spark.read \
    .option("header", "true") \
    .option("inferSchema", "false") \
    .option("mode", "DROPMALFORMED") \
    .option("sep", ",") \
    .schema(schema) \
    .csv(csv_path)

# Optional repartition for write efficiency
csv_df = csv_df.repartition(100)

# Write into Hive table in append mode
csv_df.write \
    .mode("append") \
    .format("hive") \
    .saveAsTable(full_table_name)

print(f"Loaded CSV files from {csv_path} into Hive table {full_table_name}")

spark.stop()