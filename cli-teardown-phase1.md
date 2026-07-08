# Phase 1: AWS CLI Teardown Guide

If you want to completely remove the Kill Switch infrastructure from your AWS account using the Command Line, follow these steps. 

This script will delete the Budget, the Lambda function, the IAM Role (and its policies), and the SNS Topic.

## 1. Variables
Replace your account ID below and paste this into PowerShell:

```powershell
$ACCOUNT_ID = "123456789012"
$REGION = "ap-south-1"
```

## 2. Delete the Budget
```powershell
aws budgets delete-budget --account-id $ACCOUNT_ID --budget-name Kill-Switch-Budget
Write-Host "Budget deleted!"
```

## 3. Delete the Lambda Function
```powershell
aws lambda delete-function --function-name Nuclear-Button --region $REGION
Write-Host "Lambda function deleted!"
```

## 4. Delete the IAM Role
*Note: Before you can delete a role, you must detach and delete all of its policies.*

```powershell
# Delete the custom inline policy
aws iam delete-role-policy --role-name Lambda-Kill-Switch-Role --policy-name KillSwitchResourceTermination

# Detach the AWS managed logging policy
aws iam detach-role-policy --role-name Lambda-Kill-Switch-Role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Delete the role itself
aws iam delete-role --role-name Lambda-Kill-Switch-Role

Write-Host "IAM Role and policies deleted!"
```

## 5. Delete the SNS Topic
To delete the topic, we first need to dynamically find its ARN (Amazon Resource Name).

```powershell
# Find the ARN of the topic
$TOPIC_ARN = (aws sns list-topics --region $REGION --query "Topics[?contains(TopicArn, 'Budget-Kill-Switch-Topic')].TopicArn" --output text)

if ($TOPIC_ARN) {
    # Delete the topic
    aws sns delete-topic --topic-arn $TOPIC_ARN --region $REGION
    Write-Host "SNS Topic deleted!"
} else {
    Write-Host "SNS Topic not found."
}
```

## Cleanup Complete
All Phase 1 resources have been completely removed from your AWS account!
