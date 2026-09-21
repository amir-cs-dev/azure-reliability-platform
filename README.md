# Azure Reliability Platform

An end-to-end Cloud/DevOps project focused on application deployment, reliability monitoring, incident detection, and automated delivery.

## Objective

Build a cloud-hosted application and an independent monitoring system that can detect failures, generate alerts, support incident investigation, and verify recovery.

The goal is to demonstrate practical Cloud/DevOps engineering through a working, reproducible system.

## Planned Technology Stack

- Cloud: Microsoft Azure
- Application: Python
- Infrastructure as Code: Terraform
- Containers: Docker
- CI/CD: GitHub Actions
- Monitoring: Azure Monitor and Application Insights
- Advanced infrastructure: AKS, Prometheus, and Grafana
- Future expansion: AWS

## Planned Architecture

GitHub → CI/CD → Azure Application
                         ↓
              Independent Health Monitor
                         ↓
                Incident Detection
                         ↓
                 Alerting & Logs
                         ↓
                Recovery Verification

## Project Structure

- `app/` — Application source code
- `monitor/` — Independent health checker
- `tests/` — Application and monitoring tests
- `docs/` — Architecture and incident documentation

## Development Roadmap

- [ ] Build and test the Python application
- [ ] Implement an independent health checker
- [ ] Containerize the application with Docker
- [ ] Provision Azure infrastructure using Terraform
- [ ] Implement CI/CD with GitHub Actions
- [ ] Configure monitoring and incident alerts
- [ ] Simulate failures and verify recovery
- [ ] Expand the platform to Kubernetes
- [ ] Implement an AWS version

## Current Status

**Phase 0 — Project initialization**

Repository structure created. Application implementation has not started.

## Engineering Principles

- Infrastructure defined as code
- Reproducible deployments
- Independent failure detection
- Automated testing
- Secure credential management
- Evidence-based reliability measurements

## Author

Amir Cirat

Cloud/DevOps Engineering | Data Center Infrastructure Background