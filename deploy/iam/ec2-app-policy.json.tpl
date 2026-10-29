{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AppObjectsReadWriteOnlyUnderPrefix",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::__BUCKET__/bts/*"
    },
    {
      "Sid": "DeployPackageReadOnly",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::__BUCKET__/deploy/*"
    },
    {
      "Sid": "ListOnlyOwnPrefixes",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::__BUCKET__",
      "Condition": {"StringLike": {"s3:prefix": ["bts/*", "deploy/*"]}}
    },
    {
      "Sid": "ReadOnlyTwoSecrets",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": ["__DB_SECRET_ARN__", "__ADMIN_SECRET_ARN__"]
    },
    {
      "Sid": "CustomMetricsOnlyInOwnNamespaces",
      "Effect": "Allow",
      "Action": "cloudwatch:PutMetricData",
      "Resource": "*",
      "Condition": {"StringEquals": {"cloudwatch:namespace": ["BTSExpress", "CWAgent"]}}
    },
    {
      "Sid": "CreateOwnLogGroupsOnly",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:PutRetentionPolicy"],
      "Resource": "arn:aws:logs:__REGION__:__ACCOUNT__:log-group:/bts-express/*"
    },
    {
      "Sid": "LogAgentListGroups",
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "*"
    },
    {
      "Sid": "WriteLogsToOwnGroupOnly",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
      "Resource": "arn:aws:logs:__REGION__:__ACCOUNT__:log-group:/bts-express/*:*"
    }
  ]
}
