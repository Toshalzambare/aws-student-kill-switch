# AWS Nuclear Button — Hybrid Kill Switch

> 🛡️ A budget-triggered auto-termination system that protects your AWS account from surprise bills.

## What Is This?

When your AWS spending exceeds **$0.01**, this system **immediately** terminates all expensive resources in your account — EC2, RDS, NAT Gateways, EKS, Elastic IPs, SageMaker, and Load Balancers.

It uses a **two-layer architecture**:
1. **⚡ Lambda fires FIRST** — kills top 8 cost-generating services instantly
2. **🔥 aws-nuke runs SECOND** — if your laptop is online, performs a complete account wipe

## Architecture

```
Budget ($0.01) → SNS Topic ──┬── ⚡ Lambda (INSTANT — Heavy Hitter)
                              ├── 📨 SQS → Local Worker → aws-nuke (deep cleanup)
                              └── 📧 Email (notification)
```

**Primary region:** ap-south-1 (Mumbai) — scanned first, then all other regions.

## Quick Start

### Phase 1 — Immediate Kill Switch (30 minutes)
1. Read [`setup-guides/phase1-setup.md`](setup-guides/phase1-setup.md)
2. Create SNS Topic, IAM Role, Lambda Function, and Budget
3. Test with [`setup-guides/testing-guide.md`](setup-guides/testing-guide.md)

### Phase 2 — Deep Cleanup Layer (30 minutes)
1. Read [`setup-guides/phase2-setup.md`](setup-guides/phase2-setup.md)
2. Add SQS queue, local worker, and aws-nuke
3. Test the full hybrid flow

## Project Structure

```
├── README.md                          ← You are here
├── lambda/
│   └── heavy_hitter.py                # Lambda termination script (PRIMARY)
├── local-worker/
│   ├── sqs_worker.py                  # SQS polling + aws-nuke (SECONDARY)
│   ├── nuke-config.yaml               # aws-nuke safety configuration
│   └── requirements.txt               # Python dependencies
├── iam/
│   ├── lambda-execution-role.json     # Trust policy for Lambda role
│   └── lambda-permissions-policy.json # Resource termination permissions
└── setup-guides/
    ├── phase1-setup.md                # Step-by-step Phase 1 guide
    ├── phase2-setup.md                # Step-by-step Phase 2 guide
    └── testing-guide.md               # Safe testing procedures
```

## Cost Analysis: Will This Project Cost You Money?

**The short answer: The entire project is $0.00 / month.** It comfortably fits within the "Always Free" tier of AWS (meaning it's free even after your 1st year). The safety net itself will not generate a bill.

### Service Breakdown

| Service | What It Does | Free Tier Limit | Your Usage | Your Cost |
|---------|--------------|-----------------|------------|-----------|
| **AWS Budgets** | Watchdog | 2 action-enabled budgets/month | 1 budget | **$0.00** |
| **Amazon SNS** | Alarm Bell | 1M publishes, 1K emails/month | ~3 triggers | **$0.00** |
| **AWS Lambda** | Executioner | 1M requests, 400K GB-seconds/month | ~1 run (5s) | **$0.00** |
| **Amazon SQS** | aws-nuke Queue | 1M requests/month | ~130K requests (polling) | **$0.00** |
| **CloudWatch Logs** | Logging | 5 GB ingestion/month | Tiny fraction of 1 MB | **$0.00** |
| **IAM** | Permissions | Always Free | N/A | **$0.00** |

**The ONLY Way You Get Billed:**
1. **Testing with paid resources:** If you spin up a non-free EC2 instance (e.g., `m5.large`) to test the kill switch, you are billed for the minutes it was alive. Always test with `t2.micro` or `t3.micro`.
2. **EKS Clusters:** EKS charges $0.10/hour just for the control plane. Even if terminated quickly, you pay for that fraction of an hour.
3. **The Budget Delay:** AWS Budgets syncs billing data about **3 times a day (every 8 hours)**. It is not real-time. If you launch a massive service, it may take hours for the budget to detect the $0.01 breach and pull the trigger. You are billed for those hours.

## Services Targeted by Lambda (Heavy Hitter)

| Service | Action | Why It's Targeted |
|---------|--------|-------------------|
| EC2 Instances | Terminate | Most common accidental cost |
| RDS Databases | Delete (skip snapshot) | $15-200/month |
| NAT Gateways | Delete | $32/month just for existing |
| EKS Clusters | Delete (+ node groups) | $73/month for control plane |
| Elastic IPs | Release | $3.60/month when idle |
| SageMaker Notebooks | Stop | $5-50/month |
| Load Balancers | Delete (ALB/NLB/CLB) | $16-22/month minimum |
| EBS Volumes | Delete (unattached only) | $0.08-0.10/GB/month |

**aws-nuke** (Phase 2) covers everything else — all 200+ AWS services.

## ⚠️ Important Notes

- **Budget alerts have a delay** — AWS evaluates costs ~3 times/day, not in real-time
- **This is a safety net**, not instant protection — always be mindful of what you launch
- **Test in DRY-RUN mode first** — both scripts support preview mode
- **Lambda fires FIRST** — your wallet is protected even if your laptop is off
- **aws-nuke requires an Account Alias** — set it in IAM before using

## License

MIT — Use freely, but at your own risk. Always test before deploying.
