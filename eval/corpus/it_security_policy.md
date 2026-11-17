# Helios Dynamics Information Security Policy

## Passwords and authentication

Passwords must be at least 14 characters long. Multi-factor authentication (MFA) is mandatory for
email, the VPN, source control and every production system. Hardware security keys are required
for administrators. Passwords are not rotated on a schedule; they must be changed immediately if
a compromise is suspected.

## Data classification

Company data is classified into four levels: Public, Internal, Confidential and Restricted.
Restricted data (customer battery telemetry, payroll, and private keys) may only be stored in the
approved encrypted vault and must never be shared over chat or email.

## Devices

All laptops must use full-disk encryption and lock automatically after 5 minutes of inactivity.
Lost or stolen devices must be reported to the IT helpdesk within 1 hour.

## Incident reporting

Any suspected security incident must be reported to security@helios.example within 2 hours of
discovery. The security team classifies incidents as SEV-1 to SEV-4. A SEV-1 incident triggers
the on-call incident commander and a status update to leadership every 30 minutes.

## Access reviews

Access to production systems is reviewed every quarter by the system owner. Access for leavers
is revoked on their last working day.
