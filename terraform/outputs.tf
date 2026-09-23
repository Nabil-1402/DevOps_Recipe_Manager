output "amazon_linux_ami_id" {
  description = "AMI ID selected for the EC2 instance"
  value       = nonsensitive(data.aws_ssm_parameter.amazon_linux_ami.value)
}