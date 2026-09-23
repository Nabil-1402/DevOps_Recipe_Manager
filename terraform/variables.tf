variable "aws_region" {
  description = "AWS region in which resources will be created"
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Name used to identify project resources"
  type        = string
  default     = "recipe-manager"
}

variable "vpc_cidr" {
  description = "IPv4 range allocated to the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "IPv4 range allocated to the public subnet"
  type        = string
  default     = "10.0.1.0/24"
}