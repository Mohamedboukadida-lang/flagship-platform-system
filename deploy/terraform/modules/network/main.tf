# One VPC, one public subnet, one security group. The node is reached on 80 and 443 only;
# there is no SSH (administration goes through Systems Manager).

variable "name" {
  type = string
}

variable "cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "availability_zone" {
  type = string
}

resource "aws_vpc" "this" {
  #checkov:skip=CKV2_AWS_11:Flow logs cost money and nothing reads them on a single-node demo
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}

# The default group allows everything between its members. Adopting it with no rules closes it.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr, 8, 0)
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "node" {
  #checkov:skip=CKV2_AWS_5:Attached to the instance in modules/node; the check cannot follow module outputs
  name        = "${var.name}-node"
  description = "Demo node: web traffic in, package and API traffic out"
  vpc_id      = aws_vpc.this.id
  tags        = { Name = "${var.name}-node" }
}

# Wildcard source, justified: this is a public demo site. Port 80 is needed for the
# Let's Encrypt HTTP-01 challenge.
resource "aws_vpc_security_group_ingress_rule" "web" {
  #checkov:skip=CKV_AWS_260:Port 80 must be public for the ACME HTTP-01 challenge
  for_each          = { http = 80, https = 443 }
  security_group_id = aws_security_group.node.id
  description       = "Public ${each.key}"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

# Outbound web only: OS packages, container images, AWS APIs, ACME.
resource "aws_vpc_security_group_egress_rule" "web" {
  for_each          = { http = 80, https = 443 }
  security_group_id = aws_security_group.node.id
  description       = "Outbound ${each.key}"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

output "subnet_id" {
  value = aws_subnet.public.id
}

output "security_group_id" {
  value = aws_security_group.node.id
}
