# Phase 1: AWS CLI Setup Guide

If you ever want to deploy this system on another account or automate the setup without clicking through the AWS Console, you can use the AWS Command Line Interface (CLI). 

Here is the step-by-step guide to deploying Phase 1 via CLI in **PowerShell**.

## 1. Prerequisites
You must have the AWS CLI installed and configured.
Open PowerShell and run:
```powershell
aws configure
# Enter your Access Key, Secret Key, and set default region to: ap-south-1
```

## 2. Variables (Set these first!)
Replace the email address and your account ID below, then paste this entire block into PowerShell:

```powershell
$EMAIL = "your.email@example.com"
$ACCOUNT_ID = "123456789012"
$REGION = "ap-south-1"
```

## 3. Create the SNS Topic & Subscribe Email
```powershell
# Create the Topic
$TOPIC_ARN = (aws sns create-topic --name Budget-Kill-Switch-Topic --region $REGION --query 'TopicArn' --output text)
Write-Host "Topic created: $TOPIC_ARN"

# Subscribe your email
aws sns subscribe --topic-arn $TOPIC_ARN --protocol email --notification-endpoint $EMAIL --region $REGION
Write-Host "Check your email to confirm the subscription!"
```

## 4. Create the IAM Role for Lambda
*Make sure you are running these commands from inside the `aws-student-kill-switch` project folder!*

```powershell
# Create the Role
$ROLE_ARN = (aws iam create-role --role-name Lambda-Kill-Switch-Role --assume-role-policy-document file://iam/lambda-execution-role.json --query 'Role.Arn' --output text)

# Attach Basic Logging
aws iam attach-role-policy --role-name Lambda-Kill-Switch-Role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attach our custom Nuclear Policy
aws iam put-role-policy --role-name Lambda-Kill-Switch-Role --policy-name KillSwitchResourceTermination --policy-document file://iam/lambda-permissions-policy.json

Write-Host "Waiting 10 seconds for AWS to register the new role..."
Start-Sleep -Seconds 10
```

## 5. Deploy the Lambda Function
```powershell
# Zip the python code
Compress-Archive -Path lambda\heavy_hitter.py -DestinationPath lambda\function.zip -Force

# Create the function
$LAMBDA_ARN = (aws lambda create-function --function-name Nuclear-Button `
    --runtime python3.12 `
    --role $ROLE_ARN `
    --handler heavy_hitter.lambda_handler `
    --zip-file fileb://lambda\function.zip `
    --timeout 300 `
    --region $REGION --query 'FunctionArn' --output text)

# Give SNS permission to trigger the Lambda
aws lambda add-permission --function-name Nuclear-Button `
    --statement-id sns-trigger `
    --action lambda:InvokeFunction `
    --principal sns.amazonaws.com `
    --source-arn $TOPIC_ARN `
    --region $REGION

# Connect SNS to Lambda
aws sns subscribe --topic-arn $TOPIC_ARN --protocol lambda --notification-endpoint $LAMBDA_ARN --region $REGION

Write-Host "Lambda deployed and connected to SNS!"
```

## 6. Create the AWS Budget
AWS Budgets via CLI require JSON configurations. First, create a file named `budget.json`:

```json
{
    "BudgetName": "Kill-Switch-Budget",
    "BudgetLimit": { "Amount": "0.01", "Unit": "USD" },
    "TimeUnit": "DAILY",
    "BudgetType": "COST"
}
```

Then create a file named `notifications.json` (Replace `YOUR_TOPIC_ARN_HERE` with the ARN generated in step 3):
```json
[
    {
        "Notification": {
            "NotificationType": "ACTUAL",
            "ComparisonOperator": "GREATER_THAN",
            "Threshold": 100,
            "ThresholdType": "PERCENTAGE"
        },
        "Subscribers": [
            { "SubscriptionType": "SNS", "Address": "YOUR_TOPIC_ARN_HERE" }
        ]
    }
]
```

Finally, run the command to create the budget:
```powershell
aws budgets create-budget --account-id $ACCOUNT_ID --budget file://budget.json --notifications-with-subscribers file://notifications.json
Write-Host "Phase 1 Complete!"
```
