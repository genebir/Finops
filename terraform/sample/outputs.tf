output "ec2_instance_ids" {
  description = "EC2 instance resource addresses (matches CUR ResourceId)"
  value = [
    "aws_instance.web_1",
    "aws_instance.web_2",
    "aws_instance.api_1",
    "aws_instance.api_2",
    "aws_instance.ml_1",
  ]
}

output "rds_instance_ids" {
  description = "RDS instance resource addresses (matches CUR ResourceId)"
  value = [
    "aws_db_instance.main_1",
    "aws_db_instance.analytics_1",
  ]
}

output "s3_bucket_ids" {
  description = "S3 bucket resource addresses (matches CUR ResourceId)"
  value = [
    "aws_s3_bucket.assets_1",
    "aws_s3_bucket.assets_2",
    "aws_s3_bucket.assets_3",
  ]
}
