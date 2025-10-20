#!/bin/bash
set -e

# Timesheet OCR Deployment Script
# Uses Terraform for infrastructure as code

ENVIRONMENT="${1:-dev}"
ACTION="${2:-apply}"

echo "==============================================="
echo "Timesheet OCR Deployment"
echo "Environment: $ENVIRONMENT"
echo "Action: $ACTION"
echo "==============================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}ERROR: Terraform not found. Please install Terraform.${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Terraform installed${NC}"
echo -e "${GREEN}✓ AWS CLI installed${NC}"
echo -e "${GREEN}✓ AWS credentials configured${NC}"

# Check Docker is running (needed for SAM build)
if ! /Applications/Docker.app/Contents/Resources/bin/docker ps &> /dev/null; then
    echo -e "${YELLOW}Starting Docker...${NC}"
    open -a Docker
    echo "Waiting for Docker to start (30 seconds)..."
    sleep 30
fi

echo -e "${GREEN}✓ Docker running${NC}"

# Build Lambda functions with SAM
echo -e "\n${YELLOW}Building Lambda functions...${NC}"
sam build
echo -e "${GREEN}✓ Lambda functions built${NC}"

# Navigate to terraform directory
cd terraform

# Initialize Terraform (if needed)
if [ ! -d ".terraform" ]; then
    echo -e "\n${YELLOW}Initializing Terraform...${NC}"
    terraform init
    echo -e "${GREEN}✓ Terraform initialized${NC}"
fi

# Select or create workspace
echo -e "\n${YELLOW}Selecting Terraform workspace: $ENVIRONMENT${NC}"
terraform workspace select $ENVIRONMENT 2>/dev/null || terraform workspace new $ENVIRONMENT
echo -e "${GREEN}✓ Workspace selected: $ENVIRONMENT${NC}"

# Run Terraform
case $ACTION in
    plan)
        echo -e "\n${YELLOW}Running Terraform plan...${NC}"
        terraform plan -var="environment=$ENVIRONMENT"
        ;;

    apply)
        echo -e "\n${YELLOW}Running Terraform apply...${NC}"
        terraform apply -var="environment=$ENVIRONMENT"

        if [ $? -eq 0 ]; then
            echo -e "\n${GREEN}========================================${NC}"
            echo -e "${GREEN}Deployment Successful!${NC}"
            echo -e "${GREEN}========================================${NC}"

            # Show outputs
            echo -e "\n${YELLOW}Deployment Outputs:${NC}"
            terraform output

            # Get specific outputs for testing
            API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")
            INPUT_BUCKET=$(terraform output -raw input_bucket_name 2>/dev/null || echo "")

            if [ -n "$API_URL" ]; then
                echo -e "\n${YELLOW}Test your deployment:${NC}"
                echo -e "API URL: ${GREEN}$API_URL${NC}"
                echo -e "\nList resources:"
                echo -e "  ${GREEN}curl \"$API_URL/resources\"${NC}"
                echo -e "\nView report (HTML):"
                echo -e "  ${GREEN}open \"$API_URL/report/Barry%20Breden/html\"${NC}"
            fi

            if [ -n "$INPUT_BUCKET" ]; then
                echo -e "\nUpload test image:"
                echo -e "  ${GREEN}aws s3 cp Screenshots/2025-10-20_15h54_43.png s3://$INPUT_BUCKET/${NC}"
            fi
        fi
        ;;

    destroy)
        echo -e "\n${RED}WARNING: This will destroy all resources!${NC}"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            terraform destroy -var="environment=$ENVIRONMENT"
        else
            echo "Destroy cancelled."
        fi
        ;;

    output)
        terraform output
        ;;

    *)
        echo -e "${RED}ERROR: Unknown action: $ACTION${NC}"
        echo "Usage: $0 [environment] [action]"
        echo "  environment: dev, staging, or prod (default: dev)"
        echo "  action: plan, apply, destroy, or output (default: apply)"
        exit 1
        ;;
esac
