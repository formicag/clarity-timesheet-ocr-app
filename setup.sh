#!/bin/bash
# Timesheet OCR - Setup and Deployment Script

set -e  # Exit on any error

echo "============================================================"
echo "  Timesheet OCR - Setup and Deployment"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check prerequisites
echo "Step 1: Checking prerequisites..."
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install it first:"
    echo "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi
print_success "AWS CLI installed"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Run: aws configure"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_success "AWS credentials configured (Account: $ACCOUNT_ID)"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    print_error "AWS SAM CLI not found. Please install it first:"
    echo "  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi
print_success "AWS SAM CLI installed"

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.11+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python 3 installed (version $PYTHON_VERSION)"

echo ""
echo "============================================================"
echo "Step 2: Checking Bedrock model access..."
echo "============================================================"
echo ""

# Check Bedrock model access
echo "Checking if Claude Sonnet 4.5 is available..."
BEDROCK_CHECK=$(aws bedrock list-foundation-models --region us-east-1 \
    --query 'modelSummaries[?contains(modelId, `claude-sonnet-4-5`)].modelId' \
    --output text 2>&1 || echo "error")

if [[ "$BEDROCK_CHECK" == "error" ]] || [[ -z "$BEDROCK_CHECK" ]]; then
    print_warning "Claude Sonnet 4.5 not accessible in Bedrock"
    echo ""
    echo "To enable Bedrock model access:"
    echo "  1. Go to AWS Console → Amazon Bedrock"
    echo "  2. Click 'Model access' in the left sidebar"
    echo "  3. Click 'Manage model access'"
    echo "  4. Select 'Anthropic Claude Sonnet 4.5'"
    echo "  5. Click 'Save changes'"
    echo ""
    read -p "Press Enter after enabling model access, or Ctrl+C to exit..."
else
    print_success "Claude Sonnet 4.5 is accessible"
fi

echo ""
echo "============================================================"
echo "Step 3: Choose deployment option"
echo "============================================================"
echo ""

echo "Select deployment option:"
echo "  1) Simple (5 minutes) - Basic features, quick setup"
echo "  2) Production (30 minutes) - Full features, monitoring, alarms"
echo ""
read -p "Enter choice (1 or 2): " DEPLOY_CHOICE

if [[ "$DEPLOY_CHOICE" == "1" ]]; then
    TEMPLATE="template-simple.yaml"
    STACK_NAME="timesheetocr-quickstart"
    ENV="dev"
    print_success "Selected: Simple deployment"
elif [[ "$DEPLOY_CHOICE" == "2" ]]; then
    TEMPLATE="template.yaml"
    read -p "Enter stack name [timesheetocr-prod]: " STACK_NAME
    STACK_NAME=${STACK_NAME:-timesheetocr-prod}
    read -p "Enter environment (dev/staging/prod) [prod]: " ENV
    ENV=${ENV:-prod}
    read -p "Enter alarm email (optional): " ALARM_EMAIL
    print_success "Selected: Production deployment"
else
    print_error "Invalid choice. Exiting."
    exit 1
fi

echo ""
echo "============================================================"
echo "Step 4: Building application"
echo "============================================================"
echo ""

echo "Running: sam build"
sam build

print_success "Build completed"

echo ""
echo "============================================================"
echo "Step 5: Deploying to AWS"
echo "============================================================"
echo ""

if [[ "$DEPLOY_CHOICE" == "1" ]]; then
    # Simple deployment
    echo "Deploying with template-simple.yaml..."
    sam deploy \
        --template-file $TEMPLATE \
        --stack-name $STACK_NAME \
        --capabilities CAPABILITY_IAM \
        --region us-east-1 \
        --resolve-s3 \
        --parameter-overrides Environment=$ENV
else
    # Production deployment
    if [[ -n "$ALARM_EMAIL" ]]; then
        PARAMS="Environment=$ENV AlarmEmail=$ALARM_EMAIL"
    else
        PARAMS="Environment=$ENV"
    fi

    echo "Deploying with template.yaml..."
    sam deploy \
        --template-file $TEMPLATE \
        --stack-name $STACK_NAME \
        --capabilities CAPABILITY_IAM \
        --region us-east-1 \
        --resolve-s3 \
        --parameter-overrides $PARAMS
fi

print_success "Deployment completed!"

echo ""
echo "============================================================"
echo "Step 6: Getting deployment outputs"
echo "============================================================"
echo ""

# Get stack outputs
INPUT_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`InputBucketName`].OutputValue' \
    --output text)

OUTPUT_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`OutputBucketName`].OutputValue' \
    --output text)

FUNCTION_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`FunctionArn`].OutputValue' \
    --output text)

echo "Deployment details:"
echo "  Input Bucket:  $INPUT_BUCKET"
echo "  Output Bucket: $OUTPUT_BUCKET"
echo "  Function ARN:  $FUNCTION_ARN"
echo ""

# Save to config file
cat > deployment-config.txt << EOF
# Timesheet OCR Deployment Configuration
# Generated: $(date)

STACK_NAME=$STACK_NAME
INPUT_BUCKET=$INPUT_BUCKET
OUTPUT_BUCKET=$OUTPUT_BUCKET
FUNCTION_ARN=$FUNCTION_ARN
ENVIRONMENT=$ENV

# Quick commands:
# Upload timesheet:    aws s3 cp your-timesheet.png s3://$INPUT_BUCKET/
# Download CSV:        aws s3 ls s3://$OUTPUT_BUCKET/timesheets/
# View logs:           aws logs tail /aws/lambda/TimesheetOCR-ocr-$ENV --follow
EOF

print_success "Configuration saved to deployment-config.txt"

echo ""
echo "============================================================"
echo "Deployment Complete! 🎉"
echo "============================================================"
echo ""

echo "Next steps:"
echo ""
echo "1. Upload a timesheet:"
echo "   aws s3 cp 2025-10-15_20h43_56.png s3://$INPUT_BUCKET/"
echo ""
echo "2. Watch the processing (in a new terminal):"
echo "   aws logs tail /aws/lambda/TimesheetOCR-ocr-$ENV --follow"
echo ""
echo "3. Download the result:"
echo "   aws s3 ls s3://$OUTPUT_BUCKET/timesheets/"
echo "   aws s3 cp s3://$OUTPUT_BUCKET/timesheets/YYYY-MM-DD_Name_timesheet.csv ./"
echo ""
echo "For more information, see:"
echo "  - QUICKSTART.md for a quick guide"
echo "  - DEPLOYMENT_SUMMARY.md for complete documentation"
echo "  - PROJECT_SUMMARY.md for an overview"
echo ""

print_success "Setup complete!"
