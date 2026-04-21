terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5"
}

provider "aws" {
  region = var.region
}

# -------------------------------------------------------------------
# EC2 인스턴스 5개
# ResourceId: aws_instance.web_1 ~ web_2, api_1 ~ api_2, ml_1
# CUR 생성기(_TERRAFORM_RESOURCES)와 반드시 일치해야 함
# -------------------------------------------------------------------

resource "aws_instance" "web_1" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium"

  tags = {
    Name    = "web_1"
    team    = "platform"
    product = "checkout"
    env     = "prod"
  }
}

resource "aws_instance" "web_2" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium"

  tags = {
    Name    = "web_2"
    team    = "platform"
    product = "checkout"
    env     = "prod"
  }
}

resource "aws_instance" "api_1" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.small"

  tags = {
    Name    = "api_1"
    team    = "data"
    product = "api"
    env     = "prod"
  }
}

resource "aws_instance" "api_2" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.small"

  tags = {
    Name    = "api_2"
    team    = "data"
    product = "api"
    env     = "prod"
  }
}

resource "aws_instance" "ml_1" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "g4dn.xlarge"

  tags = {
    Name    = "ml_1"
    team    = "ml"
    product = "recommender"
    env     = "prod"
  }
}

# -------------------------------------------------------------------
# RDS 인스턴스 2개
# ResourceId: aws_db_instance.main_1, aws_db_instance.analytics_1
# -------------------------------------------------------------------

resource "aws_db_instance" "main_1" {
  allocated_storage    = 20
  db_name              = "appdb"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.medium"
  username             = "admin"
  password             = "changeme123!"
  skip_final_snapshot  = true

  tags = {
    Name    = "main_1"
    team    = "platform"
    product = "checkout"
    env     = "prod"
  }
}

resource "aws_db_instance" "analytics_1" {
  allocated_storage    = 20
  db_name              = "analyticsdb"
  engine               = "postgres"
  engine_version       = "15"
  instance_class       = "db.t3.medium"
  username             = "analytics"
  password             = "changeme123!"
  skip_final_snapshot  = true

  tags = {
    Name    = "analytics_1"
    team    = "data"
    product = "search"
    env     = "prod"
  }
}

# -------------------------------------------------------------------
# S3 버킷 3개
# ResourceId: aws_s3_bucket.assets_1 ~ assets_3
# -------------------------------------------------------------------

resource "aws_s3_bucket" "assets_1" {
  bucket = "finops-platform-assets-1"

  tags = {
    Name    = "assets_1"
    team    = "frontend"
    product = "checkout"
    env     = "prod"
  }
}

resource "aws_s3_bucket" "assets_2" {
  bucket = "finops-platform-assets-2"

  tags = {
    Name    = "assets_2"
    team    = "data"
    product = "search"
    env     = "prod"
  }
}

resource "aws_s3_bucket" "assets_3" {
  bucket = "finops-platform-assets-3"

  tags = {
    Name    = "assets_3"
    team    = "platform"
    product = "checkout"
    env     = "prod"
  }
}
